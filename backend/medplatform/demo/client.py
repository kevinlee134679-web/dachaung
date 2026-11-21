from fastapi.testclient import TestClient

from ..core.documents import uid

ORIGIN = "http://127.0.0.1:8000"


class SessionClient(TestClient):
    csrf: str


class ScenarioClients:
    def __init__(self, app, login_error, api_error):
        self.app = app
        self.login_error = login_error
        self.api_error = api_error
        self.clients = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        for client in self.clients:
            client.close()

    def login(self, account):
        client = SessionClient(self.app, base_url=ORIGIN)
        self.clients.append(client)
        response = client.post(
            "/api/v1/auth/demo-session",
            json={"demo_account_id": account},
            headers={"Origin": ORIGIN, "Idempotency-Key": uid()},
        )
        if response.status_code != 201:
            raise RuntimeError(self.login_error)
        client.csrf = response.json()["data"]["csrf_token"]
        return client

    def call(self, client, method, path, body=None):
        response = client.request(
            method,
            "/api/v1" + path,
            json=body,
            headers={
                "Origin": ORIGIN,
                "X-CSRF-Token": client.csrf,
                "Idempotency-Key": uid(),
            },
        )
        if response.status_code >= 300:
            raise RuntimeError(self.api_error + response.json()["error"]["code"])
        return response.json()["data"]
