"""Checks on generated text against the sources it was given, and the evidence-strength label.

- Every [S#] must name a source that was provided; invalid ones are removed from the answer.
- Every number in the answer must appear in the sources (as written, or as the same value).
- Factual sentences without a citation are reported as unsupported.
Statements about missing information ("the sources do not record ...") need no citation.
"""
import re
from dataclasses import dataclass, field

CITATION = re.compile(r"\[\s*S\d+(?:\s*[,;]\s*S?\d+)*\s*\]", re.IGNORECASE)
SPACED_CITATION = re.compile(r"([ \t]*)(" + CITATION.pattern + ")", re.IGNORECASE)
CITED_NUMBER = re.compile(r"\d+")
NUMBER = re.compile(r"(?<![\d.,])\d+(?:[.,]\d+)*")
LIST_MARKER = re.compile(r"^\s*(?:[-*+] \[[ xX]\]|[-*+]|\d+[.)])\s+")  # checkbox items first
SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z\[(\"'*])")
GAP_STATEMENT = re.compile(
    r"insufficient evidence|not covered by the sources|\bno (?:information|data|record|mention)\b|"
    r"\bno (?:stated|recorded|documented|reported)\b|\bnot (?:stated|"
    r"mentioned|recorded|covered|specified|provided|given|documented|included|available|established)\b|\bdo(?:es)? not "
    r"(?:state|mention|record|cover|specify|provide|include|say|contain|give|document|support|establish)\b|"
    r"\bnone of the sources\b",
    re.IGNORECASE)
REFUSAL = re.compile(r"^\W*insufficient evidence\b", re.IGNORECASE)
# "Insufficient evidence:" starting a later line or sentence of an answer (not a refusal: it names a gap)
TRAILING_REFUSAL = re.compile(r"(?m)(^|[.!?]\s+)[*_\s]*insufficient evidence\s*:", re.IGNORECASE)
TRAILING_CITATIONS = re.compile(r"(?<=[A-Za-z0-9)%°\]])([.!?])((?:\s*\[S\d+\])+)")
SEPARATOR_ROW = re.compile(r"\|?[\s:\-|]*-[\s:\-|]*")
MIN_CLAIM_WORDS = 4


@dataclass
class Grounding:
    cited: list[int] = field(default_factory=list)              # source numbers cited (1-based, in order)
    invalidCitations: list[str] = field(default_factory=list)   # [S#] that name no provided source
    ungroundedNumbers: list[str] = field(default_factory=list)  # numbers found in no source
    miscitedNumbers: list[str] = field(default_factory=list)    # in some source, but not the cited ones
    unsupportedSentences: list[str] = field(default_factory=list)
    claims: int = 0

    def as_dict(self) -> dict:
        return {"citedSources": [f"S{n}" for n in self.cited], "invalidCitations": self.invalidCitations,
                "ungroundedNumbers": self.ungroundedNumbers, "miscitedNumbers": self.miscitedNumbers,
                "unsupportedSentences": self.unsupportedSentences, "claims": self.claims}

    def warnings(self) -> list[str]:
        out = []
        if self.invalidCitations:
            out.append(f"Removed citations to sources that were not provided: {', '.join(self.invalidCitations)}.")
        if self.ungroundedNumbers:
            out.append("Numbers not found in any source (verify before use): " + ", ".join(self.ungroundedNumbers) + ".")
        if self.miscitedNumbers:
            out.append("Numbers found in a different source than the one cited: " + ", ".join(self.miscitedNumbers) + ".")
        if self.unsupportedSentences:
            out.append(f"{len(self.unsupportedSentences)} statement(s) without a citation.")
        return out


def is_refusal(answer: str) -> bool:
    return bool(REFUSAL.match(answer.strip()))


def _numbers_in(text: str) -> set[str]:
    return {m.group(0) for m in NUMBER.finditer(text)}


def _value(token: str) -> float | None:
    plain = token.replace(",", "") if re.fullmatch(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?", token) else token.replace(",", ".")
    try:
        return float(plain)
    except ValueError:
        return None


def _found(token: str, texts: list[str], values: list[set[float]]) -> bool:
    pattern = re.compile(rf"(?<![\d.]){re.escape(token)}(?![\d])")
    if any(pattern.search(text) for text in texts):
        return True
    value = _value(token)
    return value is not None and any(value in v for v in values)


def _units(answer: str) -> list[tuple[str, str]]:
    """Answer split into checkable statements: (line, statement) for lines (bullets, table rows), then
    sentences within each line."""
    units = []
    lines = [line.strip() for line in answer.splitlines()]
    for index, line in enumerate(lines):
        if not line or line.startswith("#") or SEPARATOR_ROW.fullmatch(line):
            continue
        if line.startswith("|"):
            following = lines[index + 1] if index + 1 < len(lines) else ""
            if not SEPARATOR_ROW.fullmatch(following):  # the row above a |---| line is the header
                units.append((line, line))  # one table row is one statement
            continue
        line = LIST_MARKER.sub("", line)
        units.extend((line, part) for part in SENTENCE_END.split(line) if part.strip())
    return units


def normalize_citations(answer: str, source_count: int) -> tuple[str, list[str]]:
    """Rewrites [S1, S2] as [S1][S2] and drops citations to sources that were not provided."""
    invalid: list[str] = []

    def fix(match: re.Match) -> str:
        kept = []
        for number in (int(n) for n in CITED_NUMBER.findall(match.group(2))):
            if 1 <= number <= source_count:
                kept.append(f"[S{number}]")
            elif f"S{number}" not in invalid:
                invalid.append(f"S{number}")
        return match.group(1) + "".join(kept) if kept else ""  # a dropped citation takes its space with it

    text = SPACED_CITATION.sub(fix, answer)
    # "found. [S1] Next" -> "found [S1]. Next": a citation belongs to the sentence before it.
    text = TRAILING_CITATIONS.sub(lambda m: " " + "".join(m.group(2).split()) + m.group(1), text)
    return text, invalid


def check(answer: str, sources: list[str], advice: frozenset[str] = frozenset()) -> Grounding:
    """`answer` must already be normalized (normalize_citations). Lines in `advice` are recommendations
    rather than facts (RCA next steps, work-order tasks): their numbers are checked, but they need no
    citation."""
    result = Grounding()
    values = [{v for v in (_value(t) for t in _numbers_in(text)) if v is not None} for text in sources]
    for line, unit in _units(answer):
        cited = [int(n) for n in re.findall(r"\[S(\d+)\]", unit) if 1 <= int(n) <= len(sources)]
        for n in cited:
            if n not in result.cited:
                result.cited.append(n)
        text = CITATION.sub(" ", unit)
        words = re.findall(r"[A-Za-z0-9][\w\-./°%]*", text)
        if len(words) < MIN_CLAIM_WORDS and not _numbers_in(text):
            continue
        if GAP_STATEMENT.search(text) and not cited:
            continue
        result.claims += 1
        if not cited and line not in advice:
            result.unsupportedSentences.append(" ".join(text.split())[:200])
        for token in sorted(_numbers_in(text), key=text.find):
            if _found(token, sources, values):
                if cited and not _found(token, [sources[n - 1] for n in cited], [values[n - 1] for n in cited]):
                    if token not in result.miscitedNumbers:
                        result.miscitedNumbers.append(token)
            elif token not in result.ungroundedNumbers:
                result.ungroundedNumbers.append(token)
    return result


def evidence_strength(scores: list[float], grounding: Grounding | None, refused: bool) -> str:
    """High / Medium / Low from the reranker relevance of the cited evidence and the checks above.
    Thresholds are provisional; Phase 7 calibrates them on the eval set."""
    if refused or not scores:
        return "low"
    if grounding is None:  # extractive answer: verbatim evidence, judged by retrieval relevance alone
        best = scores[0]
        return "medium" if best >= 0.05 else "low"
    if grounding.invalidCitations or grounding.ungroundedNumbers or not grounding.cited:
        return "low"
    best = max(scores[n - 1] for n in grounding.cited)
    if best >= 0.5 and not grounding.unsupportedSentences and not grounding.miscitedNumbers:
        return "high"
    return "medium" if best >= 0.05 else "low"
