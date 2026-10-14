// These mirror the JSON the FastAPI server returns today (server/app/schemas/*.py).
// Phase 4 of docs/upgrade-plan.md replaces them with types generated from OpenAPI.

export interface Session {
  token: string;
  username: string;
  displayName: string;
  role: string;
}

export interface DocumentRecord {
  id: string;
  documentId: string;
  filename: string;
  contentType: string;
  size: number;
  status: 'queued' | 'processing' | 'ready' | 'failed';
  chunkCount?: number;
  jobId?: number | null;
  documentType: string;
  assetTags: string;
  summary: string;
  errorMessage?: string | null;
  uploadedBy: string;
  uploadDate: string;
}

export interface RecentQuery {
  id: number;
  question: string;
  mode: string;
  confidence: number;
  createdAt: string;
}

export interface DashboardData {
  documents: number;
  readyDocuments: number;
  assets: number;
  queries: number;
  assetTags: string[];
  aiOnline: boolean;
  llmStatus?: string;
  recentQueries: RecentQuery[];
}

export interface Citation {
  label?: string;   // "S1": the marker used in the answer text
  cited?: boolean;  // the answer cites this source
  docId: string;
  filename: string;
  source: string;
  page?: number;
  documentType: string;
  excerpt: string;
  textSnippet: string;
  relevance: number;
}

export type AnswerFormat = 'paragraph' | 'bullet' | 'table' | 'report' | 'work_order' | 'checklist';
export type EvidenceStrength = 'high' | 'medium' | 'low';

export interface ChatAnswer {
  answer: string;
  mode: 'llm' | 'extractive' | 'assistant' | 'no-evidence' | 'stopped';
  format: string;
  evidenceStrength?: EvidenceStrength | null;
  refused?: boolean;
  notice?: string | null;
  warnings?: string[];
  question?: string;
  model?: string | null;
  confidence: number;
  citations: Citation[];
  assetTag?: string;
  queryId: number;
}

// Events of POST /chat/stream (server/app/services/qa.py)
export interface StreamHandlers {
  onStatus?: (stage: string, position?: number) => void;
  onSources?: (citations: Citation[]) => void;
  onToken?: (text: string) => void;
}

export interface ConversationTurn {
  role: 'user' | 'ai';
  content: string;
  citations?: Citation[];
  id?: number;
  mode?: string;
  strength?: EvidenceStrength | null;
  notice?: string | null;
  warnings?: string[];
  streaming?: boolean;
}

export interface TimelineEvent {
  date: string;
  source: string;
  summary: string;
}

export interface AssetData {
  tag: string;
  sources: string[];
  failures: string[];
  maintenanceActions: string[];
  dates: string[];
  measurements: string[];
  timeline: TimelineEvent[];
  evidenceChunks: number;
}

export interface RcaCitation {
  label?: string;
  cited?: boolean;
  source: string;
  page: number;
  excerpt: string;
  relevance: number;
}

export interface RcaData {
  assetTag: string;
  observedProblem: string;
  probableCauses: string[];
  recordedActions: string[];
  measurements: string[];
  eventDates: string[];
  recommendedInvestigation: string[];
  preventiveActions: string[];
  mode?: 'llm' | 'extractive';
  evidenceStrength?: EvidenceStrength | null;
  notice?: string | null;
  warnings?: string[];
  model?: string | null;
  confidence: number;
  disclaimer: string;
  citations: RcaCitation[];
}

export interface AnalyticsData {
  totalChunks: number;
  totalAssets: number;
  topFailureModes: { failure: string; count: number }[];
  topActions: { action: string; count: number }[];
  assetsRankedByRisk: { assetTag: string; failureEvents: number; topFailure: string | null; documentCount: number }[];
}
