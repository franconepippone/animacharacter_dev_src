import requests
import time


class ACRemoteClient:
    def __init__(self, ip: str) -> None:
        self.ip = ip
        self.base_url = f"http://{ip}:8000/auth"

    def create_session(self, secret_key: str, timeout: int = 10) -> bool:
        try:
            resp = requests.post(f"http://{self.ip}:8000/auth", json={"key": secret_key}, timeout=timeout)
        except requests.exceptions.RequestException as e:
            print(e)
            return False
        else:
            print(resp.status_code)

            respjson = resp.json()
            print(resp.json())

        return respjson.get("success", False)
