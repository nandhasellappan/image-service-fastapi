"""
Service module for interacting with Amazon DynamoDB to store and retrieve image metadata.
"""
import boto3
from typing import Dict, List, Optional, Any
from datetime import datetime
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError
from config import settings
from utils.logger import get_logger

logger = get_logger(__name__)


class DynamoDBService:
    def __init__(self):
        """
        Initialize the DynamoDB service.

        Sets up the Boto3 resource and table reference.
        Attempts to detect a Global Secondary Index (GSI) for `user_id` to optimize queries.
        """
        logger.info(f"Initializing DynamoDBService for table: {settings.dynamodb_table_name}")
        self.resource = boto3.resource(
            'dynamodb',
            endpoint_url=settings.endpoint_url,
            region_name=settings.aws_region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key
        )
        self.table = self.resource.Table(settings.dynamodb_table_name)
        # detect an existing GSI that uses `user_id` as partition key (e.g. UserIdIndex)
        self.user_id_index_name: Optional[str] = None
        try:
            client = self.resource.meta.client
            desc = client.describe_table(TableName=settings.dynamodb_table_name)
            for gsi in desc.get('Table', {}).get('GlobalSecondaryIndexes', []) or []:
                ks = gsi.get('KeySchema', [])
                if any(k.get('AttributeName') == 'user_id' and k.get('KeyType') == 'HASH' for k in ks):
                    self.user_id_index_name = gsi.get('IndexName')
                    logger.info(f"Detected user_id GSI: {self.user_id_index_name}")
                    break
        except Exception as e:
            logger.debug(f"Could not describe table to find GSIs: {e}")
    
    def put_metadata(self, image_id: str, metadata: Dict) -> None:
        """
        Store image metadata in DynamoDB.

        Args:
            image_id (str): The unique identifier for the image.
            metadata (Dict): A dictionary containing metadata attributes (e.g., user_id, filename, tags).
        """
        logger.info(f"Storing metadata: {image_id}")
        item = {
            'image_id': image_id,
            'created_at': datetime.utcnow().isoformat(),
            **metadata
        }
        resp = self.table.put_item(Item=item)
        # log DynamoDB response metadata for observability
        try:
            rmeta = resp.get('ResponseMetadata', {})
            logger.debug(f"DynamoDB put_item response", extra={'response_metadata': rmeta})
        except Exception:
            logger.debug("DynamoDB put_item completed")
    
    def get_metadata(self, image_id: str) -> Optional[Dict]:
        """
        Retrieve metadata for a specific image.

        Args:
            image_id (str): The unique identifier for the image.

        Returns:
            Optional[Dict]: The metadata dictionary if found, otherwise None.
        """
        # normalize and validate image_id to avoid DynamoDB ValidationException
        image_id = (image_id or '').strip()
        logger.info(f"Retrieving metadata: {image_id}")
        if not image_id:
            logger.debug("Empty image_id provided to get_metadata; skipping DynamoDB call")
            return None
        try:
            response = self.table.get_item(Key={'image_id': image_id})
            return response.get('Item')
        except ClientError as e:
            logger.error(f"DynamoDB get_item failed for {image_id}: {e}")
            raise
    
    def delete_metadata(self, image_id: str) -> None:
        """
        Delete metadata for a specific image.

        Args:
            image_id (str): The unique identifier for the image to delete.
        """
        logger.info(f"Deleting metadata: {image_id}")
        resp = self.table.delete_item(Key={'image_id': image_id})
        try:
            rmeta = resp.get('ResponseMetadata', {})
            logger.debug(f"DynamoDB delete_item response", extra={'response_metadata': rmeta})
        except Exception:
            logger.debug("DynamoDB delete_item completed")
    
    def list_metadata(
        self,
        user_id: Optional[str] = None,
        category: Optional[str] = None,
        is_public: Optional[bool] = None,
        tags: Optional[List[str]] = None,
        filename_contains: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 50,
        exclusive_start_key: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        List metadata with optional filters. Best-effort uses a GSI named 'user_id-index'
        to perform efficient queries when `user_id` is provided. Otherwise falls back
        to a scan with FilterExpression.

        Returns:
            Dict containing:
            - 'items': List of metadata dictionaries.
            - 'last_evaluated_key': The key to pass as `exclusive_start_key` to retrieve the next page.
                                    None if no more items exist.
        """
        logger.info(f"Listing metadata with filters user_id={user_id} category={category} is_public={is_public} tags={tags} limit={limit}")

        filter_expr = None

        # Build filter expressions for non-key attributes
        if category is not None:
            expr = Attr('category').eq(category)
            filter_expr = expr if filter_expr is None else filter_expr & expr

        if is_public is not None:
            expr = Attr('is_public').eq(is_public)
            filter_expr = expr if filter_expr is None else filter_expr & expr

        if filename_contains:
            expr = Attr('filename').contains(filename_contains)
            filter_expr = expr if filter_expr is None else filter_expr & expr

        if start_date or end_date:
            # assume uploaded_at or created_at ISO timestamps stored; use created_at if present
            if start_date:
                expr = Attr('created_at').gte(start_date)
                filter_expr = expr if filter_expr is None else filter_expr & expr
            if end_date:
                expr = Attr('created_at').lte(end_date)
                filter_expr = expr if filter_expr is None else filter_expr & expr

        if tags:
            for t in tags:
                expr = Attr('tags').contains(t)
                filter_expr = expr if filter_expr is None else filter_expr & expr

        # If user_id provided, try to use a detected GSI for efficient query
        if user_id and self.user_id_index_name:
            try:
                key_cond = Key('user_id').eq(user_id)
                kwargs = {
                    'KeyConditionExpression': key_cond,
                    'Limit': limit,
                }
                if filter_expr is not None:
                    kwargs['FilterExpression'] = filter_expr
                if exclusive_start_key:
                    kwargs['ExclusiveStartKey'] = exclusive_start_key
                response = self.table.query(IndexName=self.user_id_index_name, **kwargs)
                items = response.get('Items', [])
                lek = response.get('LastEvaluatedKey')
                return {'items': items, 'last_evaluated_key': lek}
            except ClientError as e:
                logger.warning(f"Query on GSI '{self.user_id_index_name}' failed: {e}. Falling back to scan.")
        elif user_id and not self.user_id_index_name:
            logger.debug("user_id provided but no user_id GSI detected; will scan with filter.")

        # If user_id provided but GSI query failed or not used, ensure we filter by user_id when scanning
        if user_id:
            expr = Attr('user_id').eq(user_id)
            filter_expr = expr if filter_expr is None else filter_expr & expr

        # Fallback: scan with constructed FilterExpression
        scan_kwargs: Dict[str, Any] = {'Limit': limit}
        if filter_expr is not None:
            scan_kwargs['FilterExpression'] = filter_expr
        if exclusive_start_key:
            scan_kwargs['ExclusiveStartKey'] = exclusive_start_key

        items: List[Dict] = []
        response = self.table.scan(**scan_kwargs)
        items.extend(response.get('Items', []))
        last_evaluated_key = response.get('LastEvaluatedKey')

        return {'items': items, 'last_evaluated_key': last_evaluated_key}


dynamodb_service = DynamoDBService()
