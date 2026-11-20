from fastapi.testclient import TestClient


class SessionClient(TestClient):
    csrf: str
