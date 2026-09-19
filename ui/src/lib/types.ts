// TypeScript mirrors of vanguard/core/models.py. Keep field names exact —
// these must match the real Pydantic response shapes, not a guess.

export type Capability =
  | "GPU_INFERENCE"
  | "CUDA"
  | "WINDOWS_BUILD"
  | "LINUX_BUILD"
  | "MACOS_BUILD"
  | "DOCKER"
  | "PYTHON_RUNTIME"
  | "NODE_RUNTIME"
  | "HIGH_MEMORY"
  | "HIGH_CORE_COUNT";

export type NodeLocality = "LOCAL" | "CLOUD" | "UNKNOWN";
export type NodeStatus = "ONLINE" | "STALE" | "OFFLINE" | "UNKNOWN";

export interface VanguardNode {
  schema_version: 1;
  node_id: string;
  hostname: string;
  os_name: string;
  os_version: string;
  architecture: string;
  cpu_model: string;
  cpu_cores_logical: number;
  memory_total_mb: number;
  gpu_model: string | null;
  gpu_vram_mb: number | null;
  capabilities: Capability[];
  locality: NodeLocality;
  status: NodeStatus;
  last_seen: string;
  registered_at: string;
  notes: string;
}

export type ServiceKind =
  | "HTTP_API"
  | "BACKGROUND_WORKER"
  | "DATABASE"
  | "MESH_CONTROLLER"
  | "OTHER";

export interface VanguardService {
  schema_version: 1;
  service_id: string;
  name: string;
  kind: ServiceKind;
  node_id: string | null;
  base_url: string | null;
  health_path: string | null;
  owner: string;
  description: string;
  registered_at: string;
  updated_at: string;
}

export type ReadinessState =
  | "READY"
  | "READY_WITH_WARNING"
  | "DEGRADED"
  | "NOT_READY"
  | "UNKNOWN";

export interface ReadinessEvidence {
  check_id: string;
  passed: boolean;
  detail: string;
}

export interface ReadinessResult {
  schema_version: 1;
  node_id: string;
  profile_id: string;
  state: ReadinessState;
  evidence: ReadinessEvidence[];
  evaluated_at: string;
}

export interface ReadinessOverview {
  profiles: string[];
  recent_results: ReadinessResult[];
}

export type MeshPeerStatus = "CONNECTED" | "DISCONNECTED" | "UNKNOWN";

export interface MeshPeer {
  peer_id: string;
  name: string;
  ip: string | null;
  connected: boolean;
  status: MeshPeerStatus;
  last_seen: string | null;
  os: string | null;
  groups: string[];
}

export interface MeshRoute {
  route_id: string;
  network: string;
  peer_id: string | null;
  enabled: boolean;
  groups: string[];
}

export interface MeshPolicy {
  policy_id: string;
  name: string;
  enabled: boolean;
  description: string;
}

export type MeshConnectionStatus = "CONNECTED" | "NOT_CONNECTED" | "UNKNOWN";

export interface MeshStatus {
  provider: string;
  status: MeshConnectionStatus;
  detail: string;
  checked_at: string;
}

export type IntegrationStatus = "NOT_CONNECTED" | "CONNECTED" | "UNKNOWN";

export interface IntegrationReport {
  integration: string;
  status: IntegrationStatus;
  detail: string;
  checked_at: string;
}

export interface IntegrationsOverview {
  steward: IntegrationReport;
  watchtower: IntegrationReport;
  marshal: IntegrationReport;
  dispatch: IntegrationReport;
}

export type ProcessState = "RUNNING" | "STOPPED" | "STARTING" | "STOPPING" | "FAILED" | "UNKNOWN";

export interface ManagedProcessStatus {
  schema_version: 1;
  service_id: string;
  name: string;
  working_dir: string;
  command: string[];
  health_url: string | null;
  state: ProcessState;
  pid: number | null;
  started_at: string | null;
  last_restart_at: string | null;
  last_exit_code: number | null;
  last_checked: string | null;
  healthy: boolean | null;
  health_detail: string;
  log_path: string | null;
}

export interface ProcessLogsResponse {
  service_id: string;
  lines: string[];
}

export interface HealthResponse {
  status: string;
  mode: string;
  environment: string;
}

export type JobState = "QUEUED" | "RUNNING" | "COMPLETED" | "FAILED" | "CANCELED" | "RETRYING";

export interface Job {
  schema_version: 1;
  job_id: string;
  job_type: string;
  params: Record<string, unknown>;
  state: JobState;
  progress: string;
  result: Record<string, unknown> | null;
  error: string | null;
  retries: number;
  max_retries: number;
  requested_by: string;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}
