"""Entity extraction from industrial text.

- Equipment tags, split into subjects and negated mentions ("No relation to Pump P-101"), with
  codes that only look like tags (DN50, PN16, IP65, M12 threads, REV-12, "P-100 series") excluded.
- Dates normalised to ISO (day-first for numeric dates), so they sort chronologically.
- Measurements with thousands separators and percentages ("2,950 rpm", "85%").
- Failure modes and maintenance actions matched on word boundaries and skipped when negated
  ("no cavitation observed", "was not tested").
"""
import re
from datetime import date

# ── Equipment tags ──────────────────────────────────────────────────────────────────────────────
ASSET_PATTERN = re.compile(r"\b([A-Z]{1,4})([- ]?)(\d{2,4}[A-Z]?)\b")
NOT_ASSET_PREFIXES = frozenset({
    "IR", "SOP", "OEM", "ISO", "API", "DN", "PN", "IP", "REV", "UTC", "GMT", "IST", "ID", "WO", "PO",
    "NO", "SN", "PH", "SIL", "EN", "IEC", "ASME", "ANSI", "NFPA", "MSME", "PAGE", "STEP", "ROOM",
    "JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC",
})
NOT_ASSET_FOLLOWERS = re.compile(r"\s*(?:series|family|class|range|standard)\b", re.IGNORECASE)
NEGATED_ASSET_CUE = re.compile(
    r"(?:no relation (?:to|with)|not related to|unrelated to|no (?:link|connection) (?:to|with)|"
    r"not linked to|ruled out|independent of|not caused by|other than)\s+(?:[\w-]+\s+){0,2}$",
    re.IGNORECASE,
)


def asset_mentions(text: str, registry: set[str] | None = None) -> tuple[list[str], list[str]]:
    """Return (subject tags, negated-only tags). With a non-empty registry, only registry tags count."""
    subject: set[str] = set()
    negated: set[str] = set()
    for match in ASSET_PATTERN.finditer(text):
        prefix, separator, number = match.groups()
        if prefix in NOT_ASSET_PREFIXES:
            continue
        if separator == " " and len(prefix) < 2:  # "A 150 mm" is not a tag
            continue
        if prefix == "M" and not separator and len(number) <= 2:  # M12 / M16 thread sizes
            continue
        if NOT_ASSET_FOLLOWERS.match(text, match.end()):
            continue
        tag = f"{prefix}-{number}"
        if registry and tag not in registry:
            continue
        before = text[max(0, match.start() - 60):match.start()]
        (negated if NEGATED_ASSET_CUE.search(before) else subject).add(tag)
    return sorted(subject), sorted(negated - subject)


def normalize_tag(value: str) -> str:
    match = ASSET_PATTERN.fullmatch(value.strip().upper())
    return f"{match.group(1)}-{match.group(3)}" if match else value.strip().upper()


# ── Dates ───────────────────────────────────────────────────────────────────────────────────────
MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}
_MON = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?"
DATE_REGEX = (
    rf"\d{{1,2}}[-/ ]{_MON}[-/ ,]\s?\d{{2,4}}"   # 12-Jan-2025, 12 Jan 2025
    rf"|{_MON} \d{{1,2}},? \d{{4}}"              # Jan 12, 2025
    r"|\d{4}-\d{2}-\d{2}"                        # 2025-01-12
    r"|\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}"          # 12/01/2025 (day first)
)
DATE_PATTERN = re.compile(rf"\b(?:{DATE_REGEX})\b", re.IGNORECASE)


def parse_date(raw: str) -> date | None:
    text = raw.strip().replace(",", " ").replace(".", " ")
    try:
        if m := re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", raw.strip()):
            return date(int(m[1]), int(m[2]), int(m[3]))
        if m := re.fullmatch(r"(\d{1,2})[-/ ]([A-Za-z]{3})[a-z]*[-/ ]\s*(\d{2,4})", text):
            return date(_year(m[3]), MONTHS[m[2].lower()], int(m[1]))
        if m := re.fullmatch(r"([A-Za-z]{3})[a-z]* (\d{1,2}) +(\d{4})", text):
            return date(int(m[3]), MONTHS[m[1].lower()], int(m[2]))
        if m := re.fullmatch(r"(\d{1,2})[-/ ](\d{1,2})[-/ ](\d{2,4})", text):
            day, month = int(m[1]), int(m[2])
            if month > 12 and day <= 12:  # clearly month-first
                day, month = month, day
            return date(_year(m[3]), month, day)
    except (KeyError, ValueError):
        return None
    return None


def _year(value: str) -> int:
    year = int(value)
    return year + 2000 if year < 100 else year


def find_dates(text: str) -> list[str]:
    """ISO dates in order of first appearance."""
    found: dict[str, None] = {}
    for match in DATE_PATTERN.finditer(text):
        parsed = parse_date(match.group(0))
        if parsed:
            found.setdefault(parsed.isoformat(), None)
    return list(found)


# ── Measurements ────────────────────────────────────────────────────────────────────────────────
UNITS = {"mm/s": "mm/s", "bar": "bar", "psi": "psi", "kpa": "kPa", "mpa": "MPa", "rpm": "rpm",
         "°c": "°C", "°f": "°F", "c": "C", "kw": "kW", "hz": "Hz", "%": "%"}
