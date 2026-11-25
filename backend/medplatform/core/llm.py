from dataclasses import dataclass

import httpx2

DOCUMENT_TIMEOUT_SECONDS = 240


@dataclass(frozen=True)
class Reply:
    content: str | None
    usage: dict | None


class LLMClient:
    def __init__(self, settings):
        self.client = httpx2.Client(
            base_url=settings.LLM_BASE_URL,
            headers={
                "Authorization": f"Bearer {settings.LLM_API_KEY.get_secret_value()}"
            },
            timeout=settings.LLM_TIMEOUT_SECONDS,
        )
        self.model = settings.LLM_MODEL

    def chat(self, messages: list[dict]) -> Reply:
        response = self.client.post(
            "/chat/completions",
            json={
                "model": self.model,
                "messages": messages,
                "response_format": {"type": "json_object"},
                "stream": False,
            },
        )
        response.raise_for_status()
        body = response.json()
        return Reply(
            body["choices"][0]["message"]["content"] or None, body.get("usage")
        )

    def upload_document(self, content: bytes, filename: str) -> str:
        response = self.client.post(
            "/files",
            data={
                "purpose": "text_recognition",
                "expires_after[anchor]": "created_at",
                "expires_after[seconds]": "3600",
            },
            files={"file": (filename, content, "application/pdf")},
            timeout=DOCUMENT_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return response.json()["id"]
