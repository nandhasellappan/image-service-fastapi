#!/usr/bin/env bash
set -euo pipefail

# ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="${ROOT_DIR}/build_lambda"
PKG_DIR="${BUILD_DIR}/package"
ZIP_PATH="${ROOT_DIR}/lambda_function.zip"

# choose one:
ARCH="${ARCH:-x86_64}"   # x86_64 or aarch64
PYVER="${PYVER:-3.11}"

rm -rf "${BUILD_DIR}" "${ZIP_PATH}"
mkdir -p "${PKG_DIR}"

# Install Lambda-compatible wheels into package/
if [ "${ARCH}" = "x86_64" ]; then
  PLATFORM="manylinux2014_x86_64"
else
  PLATFORM="manylinux2014_aarch64"
fi
echo "Platform ${PLATFORM}"

python.exe -m pip install -r "${ROOT_DIR}/requirements.txt" \
  --target "${PKG_DIR}" \
  --platform "${PLATFORM}" \
  --implementation cp \
  --python-version "${PYVER}" \
  --only-binary=:all: \
  --upgrade

# Copy your code next to dependencies
cp -r "${ROOT_DIR}/src/." "${PKG_DIR}/"

# Zip it (Lambda expects deps + code at zip root)
cd "${PKG_DIR}"
python -m zipfile -c "${ZIP_PATH}" .
echo "Created ${ZIP_PATH}"
