export type HealthData = {
  status: string
  service: string
  aiService: 'UP' | 'DOWN'
  supportedFormats: string[]
}

export type DashboardData = {
  documents: number
  readyDocuments: number
  assets: number
  queries: number
  assetTags: string[]
  aiOnline: boolean
  recentQueries: { id: number; question: string; mode: string; confidence: number; createdAt: string }[]
}

export type DocumentRecord = {
  id: number
  originalName: string
  contentType: string
  sizeBytes: number
  status: string
  documentType: string
  assetTags: string
  summary: string
  errorMessage?: string
  uploadedBy?: string
  uploadedAt: string
}

export type Citation = {
  source: string
  page: number
  excerpt: string
  relevance?: number
  documentType?: string
}

export type AnswerFormat = 'quick_answer' | 'work_order' | 'checklist' | 'table' | 'report'
export type ExportFormat = 'docx' | 'pdf' | 'csv'

export type ChatAnswer = {
  answer: string
  mode: string
  format: AnswerFormat
  confidence: number
  citations: Citation[]
  assetTag: string
  queryId?: number
  feedback?: 1 | -1
}

export type ConversationTurn = { question: string; answer: string }

export type AssetData = {
  tag: string
  sources: string[]
  failures: string[]
  maintenanceActions: string[]
  dates: string[]
  measurements: string[]
  timeline: { date: string; source: string; summary: string }[]
  evidenceChunks: number
}

export type RcaData = {
  assetTag: string
  observedProblem: string
  probableCauses: string[]
  recordedActions: string[]
  measurements: string[]
  eventDates: string[]
  recommendedInvestigation: string[]
  preventiveActions: string[]
  confidence: number
  disclaimer: string
  citations: Citation[]
}

export type AuditLogEntry = {
  id: number
  actor: string
  action: string
  targetType?: string
  targetId?: string
  detail?: string
  createdAt: string
}

export type AssetRegistryEntry = {
  id: number
  tag: string
  name?: string
  location?: string
  criticality?: string
  manufacturer?: string
  installDate?: string
  notes?: string
  createdAt: string
  updatedAt: string
}

export type AnalyticsData = {
  totalChunks: number
  totalAssets: number
  topFailureModes: { failure: string; count: number }[]
  topActions: { action: string; count: number }[]
  assetsRankedByRisk: { assetTag: string; failureEvents: number; topFailure: string | null; documentCount: number }[]
}

