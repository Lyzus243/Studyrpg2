import requests
import json

# Get the OpenAPI schema
response = requests.get("http://127.0.0.1:8000/openapi.json")
if response.status_code == 200:
    schema = response.json()
    print("Available paths:")
    for path in schema.get("paths", {}).keys():
        print(f"  {path}")
else:
    print("Failed to get OpenAPI schema")