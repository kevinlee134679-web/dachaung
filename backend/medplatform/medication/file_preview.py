import re
import unicodedata
from io import BytesIO

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from .inputs import positive_decimal

FIELDS = {
    "name": ("药品名称", "药品", "药名", "Medication"),
    "dose": ("每次剂量", "Dose"),
    "unit": ("剂量单位", "Dose unit"),
    "frequency": ("用药频次", "服药频次", "频次", "Frequency"),
    "times": ("服药时间", "用药时间", "Times"),
}
LABELS = {
    label.casefold(): key for key, synonyms in FIELDS.items() for label in synonyms
}
FIELD = re.compile(
    r"(?:^|[\t ;|])(" + "|".join(map(re.escape, LABELS)) + r")\s*:\s*",
    re.IGNORECASE,
)
DOSE = re.compile(
    r"([0-9]+(?:\.[0-9]+)?)\s*(片|粒|袋|支|滴|mg|g|mcg|μg|ml|单位)?", re.IGNORECASE
)
UNIT = re.compile(r"片|粒|袋|支|滴|mg|g|mcg|μg|ml|单位", re.IGNORECASE)
DAILY = re.compile(
    r"(?:每天|每日|daily)(?:\s*([0-9]{1,2}|[一二两三四五六七八九十])\s*次)?",
    re.IGNORECASE,
)
TIME = re.compile(r"(?:[0-9]|[01][0-9]|2[0-3]):[0-5][0-9]")
COUNTS = dict(zip("一二两三四五六七八九十", (1, 2, 2, 3, 4, 5, 6, 7, 8, 9, 10)))
MAX_PAGES = 12
MAX_PAGE_CONTENT = 1024 * 1024
MAX_PAGE_TEXT = 20_000
MAX_CANDIDATES = 30


def only(fields, key):
    options = set(fields.get(key, []))
    return next(iter(options)) if len(options) == 1 else None


def summarize(fields, page):
    name = only(fields, "name")
    if not name or len(name) > 128:
        return None
    dose = only(fields, "dose")
    unit = only(fields, "unit")
    value = None
    match = DOSE.fullmatch(dose or "")
    if match and len(match[1]) <= 80:
        inline = match[2]
        # The two explicit unit locations must agree if both are present.
        if len(set(fields.get("unit", []))) > 1 or (
            unit
            and (
                not UNIT.fullmatch(unit)
                or inline
                and unit.casefold() != inline.casefold()
            )
        ):
            unit = None
        else:
            unit = unit or inline
            try:
                value = positive_decimal(match[1])
            except ValueError:
                pass
    else:
        unit = None
    frequency = only(fields, "frequency")
    daily = DAILY.fullmatch(frequency or "")
    times = re.split(r"[\s,、和与及]+", only(fields, "times") or "")
    times = [moment.zfill(5) for moment in times]
    count = daily[1] if daily else None
    expected = (int(count) if count.isascii() else COUNTS[count]) if count else None
    if (
        not daily
        or not all(TIME.fullmatch(moment) for moment in times)
        or len(set(times)) != len(times)
        or (expected is not None and expected != len(times))
    ):
        times = []
    return {
        "name": name,
        "dose_value": value,
        "dose_unit": unit if value is not None else None,
        "frequency_text": frequency,
        "schedule_kind": "daily" if daily else None,
        "times": sorted(times),
        "page": page,
        "source_excerpt": "\n".join(
            f"{FIELDS[key][0]}：{value}"
            for key, values in fields.items()
            for value in values
        )[:1000],
    }


def extract_candidates(text, page):
    fields = {}
    for line in unicodedata.normalize("NFKC", text).splitlines():
        matches = list(FIELD.finditer(line))
        for index, match in enumerate(matches):
            key = LABELS[match[1].casefold()]
            if key == "name":
                if fields and (candidate := summarize(fields, page)):
                    yield candidate
                fields = {}
            if key == "name" or "name" in fields:
                end = (
                    matches[index + 1].start()
                    if index + 1 < len(matches)
                    else len(line)
                )
                value = line[match.end() : end].strip(" \t;|")
                if value:
                    fields.setdefault(key, []).append(value)
    if fields and (candidate := summarize(fields, page)):
        yield candidate


def medication_preview(media_type, content):
    if media_type != "application/pdf":
        return {"status": "unsupported", "candidates": [], "partial": False}
    candidates = []
    readable = False
    try:
        pdf = PdfReader(BytesIO(content), strict=True)
        if pdf.is_encrypted:
            return {"status": "unreadable", "candidates": [], "partial": False}
        partial = len(pdf.pages) > MAX_PAGES
        for index, page in enumerate(pdf.pages[:MAX_PAGES], 1):
            stream = page.get_contents()
            if stream and len(stream.get_data()) > MAX_PAGE_CONTENT:
                partial = True
                continue
            text = page.extract_text()
            partial |= len(text) > MAX_PAGE_TEXT
            readable |= bool(text.strip())
            for candidate in extract_candidates(text[:MAX_PAGE_TEXT], index):
                if len(candidates) == MAX_CANDIDATES:
                    return {
                        "status": "ready",
                        "candidates": candidates,
                        "partial": True,
                    }
                candidates.append(candidate)
    except (
        PdfReadError,
        ValueError,
        TypeError,
        RecursionError,
        OverflowError,
        NotImplementedError,
    ):
        return {"status": "unreadable", "candidates": [], "partial": False}
    return {
        "status": "ready"
        if candidates
        else ("no_candidates" if readable else "no_text"),
        "candidates": candidates,
        "partial": partial,
    }
