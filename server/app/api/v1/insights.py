"""Asset 360, RCA briefs, analytics and the dashboard summary."""
from collections import Counter

from fastapi import APIRouter, HTTPException, Path, Request, Response
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import func, select

from ...db.models import Document, QueryLog
from ...schemas.common import ERROR_RESPONSES, Problem
from ...schemas.insights import (ActionCount, AnalyticsOut, AssetOut, AssetRisk, DashboardOut, FailureCount,
                                 RcaOut, RecentQuery, TimelineEvent)
from ...services import audit, store
from ...services.answers import generate_rca
from ...services.rca_docx import build_rca_docx
from ..deps import CurrentUser, EngineerUser, SessionDep

router = APIRouter(tags=["insights"], responses={401: ERROR_RESPONSES[401]})
AssetTag = Path(min_length=1, max_length=32, description="Equipment tag, e.g. P-101 (exact match)")


def _split(value: str) -> list[str]:
    return [v for v in value.split(",") if v]


@router.get("/assets/{tag}", response_model=AssetOut, responses={404: {"model": Problem}})
async def get_asset(session: SessionDep, _: CurrentUser, tag: str = AssetTag) -> AssetOut:
    evidence = await store.asset_evidence(session, tag)
    if not evidence:
        raise HTTPException(404, f"No indexed evidence found for {tag.upper()}")
    sources, failures, actions, dates, measurements = set(), set(), set(), set(), set()
    events = []
    for item in evidence:
        meta = item["metadata"]
        sources.add(meta["source"])
        failures.update(_split(meta["failures"]))
        actions.update(_split(meta["actions"]))
        dates.update(_split(meta["dates"]))
        measurements.update(_split(meta["measurements"]))
        if meta["dates"]:
            events.append(TimelineEvent(date=meta["dates"].split(",")[0], source=meta["source"], summary=item["text"][:220]))
    return AssetOut(tag=tag.upper(), sources=sorted(sources), failures=sorted(failures),
                    maintenanceActions=sorted(actions), dates=sorted(dates), measurements=sorted(measurements),
                    timeline=events[:12], evidenceChunks=len(evidence))


@router.post("/rca/{tag}", response_model=RcaOut, responses={403: ERROR_RESPONSES[403]})
async def create_rca(session: SessionDep, _: EngineerUser, tag: str = AssetTag) -> RcaOut:
    evidence = await store.asset_evidence(session, tag)
    return RcaOut(**await run_in_threadpool(generate_rca, tag, evidence))


@router.get("/rca/export/{tag}", response_class=Response, responses={
    200: {"content": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document": {}},
          "description": "RCA brief as a Word document"},
    403: ERROR_RESPONSES[403]})
async def export_rca(request: Request, session: SessionDep, user: EngineerUser, tag: str = AssetTag) -> Response:
    evidence = await store.asset_evidence(session, tag)
    rca = await run_in_threadpool(generate_rca, tag, evidence)
    content = await run_in_threadpool(build_rca_docx, rca)
    audit.record(session, "rca_exported", user=user, request=request, target_type="asset", target_id=rca["assetTag"])
    await session.commit()
    return Response(content, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    headers={"Content-Disposition": f'attachment; filename="RCA-{rca["assetTag"]}.docx"'})


@router.get("/analytics", response_model=AnalyticsOut)
async def analytics(session: SessionDep, _: CurrentUser) -> AnalyticsOut:
    """Counts are failure/action term mentions across indexed chunks, not distinct events (Phase 2)."""
    failure_counter: Counter = Counter()
    action_counter: Counter = Counter()
    asset_failures: dict[str, Counter] = {}
    asset_docs: dict[str, set] = {}
    rows = await store.chunk_entities(session)
    for tags, entities, document_id in rows:
        failures = entities.get("failures", [])
        failure_counter.update(failures)
        action_counter.update(entities.get("actions", []))
        for tag in tags:
            asset_failures.setdefault(tag, Counter()).update(failures)
            asset_docs.setdefault(tag, set()).add(document_id)
    ranked = sorted(
        (AssetRisk(assetTag=tag, failureEvents=sum(counts.values()),
                   topFailure=counts.most_common(1)[0][0] if counts else None,
                   documentCount=len(asset_docs[tag]))
         for tag, counts in asset_failures.items()),
        key=lambda a: (-a.failureEvents, a.assetTag),
    )
    return AnalyticsOut(
        totalChunks=len(rows), totalAssets=len(asset_failures),
        topFailureModes=[FailureCount(failure=f, count=c) for f, c in failure_counter.most_common(10)],
        topActions=[ActionCount(action=a, count=c) for a, c in action_counter.most_common(10)],
        assetsRankedByRisk=ranked[:20],
    )


@router.get("/dashboard", response_model=DashboardOut)
async def dashboard(session: SessionDep, _: CurrentUser) -> DashboardOut:
    documents = (await session.execute(select(func.count(Document.id)))).scalar_one()
    ready = (await session.execute(select(func.count(Document.id)).where(Document.status == "ready"))).scalar_one()
    queries = (await session.execute(select(func.count(QueryLog.id)))).scalar_one()
    tags = sorted(await store.known_asset_tags(session))
    recent = (await session.execute(select(QueryLog).order_by(QueryLog.id.desc()).limit(5))).scalars()
    return DashboardOut(
        documents=documents, readyDocuments=ready, assets=len(tags), queries=queries, assetTags=tags,
        aiOnline=True,  # the evidence index lives in the database this request just used
        recentQueries=[RecentQuery(id=q.id, question=q.question, mode=q.mode, confidence=q.confidence,
                                   createdAt=q.created_at) for q in recent],
    )
