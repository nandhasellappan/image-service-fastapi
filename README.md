# Serverless Image Service API

A high-performance, serverless REST API built with **FastAPI** and **Python 3.11** for managing image uploads, retrieval, and metadata. Designed for deployment on **AWS Lambda**, utilizing **S3** for object storage and **DynamoDB** for metadata indexing.

This project demonstrates a cloud-native implementation strategy, featuring local cloud simulation via **LocalStack**, secure configuration management with **AWS Secrets Manager**, and efficient data access patterns.

## 🚀 Key Features

- **Serverless Architecture**: Fully compatible with AWS Lambda and API Gateway via `Mangum`.
- **Scalable Storage**: Images stored in S3 with secure, time-limited access via **Presigned URLs**.
- **High-Performance Metadata**: DynamoDB single-table design principles with Global Secondary Indexes (GSI) for efficient filtering by user.
- **Secure Authentication**: API Token validation backed by **AWS Secrets Manager** (with caching strategy).
- **Advanced Filtering**: List images by category, tags, visibility, and date ranges.
- **Pagination**: Efficient DynamoDB pagination using `LastEvaluatedKey`.
- **Local Development**: Full AWS environment simulation using **LocalStack** (S3, DynamoDB, Lambda, Secrets Manager).
- **Observability**: Structured logging configured for AWS CloudWatch.

## 🛠️ Tech Stack

- **Framework**: FastAPI, Pydantic
- **Runtime**: Python 3.11
- **AWS Services**: Lambda, API Gateway, S3, DynamoDB, Secrets Manager, CloudWatch
- **Infrastructure**: Docker, Docker Compose, LocalStack
- **SDK**: Boto3

## ww🏗️ Architecture & Design Decisions

### 1. Storage Strategy (S3 + Presigned URLs)
Instead of serving binary image data through the API (which is expensive and slow for Lambda), the service generates **S3 Presigned URLs**.
- **Uploads**: The API handles the file stream to S3 immediately.
- **Downloads**: The API returns a temporary URL, offloading the data transfer to S3's robust infrastructure.

### 2. Database Design (DynamoDB)
- **Partition Key**: `image_id` (UUID) for uniform data distribution.
- **GSI (`UserIdIndex`)**: `user_id` (Partition Key) + `created_at` (Sort Key).
    - *Why?* Allows efficient querying of "all images for a specific user", sorted by date, without scanning the entire table.
- **Pagination**: Implemented using `ExclusiveStartKey` to handle large datasets without memory overhead.

### 3. Security (Secrets Manager)
Static API tokens are not hardcoded. The application fetches the `image_service_api_token` from AWS Secrets Manager at runtime.
- **Caching**: The token is cached in the Lambda execution context global scope to reduce API calls and latency on subsequent warm invocations.

## ⚡ Getting Started

### Prerequisites
- Python 3.11+
- Docker & Docker Compose
- AWS CLI (optional, for manual interaction)
- `awslocal` (optional, wrapper for LocalStack)

### 1. Clone the Repository
```bash
git clone https://github.com/yourusername/image-service-fastapi.git
cd image-service-fastapi
```

### 2. Environment Setup
Create a virtual environment and install dependencies:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Start Local Infrastructure
We use **LocalStack** to simulate AWS services locally. The `docker-compose.yml` includes an initialization script (`init-aws.sh`) that automatically provisions the S3 bucket, DynamoDB table, and Secrets Manager secret.

```bash
cd localstack
docker-compose up -d
```

*Wait for a few moments for the services to initialize.*

### 4. Configuration
The application uses `pydantic-settings`. Create a `.env` file in the `src` directory or rely on the defaults set for LocalStack in `config.py`.

**Default Local Config:**
- **Endpoint**: `http://localhost:4566`
- **Region**: `us-east-1`
- **Bucket**: `image-storage-bucket`
- **Table**: `ImageMetadata`

## 🏃‍♂️ Running the Application

You can run the FastAPI server locally using Uvicorn. It will connect to the Dockerized LocalStack services.

```bash
cd src
uvicorn main:app --reload --port 8000
```

Access the interactive API documentation at: **http://localhost:8000/docs**

## 🧪 API Usage

### Authentication
Requests to sensitive endpoints (like Bulk Delete) require authentication.
- **Header**: `x-api-key: <user_id>:<api_token>`
- **Default Local Token**: `6f0ced3f-5028-4b1c-8294-3d894c48c645`

### Key Endpoints

#### 1. Upload Image
`POST /api/v1/images`
- **Form Data**: `files` (binary), `user_id`, `category`, `tags`
- Stores file in S3 and metadata in DynamoDB.

#### 2. Get Image Metadata
`GET /api/v1/images/{image_id}`
- Returns metadata and a valid `presigned_url` to view the image.

#### 3. List Images
`GET /api/v1/images`
- **Query Params**: `user_id`, `category`, `tags`, `limit`
- Returns a list of images and a `last_evaluated_key` for pagination.

#### 4. Bulk Delete
`DELETE /api/v1/images`
- **Body**: `{"user_id": "...", "image_ids": [...]}`
- **Auth Required**: Yes.

## 📂 Project Structure

```
image-service-fastapi/
├── localstack/             # Infrastructure definitions
│   ├── docker-compose.yml  # LocalStack setup
│   └── init-aws.sh         # AWS resource provisioning script
├── src/
│   ├── api/
│   │   └── routes/         # API Endpoint definitions
│   ├── models/             # Pydantic schemas
│   ├── services/           # Business logic (S3, DynamoDB)
│   ├── utils/              # Logging and helpers
│   ├── config.py           # Environment configuration
│   ├── main.py             # FastAPI entry point
│   └── lambda_handler.py   # Mangum adapter for AWS Lambda
└── requirements.txt
```

## 🐛 Debugging & Logs

The application uses a custom logger that outputs JSON-formatted logs suitable for CloudWatch Query Syntax.

To view logs when running in LocalStack Lambda:
```bash
awslocal logs tail /aws/lambda/image-service-lambda --follow
```

## 🚢 Deployment

The project is ready for packaging as a Lambda function.

1. **Package Dependencies**: Install dependencies into a `package` folder.
2. **Zip**: Zip the `src` directory and the `package` directory.
3. **Deploy**: Upload the zip to AWS Lambda.

*(Note: The `init-aws.sh` script simulates this deployment process locally).*

## 📜 License

This project is licensed under the MIT License.