MEASUREMENT_PATTERN = re.compile(
    r"(?<![\w.,-])(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)\s?(mm/s|bar|psi|kpa|mpa|rpm|°c|°f|c|kw|hz|%)(?![A-Za-z0-9/-])",
    re.IGNORECASE,
)


def find_measurements(text: str) -> list[dict]:
    found: dict[str, dict] = {}
    for match in MEASUREMENT_PATTERN.finditer(text):
        if match.group(2) == "c":  # a bare temperature unit must be an upper-case "C" ("5926c" in an id is not)
            continue
        number, unit = match.group(1).replace(",", ""), UNITS[match.group(2).lower()]
        label = f"{number}{unit}" if unit == "%" else f"{number} {unit}"
        found.setdefault(label, {"label": label, "value": float(number), "unit": unit, "start": match.start()})
    return list(found.values())


# ── Failure modes and maintenance actions ───────────────────────────────────────────────────────
FAILURE_PATTERNS = {
    "bearing wear": r"bearing wear|worn bearing|bearing (?:showed|displayed) (?:repeated |uneven )?(?:wear|pitting)",
    "bearing failure": r"bearing (?:failure|damage|seizure)",
    "seal leakage": r"seal leak(?:age)?|(?:minor )?leakage",
    "cavitation": r"cavitation",
    "overheating": r"overheat(?:ing|ed)?|high (?:bearing )?temperature",
    "high vibration": r"(?:high|excessive|elevated) vibration",
    "lubrication contamination": r"(?:lubrication|lubricant|oil) contamination|contaminated (?:lubricant|oil|lubrication)",
    "misalignment": r"misalign(?:ment|ed)",
    "corrosion": r"corrosion|corroded",
    "pressure loss": r"pressure (?:loss|drop)|loss of pressure|pressure fell",
    "motor trip": r"motor trip(?:ped)?",
    "trip": r"tripped",
}
ACTION_PATTERNS = {
    "replaced": r"replaced", "inspected": r"inspected", "lubricated": r"lubricated|re-?greased",
    "aligned": r"(?:re-?)?aligned", "cleaned": r"cleaned", "tightened": r"tightened",
    "overhauled": r"overhauled", "calibrated": r"calibrated", "tested": r"tested", "flushed": r"flushed",
}
_FAILURES = {label: re.compile(rf"\b(?:{p})\b", re.IGNORECASE) for label, p in FAILURE_PATTERNS.items()}
_ACTIONS = {label: re.compile(rf"\b(?:{p})\b", re.IGNORECASE) for label, p in ACTION_PATTERNS.items()}
NEGATION_CUE = re.compile(
    r"\b(?:no|not|never|without|free of|absence of|no signs? of|no evidence of|ruled out)\b[^.;:\n]{0,40}$",
    re.IGNORECASE,
)


def _matches(text: str, patterns: dict[str, re.Pattern]) -> list[tuple[str, int]]:
    """(label, position) of the first non-negated match of each pattern."""
    found = []
    for label, pattern in patterns.items():
        for match in pattern.finditer(text):
            if not NEGATION_CUE.search(text[max(0, match.start() - 60):match.start()]):
                found.append((label, match.start()))
                break
    return found


def find_failures(text: str) -> list[tuple[str, int]]:
    found = _matches(text, _FAILURES)
    if any(label == "motor trip" for label, _ in found):
        found = [(label, pos) for label, pos in found if label != "trip"]
    return found


def find_actions(text: str) -> list[tuple[str, int]]:
    return _matches(text, _ACTIONS)


def extract_entities(text: str, registry: set[str] | None = None) -> dict:
    subject, negated = asset_mentions(text, registry)
    return {
        "asset_tags": subject,
        "negated_asset_tags": negated,
        "dates": find_dates(text)[:50],
        "measurements": [m["label"] for m in find_measurements(text)][:50],
        "failures": sorted(label for label, _ in find_failures(text)),
        "actions": sorted(label for label, _ in find_actions(text)),
    }


# ── Document type ───────────────────────────────────────────────────────────────────────────────
DOCUMENT_TYPES = [
    (r"inspection", "Inspection Report"),
    (r"incident", "Incident Report"),
    (r"\bsop\b|operating procedure|procedure", "Standard Operating Procedure"),
    (r"manual|guide|datasheet", "Equipment Manual"),
    (r"maintenance|work order", "Maintenance Record"),
    (r"reading|telemetry|log sheet", "Operating Readings"),
    (r"safety", "Safety Document"),
]
# Documents that record things that happened (they produce asset events); manuals and procedures don't.
RECORD_TYPES = frozenset({"Inspection Report", "Incident Report", "Maintenance Record", "Operating Readings"})


def classify_document(name: str, text: str) -> str:
    """Filename first, then the title area, then the body: the first match wins."""
    stem = re.sub(r"[_\-.]+", " ", name.lower())
    for source in (stem, text[:300].lower(), text[:2000].lower()):
        for pattern, label in DOCUMENT_TYPES:
            if re.search(pattern, source):
                return label
    return "Industrial Document"
