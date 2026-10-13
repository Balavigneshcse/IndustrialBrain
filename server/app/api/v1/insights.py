"""Asset 360, RCA briefs, analytics and the dashboard summary."""
from collections import Counter, defaultdict

from fastapi import APIRouter, HTTPException, Path, Request, Response
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import func, select

from ...db.models import Asset, Document, QueryLog
from ...schemas.common import ERROR_RESPONSES, Problem
from ...schemas.insights import (ActionCount, AnalyticsOut, AssetEventOut, AssetOut, AssetRisk, DashboardOut,
                                 FailureCount, RcaOut, RecentQuery, TimelineEvent)
from ...services import audit, store
from ...services.answers import generate_rca
from ...services.rca_docx import build_rca_docx
from ..deps import CurrentUser, EngineerUser, SessionDep

router = APIRouter(tags=["insights"], responses={401: ERROR_RESPONSES[401]})
AssetTag = Path(min_length=1, max_length=32, description="Equipment tag, e.g. P-101 (exact match)")


KIND_ORDER = {"failure": 0, "action": 1, "measurement": 2, "reading": 3}


@router.get("/assets/{tag}", response_model=AssetOut, responses={404: {"model": Problem}})
async def get_asset(session: SessionDep, _: CurrentUser, tag: str = AssetTag) -> AssetOut:
    """Asset 360: registry details, evidence sources and a chronological event timeline."""
    tag = tag.strip().upper()
    evidence = await store.asset_evidence(session, tag)
    events = await store.asset_events(session, tag)
    asset = (await session.execute(select(Asset).where(Asset.tag == tag))).scalar_one_or_none()
    if not evidence and not events:
        raise HTTPException(404, f"No indexed evidence found for {tag}")

    by_kind: dict[str, set[str]] = defaultdict(set)
    grouped: dict[tuple[str, str], dict[str, list[str]]] = {}
    for event, source in events:
        by_kind[event.kind].add(event.label)
        if event.event_date is not None:
            labels = grouped.setdefault((event.event_date.isoformat(), source), defaultdict(list))
            if event.label not in labels[event.kind]:
                labels[event.kind].append(event.label)
    timeline = [
        TimelineEvent(date=day, source=source, summary=" · ".join(
            ", ".join(labels[kind]) for kind in sorted(labels, key=KIND_ORDER.get)))
        for (day, source), labels in sorted(grouped.items())
    ]
    return AssetOut(
        tag=tag, name=asset.name if asset else None, assetClass=asset.asset_class if asset else None,
        location=asset.location if asset else None, criticality=asset.criticality if asset else None,
        inRegistry=asset is not None,
        sources=sorted({item["metadata"]["source"] for item in evidence} | {source for _, source in events}),
        failures=sorted(by_kind["failure"]), maintenanceActions=sorted(by_kind["action"]),
        dates=sorted({e.event_date.isoformat() for e, _ in events if e.event_date}),
        measurements=sorted(by_kind["measurement"]),
        timeline=timeline,
        events=[AssetEventOut(date=e.event_date.isoformat() if e.event_date else None, kind=e.kind, label=e.label,
                              value=e.value, unit=e.unit, detail=e.detail, source=source) for e, source in events],
        evidenceChunks=len(evidence),
    )


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
    """Counts are distinct events (asset, date, label) from record documents, not text mentions."""
    failures: Counter = Counter()
    actions: Counter = Counter()
    asset_failures: dict[str, Counter] = defaultdict(Counter)
    asset_documents: dict[str, set] = defaultdict(set)
    seen: set[tuple] = set()
    for tag, kind, label, event_date, document_id in await store.all_events(session):
        asset_documents[tag].add(document_id)
        key = (tag, kind, label, event_date)
        if key in seen:
            continue
        seen.add(key)
        if kind == "failure":
            failures[label] += 1
            asset_failures[tag][label] += 1
        elif kind == "action":
            actions[label] += 1
    ranked = sorted(
        (AssetRisk(assetTag=tag, failureEvents=sum(counts.values()),
                   topFailure=counts.most_common(1)[0][0] if counts else None,
                   documentCount=len(asset_documents[tag]))
         for tag, counts in asset_failures.items()),
        key=lambda a: (-a.failureEvents, a.assetTag),
    )
    tags = await store.known_asset_tags(session) | set((await session.execute(select(Asset.tag))).scalars())
    return AnalyticsOut(
        totalChunks=await store.chunk_count(session), totalAssets=len(tags),
        topFailureModes=[FailureCount(failure=f, count=c) for f, c in failures.most_common(10)],
        topActions=[ActionCount(action=a, count=c) for a, c in actions.most_common(10)],
        assetsRankedByRisk=ranked[:20],
    )


@router.get("/dashboard", response_model=DashboardOut)
async def dashboard(session: SessionDep, _: CurrentUser) -> DashboardOut:
    documents = (await session.execute(select(func.count(Document.id)))).scalar_one()
    ready = (await session.execute(select(func.count(Document.id)).where(Document.status == "ready"))).scalar_one()
    queries = (await session.execute(select(func.count(QueryLog.id)))).scalar_one()
    tags = sorted(await store.known_asset_tags(session) | set((await session.execute(select(Asset.tag))).scalars()))
    recent = (await session.execute(select(QueryLog).order_by(QueryLog.id.desc()).limit(5))).scalars()
    return DashboardOut(
        documents=documents, readyDocuments=ready, assets=len(tags), queries=queries, assetTags=tags,
        aiOnline=True,  # the evidence index lives in the database this request just used
        recentQueries=[RecentQuery(id=q.id, question=q.question, mode=q.mode, confidence=q.confidence,
                                   createdAt=q.created_at) for q in recent],
    )
