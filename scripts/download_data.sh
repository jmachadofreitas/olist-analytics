#!/usr/bin/env bash

set -euo pipefail

readonly DATA_DIR="data/raw"
readonly MANIFEST="data/manifest.sha256"

mkdir -p "$DATA_DIR/ecommerce" "$DATA_DIR/seller-funnel"

uv run kaggle datasets download olistbr/brazilian-ecommerce \
    --path "$DATA_DIR/ecommerce" --unzip

uv run kaggle datasets download olistbr/marketing-funnel-olist \
    --path "$DATA_DIR/seller-funnel" --unzip

checksum() {
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$1"
    else
        shasum -a 256 "$1"
    fi
}

find "$DATA_DIR" -type f -name '*.csv' | LC_ALL=C sort | while IFS= read -r file; do
    checksum "$file"
done > "$MANIFEST"
