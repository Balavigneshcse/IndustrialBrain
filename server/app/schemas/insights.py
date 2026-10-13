"""Asset 360, RCA, analytics and dashboard responses."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class TimelineEvent(BaseModel):
    date: str
    source: str
    summary: str


class AssetEventOut(BaseModel):
    date: str | None  # ISO date; null when the record gives none
    kind: Literal["failure", "action", "measurement", "reading"]
    label: str
    value: float | None
    unit: str | None
    detail: str
    source: str


class AssetOut(BaseModel):
    tag: str
    name: str | None = None
    assetClass: str | None = None
    location: str | None = None
    criticality: str | None = None
    inRegistry: bool = False
    sources: list[str]
    failures: list[str]
    maintenanceActions: list[str]
    dates: list[str]
    measurements: list[str]
    timeline: list[TimelineEvent]  # dated events grouped per date and document, oldest first
    events: list[AssetEventOut] = []
    evidenceChunks: int


class AssetSummary(BaseModel):
    tag: str
    name: str
    assetClass: str
    location: str
    criticality: str
    inRegistry: bool
    documentCount: int
    failureEvents: int
    lastEventDate: str | None


class AssetImportResult(BaseModel):
    created: int
    updated: int
    skipped: list[str]
    hint: str


class RcaCitation(BaseModel):
    source: str
    page: int
    excerpt: str
    relevance: float


class RcaOut(BaseModel):
    assetTag: str
    observedProblem: str
    probableCauses: list[str]
    recordedActions: list[str]
    measurements: list[str]
    eventDates: list[str]
    recommendedInvestigation: list[str]
    preventiveActions: list[str]
    confidence: float
    disclaimer: str
    citations: list[RcaCitation]


class FailureCount(BaseModel):
    failure: str
    count: int


class ActionCount(BaseModel):
    action: str
    count: int


class AssetRisk(BaseModel):
    assetTag: str
    failureEvents: int
    topFailure: str | None
    documentCount: int


class AnalyticsOut(BaseModel):
    totalChunks: int
    totalAssets: int
    topFailureModes: list[FailureCount]
    topActions: list[ActionCount]
    assetsRankedByRisk: list[AssetRisk]


class RecentQuery(BaseModel):
    id: int
    question: str
    mode: str
    confidence: float
    createdAt: datetime


class DashboardOut(BaseModel):
    documents: int
    readyDocuments: int
    assets: int
    queries: int
    assetTags: list[str]
    aiOnline: bool
    recentQueries: list[RecentQuery]
