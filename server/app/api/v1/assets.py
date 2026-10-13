"""Asset registry: list equipment (registered and discovered in documents) and import the master list."""
from collections import defaultdict

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from sqlalchemy import select

from ...db.models import Asset
from ...schemas.common import ERROR_RESPONSES, Problem
from ...schemas.insights import AssetImportResult, AssetSummary
from ...services import audit, store
from ...services.registry import import_csv
from ..deps import AdminUser, CurrentUser, SessionDep

router = APIRouter(prefix="/assets", tags=["assets"], responses={401: ERROR_RESPONSES[401]})


@router.get("", response_model=list[AssetSummary])
async def list_assets(session: SessionDep, _: CurrentUser) -> list[AssetSummary]:
    """Registered assets plus tags found in documents, with failure-event counts and last event date."""
    registry = {a.tag: a for a in (await session.execute(select(Asset))).scalars()}
    discovered = await store.known_asset_tags(session)
    failures: dict[str, set] = defaultdict(set)
    documents: dict[str, set] = defaultdict(set)
    last_date: dict[str, str] = {}
    for tag, kind, label, event_date, document_id in await store.all_events(session):
        documents[tag].add(document_id)
        if kind == "failure":
            failures[tag].add((event_date, label))
        if event_date is not None and event_date.isoformat() > last_date.get(tag, ""):
            last_date[tag] = event_date.isoformat()
    summaries = []
    for tag in sorted(set(registry) | discovered):
        asset = registry.get(tag)
        summaries.append(AssetSummary(
            tag=tag, name=asset.name if asset else "", assetClass=asset.asset_class if asset else "",
            location=asset.location if asset else "", criticality=asset.criticality if asset else "",
            inRegistry=asset is not None, documentCount=len(documents[tag]), failureEvents=len(failures[tag]),
            lastEventDate=last_date.get(tag),
        ))
    return summaries


@router.post("/import", response_model=AssetImportResult, responses={
    403: ERROR_RESPONSES[403], 422: {"model": Problem, "description": "Not a valid registry CSV"}})
async def import_assets(request: Request, session: SessionDep, admin: AdminUser,
                        file: UploadFile = File(...)) -> AssetImportResult:
    """Upsert the equipment master list from CSV (header: tag,name,class,location,criticality,
    manufacturer,notes). Once a registry exists, only registered tags are recognised in documents."""
    content = await file.read(5 * 1024 * 1024 + 1)
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(413, "Registry CSV larger than 5 MB")
    try:
        created, updated, skipped = await import_csv(session, content)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    audit.record(session, "assets_imported", user=admin, request=request,
                 detail={"created": created, "updated": updated, "skipped": len(skipped)})
    await session.commit()
    return AssetImportResult(created=created, updated=updated, skipped=skipped,
                             hint="Re-index documents so tag recognition uses the registry "
                                  "(POST /documents/{id}/reindex or `python -m server.app.cli reindex`).")
