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
  uploadedAt: string
}

export type Citation = {
  source: string
  page: number
  excerpt: string
  relevance?: number
  documentType?: string
}

export type ChatAnswer = {
  answer: string
  mode: string
  confidence: number
  citations: Citation[]
  assetTag: string
}

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

