import requests
import time


resp = requests.post("http://localhost:8000/auth", json={"key": "supersecret-client-key"}, timeout=15)
print(resp.status_code)

respjson = resp.json()
print(resp.json())