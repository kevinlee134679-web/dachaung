from io import BytesIO

import fixtures as support
from medplatform.medication.file_preview import extract_candidates, medication_preview
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject


def pdf_with_text(*lines):
    pdf = PdfWriter()
    page = pdf.add_blank_page(width=400, height=300)
    font = {"/Type": "/Font", "/Subtype": "/Type1", "/BaseFont": "/Helvetica"}
    font_dict = DictionaryObject(
        {NameObject(k): NameObject(v) for k, v in font.items()}
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_dict})}
    )
    stream = DecodedStreamObject()
    operators = ["BT /F1 13 Tf 36 240 Td 18 TL"]
    operators.extend(f"({text}) Tj T*" for text in lines)
    stream.set_data((" ".join(operators) + " ET").encode("ascii"))
    page.replace_contents(stream)
    content = BytesIO()
    pdf.write(content)
    return content.getvalue()


class FilePreviewTests(support.IdentityFixture):
    def test_saved_pdf_candidates_are_read_only_and_patient_only(self):
        content = pdf_with_text(
            "Medication: DEMO MEDICINE",
            "Dose: 1.5 tablets",
            "Frequency: daily",
            "Times: 08:00, 20:00",
        )
        response = self.upload(raw=content)
        self.assertEqual(response.status_code, 201, response.text)
        file = response.json()["data"]
        endpoint = f"/files/{file['file_id']}/medication-preview"
        preview = self.call(self.a, "GET", endpoint)
        self.assertEqual(preview["status"], "ready")
        self.assertEqual(len(preview["candidates"]), 1)
        candidate = preview["candidates"][0]
        self.assertEqual(candidate["name"], "DEMO MEDICINE")
        self.assertEqual(candidate["page"], 1)
        self.assertEqual(candidate["times"], ["08:00", "20:00"])
        self.assertIsNone(candidate["dose_value"])
        self.assertIn("1.5 tablets", candidate["source_excerpt"])
        self.assertEqual(self.call(self.a, "GET", endpoint), preview)
        self.call(self.b, "GET", endpoint, expected=404)
        self.bind(["files:read"])
        self.call(self.f, "GET", f"/files/{file['file_id']}/content")
        self.call(self.f, "GET", endpoint, expected=403)
        for resource in ("medications", "drafts", "plans"):
            self.assertEqual(
                self.call(self.a, "GET", f"/patients/{support.PA}/{resource}")["items"],
                [],
            )

    def test_only_explicit_fields_are_prefilled(self):
        medicine, ambiguous, conflicting = extract_candidates(
            """药品名称：虚构 A；每次剂量：1.50 片
用药频次：每日两次；服药时间：８：００, 20:00
药品名称：虚构 B
每次剂量：2mg
用药频次：每日两次
药品名称：虚构 C
每次剂量：1片
剂量单位：粒
服药时间：08:00
用药频次：每日两次
""",
            2,
        )
        self.assertEqual(medicine["dose_value"], "1.5")
        self.assertEqual(medicine["dose_unit"], "片")
        self.assertEqual(medicine["times"], ["08:00", "20:00"])
        self.assertEqual(ambiguous["times"], [])
        self.assertEqual(ambiguous["frequency_text"], "每日两次")
        self.assertEqual(ambiguous["dose_unit"], "mg")
        self.assertEqual(conflicting["times"], [])
        self.assertIsNone(conflicting["dose_value"])
        self.assertIsNone(conflicting["dose_unit"])

    def test_image_only_or_invalid_documents_yield_no_guesses(self):
        self.assertEqual(medication_preview("image/png", b"")["status"], "unsupported")
        self.assertEqual(
            medication_preview("application/pdf", b"%PDF-1.4")["status"], "unreadable"
        )
        self.assertEqual(
            medication_preview("application/pdf", pdf_with_text())["status"], "no_text"
        )
