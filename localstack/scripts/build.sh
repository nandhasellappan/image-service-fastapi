#!/bin/bash
set -e

echo "Building Lambda deployment package..."

cd ..

BUILD_DIR="build"
CACHE_DIR=".build_cache"

# Check for rebuild flag
if [ "$1" == "--rebuild" ]; then
    echo "Force rebuild requested - clearing cache..."
    rm -rf "$CACHE_DIR"
fi

# Clean previous build
rm -rf "$BUILD_DIR" lambda_function.zip
mkdir -p "$BUILD_DIR"

# Handle dependencies
if [ -d "$CACHE_DIR" ]; then
    echo "✓ Using cached dependencies"
    cp -r "$CACHE_DIR/"* "$BUILD_DIR/"
else
    echo "Installing dependencies..."
    mkdir -p "$CACHE_DIR"
    python.exe -m pip install -r requirements.txt -t "$CACHE_DIR/" --upgrade --quiet
    echo "✓ Dependencies cached"
    cp -r "$CACHE_DIR/"* "$BUILD_DIR/"
fi

# Copy source code
echo "✓ Copying source code"
cp -r src/* "$BUILD_DIR/"

# Create zip package
echo "✓ Creating deployment package"
cd "$BUILD_DIR"
python3 -m zipfile -c ../lambda_function.zip .
cd ..

# Verify package
if [ ! -f "lambda_function.zip" ]; then
    echo "✗ ERROR: Failed to create lambda_function.zip"
    exit 1
fi

echo "✓ Package created ($(du -h lambda_function.zip | cut -f1))"

cd localstack
