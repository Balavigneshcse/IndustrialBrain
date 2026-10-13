"""Asset registry: import from the plant's equipment master list (CSV)."""
import csv
import io

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import Asset
from .entities import ASSET_PATTERN, normalize_tag

COLUMNS = {"tag", "name", "class", "location", "criticality", "manufacturer", "notes"}
CRITICALITY = {"a": "high", "b": "medium", "c": "low", "high": "high", "medium": "medium", "low": "low", "": ""}


async def import_csv(session: AsyncSession, content: bytes) -> tuple[int, int, list[str]]:
    """Upsert assets from CSV with a header row (tag required; name, class, location, criticality
    (A/B/C or high/medium/low), manufacturer, notes optional). Returns (created, updated, skipped)."""
    text = content.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    header = {h.strip().lower() for h in (reader.fieldnames or [])}
    if "tag" not in header:
        raise ValueError("The CSV needs a header row with at least a 'tag' column")
    unknown = header - COLUMNS
    if unknown:
        raise ValueError(f"Unknown column(s): {', '.join(sorted(unknown))}. Allowed: {', '.join(sorted(COLUMNS))}")

    existing = {a.tag: a for a in (await session.execute(select(Asset))).scalars()}
    created = updated = 0
    skipped: list[str] = []
    for number, raw in enumerate(reader, start=2):
        row = {(k or "").strip().lower(): (v or "").strip() for k, v in raw.items()}
        tag = normalize_tag(row.get("tag", ""))
        criticality = CRITICALITY.get(row.get("criticality", "").lower())
        if not ASSET_PATTERN.fullmatch(tag) or criticality is None:
            skipped.append(f"line {number}: invalid tag or criticality ({row.get('tag', '')!r})")
            continue
        values = {"name": row.get("name", "")[:200], "asset_class": row.get("class", "")[:64],
                  "location": row.get("location", "")[:200], "criticality": criticality,
                  "manufacturer": row.get("manufacturer", "")[:128], "notes": row.get("notes", "")}
        asset = existing.get(tag)
        if asset is None:
            asset = Asset(tag=tag, **values)
            session.add(asset)
            existing[tag] = asset
            created += 1
        else:
            for key, value in values.items():
                setattr(asset, key, value)
            updated += 1
    return created, updated, skipped
