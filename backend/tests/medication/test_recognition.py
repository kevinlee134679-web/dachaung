import json
import unittest

import httpx2

import fixtures as support
from medplatform.core.llm import Reply
from medplatform.medication.recognition import recognize


class FakeLLM:
    def __init__(self, content):
        self.content = content
        self.calls = []

    def upload_document(self, content, filename):
        self.calls.append(("upload", content, filename))
        return "file-1"

    def chat(self, messages):
        self.calls.append(("chat", messages))
        if isinstance(self.content, Exception):
            raise self.content
        return Reply(self.content, None)


class RecognitionTests(unittest.TestCase):
    def test_image_and_field_validation(self):
        llm = FakeLLM(
            json.dumps(
                {
                    "medications": [
                        {"name": "药", "times": ["08:00", "25:00"], "daily_count": 2},
                        {"name": ""},
                    ],
                    "allergies": None,
                    "diagnosis": None,
                }
            )
        )
        result = recognize(llm, "image/png", b"image", "file.png")
        self.assertEqual(result["status"], "ready")
        self.assertEqual(len(result["medications"]), 1)
        self.assertEqual(result["medications"][0]["times"], ["08:00"])
        self.assertEqual(
            llm.calls[0][1][1]["content"][1]["image_url"]["url"],
            "data:image/png;base64,aW1hZ2U=",
        )

    def test_pdf_upload(self):
        llm = FakeLLM('{"medications": [], "allergies": null, "diagnosis": null}')
        self.assertEqual(
            recognize(llm, "application/pdf", b"pdf", "a.pdf")["status"],
            "no_candidates",
        )
        self.assertEqual(llm.calls[0], ("upload", b"pdf", "a.pdf"))
        self.assertEqual(
            llm.calls[1][1][1]["content"][0], {"type": "file", "file_id": "file-1"}
        )

    def test_failures_and_unavailable(self):
        for content in (httpx2.TimeoutException("timeout"), "not json", "{}"):
            with self.subTest(content=content):
                self.assertEqual(
                    recognize(FakeLLM(content), "image/jpeg", b"", "a.jpg")["status"],
                    "failed",
                )
        self.assertEqual(
            recognize(None, "image/jpeg", b"", "a.jpg")["status"], "unavailable"
        )


class RecognitionHttpTests(support.IdentityFixture):
    def test_family_access_and_patient_isolation(self):
        file = self.upload().json()["data"]
        endpoint = f"/files/{file['file_id']}/medication-recognition"
        self.bind(["files:read"])
        self.assertEqual(self.call(self.f, "GET", endpoint)["status"], "unavailable")
        self.call(self.b, "GET", endpoint, expected=404)
