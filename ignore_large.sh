#!/bin/bash

# List of large directories/files to ignore
LARGE_ITEMS=("models" "static" ".mypy_cache" ".pytest_cache" "__pycache__")

# Make sure .gitignore exists
touch .gitignore

echo "Adding large files/folders to .gitignore..."

for item in "${LARGE_ITEMS[@]}"; do
    # Check if already ignored
    if ! grep -qx "$item/" .gitignore; then
        echo "$item/" >> .gitignore
        echo "✔ Ignored $item/"
    else
        echo "ℹ Already ignoring $item/"
    fi
done

echo "✅ Done! Large files/folders are now ignored."
