export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  fact?: string
}

export interface ChatRequest {
  message: string
  history: ChatMessage[]
}

export interface ContainerOverview {
  total: number
  running: number
  stopped: number
  severity_breakdown: Record<string, number>
  top_risky_containers: {
    name: string
    state: string
    critical: number
    high: number
  }[]
}

export interface ImageVulnerabilities {
  total_images: number
  severity_totals: {
    critical: number
    high: number
    medium: number
    low: number
  }
  top_vulnerable_images: {
    name?: string
    sha?: string
    tag?: string
    critical: number
    high: number
    medium: number
  }[]
}

export interface Registry {
  name: string
  type?: string
  state?: string
  total_images?: number
  last_scanned?: string
}

export interface RegistryHealth {
  total: number
  registries: Registry[]
}

export interface K8sCluster {
  name?: string
  uid?: string
  version?: string
  node_count?: number
  sensor_status?: string
}

export interface K8sPosture {
  total_clusters: number
  posture_summary?: {
    passed?: number
    failed?: number
    PASS?: number
    FAIL?: number
  }
  clusters: K8sCluster[]
}

export interface ThreatIntelCategory {
  key: string
  label: string
  description: string
  group: 'exploited' | 'exploitability' | 'impact'
  count: number | null
  capped: boolean
  error: string | null
}

export interface ThreatIntelOverview {
  categories: ThreatIntelCategory[]
  cached_for_seconds?: number
}

export interface ThreatIntelVuln {
  qid: number | null
  title: string
  severity: number
  cves: string[]
  patch_available: boolean | null
  first_found: string | null
  images: number | null
  containers: number | null
}

export interface ThreatIntelDetail {
  key: string
  label: string
  filter: string
  total: number
  capped: boolean
  items: ThreatIntelVuln[]
}

export type DashboardEndpoint =
  | 'threat-intel'
  | 'containers/overview'
  | 'images/vulnerabilities'
  | 'registry/health'
  | 'k8s/posture'
