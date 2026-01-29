import requests
import time

try:
    resp = requests.post("http://localhost:8000/auth", json={"key": "supersecret-client-key"}, timeout=15)
except requests.exceptions.RequestException as e:
    print(e)
else:

    print(resp.status_code)

    respjson = resp.json()
    print(resp.json())