/**
 * Types mirroring the FastAPI response models.
 *
 * These are hand-maintained rather than generated. Keep them in step with
 * `apps/api/app/routers/*.py` — when a project adds an endpoint, its response
 * type belongs here so the web app never re-declares an API shape locally.
 */

/** Status of one dependency, from `GET /health/ready`. */
export type CheckStatus = "ok" | "not_configured" | "unavailable";

/** Overall readiness. `degraded` means an *optional* dependency is missing. */
export type ReadinessStatus = "ok" | "degraded" | "unhealthy";

export interface HealthCheck {
  name: string;
  status: CheckStatus;
  detail: string;
}

export interface ReadinessResponse {
  status: ReadinessStatus;
  checked_at: string;
  checks: HealthCheck[];
}

/**
 * `GET /api/system` — non-secret configuration.
 *
 * This is what lets the UI label the active mode at all times, which
 * CLAUDE.md Section 3b requires ("Never blur the two").
 */
export interface SystemInfo {
  app_name: string;
  app_env: string;
  demo_mode: boolean;
  allow_bring_your_own_key: boolean;
  ai_provider: string;
  auth_mode: string;
  database_configured: boolean;
  demo_recordings: number;
  export_formats: string[];
  priced_models: string[];
}

/** The error envelope every failed API call returns (see `app/errors.py`). */
export interface ApiError {
  code: string;
  message: string;
  fields?: { field: string; problem: string }[];
}

/** Shared urgency scale, mirroring `aiops_ai.types.Priority`. */
export type Priority = "low" | "medium" | "high" | "urgent";

/** Which build phase a project belongs to, per CLAUDE.md Section 8. */
export type ProjectStatus = "planned" | "in_progress" | "shipped";

export interface ProjectSummary {
  slug: string;
  name: string;
  /** The JD requirement this project proves (CLAUDE.md Section 26). */
  jdRequirement: string;
  description: string;
  status: ProjectStatus;
  /** Build order position from CLAUDE.md Section 8. */
  phase: number;
}

// ---------------------------------------------------------------------------
// Project 1 — AI SOP Generator
// ---------------------------------------------------------------------------

export type SopStatus = "draft" | "active" | "under_review" | "retired";

export interface ProcedureStep {
  number: number;
  instruction: string;
  responsible: string;
  expected_result: string;
}

export interface DecisionPoint {
  at_step: number | null;
  question: string;
  if_yes: string;
  if_no: string;
}

export interface SopException {
  situation: string;
  action: string;
}

export interface EscalationRule {
  trigger: string;
  escalate_to: string;
  within: string;
}

export interface Kpi {
  name: string;
  target: string;
  how_measured: string;
}

export interface Risk {
  description: string;
  severity: string;
  mitigation: string;
}

/** The body of an SOP — the 13 sections CLAUDE.md Section 9 requires. */
export interface SopContent {
  title: string;
  purpose: string;
  scope: string;
  prerequisites: string[];
  roles: string[];
  procedure: ProcedureStep[];
  decision_points: DecisionPoint[];
  exceptions: SopException[];
  escalation_rules: EscalationRule[];
  checklist: string[];
  kpis: Kpi[];
  risks: Risk[];
  improvement_suggestions: string[];
}

export interface SopMetadata {
  owner: string;
  department: string;
  status: SopStatus;
  effective_date: string | null;
  review_date: string | null;
}

/** Cost metadata attached to every AI call (CLAUDE.md Section 3d). */
export interface UsageInfo {
  model: string;
  provider: string;
  duration_ms: number;
  input_tokens: number;
  output_tokens: number;
  estimated_cost_usd: number | null;
  from_demo_cache: boolean;
}

export interface SopSummary {
  id: string;
  title: string;
  owner: string;
  department: string;
  status: SopStatus;
  current_version: number;
  effective_date: string | null;
  review_date: string | null;
  updated_at: string;
}

export interface VersionSummary {
  version: number;
  change_note: string;
  created_by: string;
  created_at: string;
  ai_generated: boolean;
  ai_model: string | null;
  searchable: boolean;
}

export interface SopDetail {
  id: string;
  metadata: SopMetadata;
  content: SopContent;
  version: number;
  versions: VersionSummary[];
}

export type ChangeKind = "unchanged" | "added" | "removed" | "modified";

export interface LineChange {
  kind: ChangeKind;
  text: string;
}

export interface FieldDiff {
  field: string;
  label: string;
  kind: ChangeKind;
  lines: LineChange[];
}

export interface SopDiff {
  from_version: number;
  to_version: number;
  fields: FieldDiff[];
}

export interface Citation {
  sop_id: string;
  title: string;
  version: number;
  similarity: number;
}

export interface AnswerResult {
  answered: boolean;
  answer: string;
  citations: Citation[];
  reasoning_summary: string;
}

export interface AskResponse {
  result: AnswerResult;
  usage: UsageInfo;
  skipped_ai: boolean;
}

export interface GenerateResponse {
  content: SopContent;
  usage: UsageInfo;
}

/* ------------------------------------------------------------------ *
 * Project 3 — AI Operations Dashboard (`/api/dashboard`)
 *
 * The split between `Analysis` and `InsightReport` is deliberate and load
 * bearing: `Analysis` is measured, `InsightReport` is interpreted. They arrive
 * from different endpoints and must never be merged into one object, because
 * the UI's job is to keep a reader able to tell them apart.
 * ------------------------------------------------------------------ */

export type ColumnKind =
  | "numeric"
  | "date"
  | "categorical"
  | "identifier"
  | "text"
  | "boolean"
  | "empty";

export type TrendDirection = "rising" | "falling" | "flat";

export interface ColumnProfile {
  name: string;
  kind: ColumnKind;
  dtype: string;
  non_null_count: number;
  null_count: number;
  distinct_count: number;
  minimum: number | null;
  maximum: number | null;
  mean: number | null;
  top_values: string[];
}

export interface Trend {
  column: string;
  direction: TrendDirection;
  first_value: number;
  last_value: number;
  change_pct: number;
  periods: number;
}

export interface Anomaly {
  column: string;
  index_label: string;
  value: number;
  mean: number;
  std_dev: number;
  z_score: number;
}

export interface KpiCard {
  label: string;
  value: number;
  unit: string;
  change_pct: number | null;
  direction: TrendDirection | null;
}

export interface SeriesPoint {
  label: string;
  value: number;
  is_anomaly: boolean;
}

export interface ChartSeries {
  column: string;
  points: SeriesPoint[];
}

/** Everything measured from a file. No model was involved in producing it. */
export interface Analysis {
  dataset: string;
  row_count: number;
  column_count: number;
  columns: ColumnProfile[];
  date_column: string | null;
  kpis: KpiCard[];
  series: ChartSeries[];
  trends: Trend[];
  anomalies: Anomaly[];
  preview_rows: Record<string, string>[];
  preview_columns: string[];
  facts_key: string;
}

/** One finding in the three-part form CLAUDE.md Section 11 mandates. */
export interface Insight {
  observed: string;
  hypothesis: string;
  recommendation: string;
}

export interface InsightReport {
  summary: string;
  insights: Insight[];
}

export interface InsightResponse {
  report: InsightReport;
  model: string;
  provider: string;
  duration_ms: number;
  input_tokens: number;
  output_tokens: number;
  estimated_cost_usd: number | null;
  from_cache: boolean;
}

export interface SampleDataset {
  key: string;
  name: string;
  description: string;
  row_count: number;
}

export interface SampleListResponse {
  samples: SampleDataset[];
}

/* ------------------------------------------------------------------ *
 * Project 6 — AI Travel Operations, the flagship (`/api/travel`)
 *
 * `CommunicationStatus` has no "sent". The deployment records an approved
 * message and transmits nothing, and a status implying otherwise would be a
 * lie told by a type.
 * ------------------------------------------------------------------ */

export type IncidentKind =
  | "flight_delay"
  | "flight_cancellation"
  | "hotel_overbooking"
  | "schedule_change"
  | "other";

export type Severity = "low" | "medium" | "high" | "critical";

export type IncidentStatus =
  | "open"
  | "assessed"
  | "awaiting_approval"
  | "resolved";

export type CommunicationStatus = "draft" | "approved" | "rejected";

export interface AffectedBooking {
  id: string;
  agent_id: string;
  agent_name: string;
  traveller_name: string;
  booking_type: string;
  route: string | null;
  supplier: string | null;
  departure_at: string | null;
  status: string;
  value_inr: number;
}

export interface CommunicationView {
  id: string;
  agent_id: string;
  agent_name: string;
  booking_ids: string[];
  subject: string;
  body: string;
  status: CommunicationStatus;
  approved_by: string | null;
  approved_at: string | null;
  rejection_note: string | null;
  recorded_message_id: string | null;
}

export interface IncidentSummary {
  id: string;
  kind: IncidentKind;
  title: string;
  route: string | null;
  supplier: string | null;
  occurred_at: string | null;
  status: IncidentStatus;
  severity: Severity | null;
  affected_count: number;
  affected_value_inr: number;
  draft_count: number;
  awaiting_approval_count: number;
}

export interface IncidentDetail {
  id: string;
  kind: IncidentKind;
  title: string;
  description: string;
  route: string | null;
  supplier: string | null;
  occurred_at: string | null;
  status: IncidentStatus;
  severity: Severity | null;
  severity_reasoning: string | null;
  traveller_impact: string | null;
  recommended_action: string | null;
  affected_count: number;
  affected_value_inr: number;
  affected_bookings: AffectedBooking[];
  communications: CommunicationView[];
  execution: WorkflowExecutionView | null;
  created_at: string;
}

/** The stored workflow run — the audit trail for one incident. */
export interface WorkflowExecutionView {
  id: string;
  workflow_id: string;
  status: "running" | "succeeded" | "failed" | "awaiting_approval";
  node_runs: {
    node_id: string;
    node_type: string;
    label: string;
    status: string;
    duration_ms: number;
    output: Record<string, unknown>;
    error: string | null;
    ai_model: string | null;
    estimated_cost_usd: number | null;
  }[];
  awaiting_node_id: string | null;
  error: string | null;
}

export interface TravelUsageInfo {
  model: string;
  provider: string;
  duration_ms: number;
  input_tokens: number;
  output_tokens: number;
  estimated_cost_usd: number | null;
  from_demo_cache: boolean;
}

export interface AssessResponse {
  incident: IncidentDetail;
  usage: TravelUsageInfo;
}

export interface IncidentListResponse {
  incidents: IncidentSummary[];
  seeded: number;
}

export interface AgentPartner {
  agent_id: string;
  agent_name: string;
  booking_count: number;
  total_value_inr: number;
  confirmed: number;
  delayed: number;
  cancelled: number;
  open_tickets: number;
  urgent_tickets: number;
  last_booking_at: string | null;
  incidents_involved: number;
  awaiting_approval: number;
  next_follow_up: string | null;
}

export interface PartnerListResponse {
  partners: AgentPartner[];
}

/* ------------------------------------------------------------------ *
 * Project 4 — AI Workflow Builder (`/api/workflows`)
 *
 * `WorkflowDefinition` mirrors the engine's own `Workflow`. The builder edits
 * this and hands it straight back, which is what makes Project 4 a client of
 * the engine rather than a second implementation of it.
 * ------------------------------------------------------------------ */

export type WorkflowNodeType =
  | "trigger"
  | "ai_classification"
  | "ai_extraction"
  | "ai_summarization"
  | "ai_generation"
  | "condition"
  | "transform"
  | "email"
  | "webhook"
  | "database"
  | "notification"
  | "human_approval";

export interface WorkflowNodeDefinition {
  id: string;
  type: WorkflowNodeType;
  label: string;
  config: Record<string, unknown>;
  next_id: string | null;
  next_id_if_false: string | null;
}

export interface WorkflowDefinition {
  id: string;
  name: string;
  description: string;
  nodes: WorkflowNodeDefinition[];
  start_node_id: string | null;
  is_active: boolean;
  created_at: string;
}

export interface WorkflowValidationIssue {
  code: string;
  message: string;
  node_id: string | null;
}

export interface PaletteEntry {
  type: WorkflowNodeType;
  label: string;
  available: boolean;
  reason: string | null;
  high_risk: boolean;
}

export interface WorkflowSummary {
  id: string;
  name: string;
  description: string;
  node_count: number;
  is_read_only: boolean;
  blocking_issue_count: number;
  ai_request_estimate: number;
}

export interface WorkflowExecutionSummary {
  id: string;
  status: string;
  created_at: string;
  node_count: number;
  total_cost_usd: number;
}

export interface WorkflowDetail {
  id: string;
  name: string;
  description: string;
  is_read_only: boolean;
  definition: WorkflowDefinition;
  issues: WorkflowValidationIssue[];
  ai_request_estimate: number;
  executions: WorkflowExecutionSummary[];
}

export interface WorkflowListResponse {
  workflows: WorkflowSummary[];
  palette: PaletteEntry[];
  seeded: number;
}

export interface WorkflowExecutionDetail {
  id: string;
  workflow_id: string;
  status: string;
  execution: WorkflowExecutionView;
}

/* ------------------------------------------------------------------------- *
 * Project 5 — AI Project Tracker (`/api/tracker`)
 *
 * The split that defines this project shows up in these types. `ProjectFacts`
 * is computed in Python from the stored rows — overdue counts, blocked counts,
 * dependency state — and no model ever produces it. `health` and its
 * `health_reasoning` are the model's, and the backend cannot store one without
 * the other.
 * ------------------------------------------------------------------------- */

export type Health = "green" | "yellow" | "red";
export type ProjectState = "active" | "paused" | "done";
export type TaskStatus = "todo" | "in_progress" | "blocked" | "done";
export type TaskPriority = "low" | "medium" | "high" | "urgent";

export interface TaskView {
  id: string;
  title: string;
  owner: string;
  due_date: string | null;
  status: TaskStatus;
  priority: TaskPriority;
  blocker_note: string | null;
  depends_on_id: string | null;
  depends_on_title: string | null;
  /** Computed, never stored and never generated. */
  is_overdue: boolean;
  days_overdue: number | null;
  blocked_by: string | null;
}

export interface ProjectFacts {
  task_count: number;
  done_count: number;
  in_progress_count: number;
  todo_count: number;
  blocked_count: number;
  overdue_count: number;
  overdue_task_titles: string[];
  blocked_task_titles: string[];
  dependency_blocked_titles: string[];
  unassigned_count: number;
  completion_percent: number;
  days_to_target: number | null;
  target_date: string | null;
  risk_count: number;
  risks: string[];
}

export interface TrackerSuggestedAction {
  action: string;
  rationale: string;
  task_id: string | null;
}

export interface TrackedProjectListItem {
  id: string;
  name: string;
  owner: string;
  state: ProjectState;
  target_date: string | null;
  health: Health | null;
  health_reasoning: string | null;
  task_count: number;
  done_count: number;
  overdue_count: number;
  blocked_count: number;
  completion_percent: number;
}

export interface TrackedProjectDetail {
  id: string;
  name: string;
  description: string;
  owner: string;
  state: ProjectState;
  target_date: string | null;
  risks: string[];
  health: Health | null;
  health_reasoning: string | null;
  health_factors: string[];
  health_confidence: string | null;
  health_assessed_at: string | null;
  next_actions: TrackerSuggestedAction[];
  summary: string | null;
  facts: ProjectFacts;
  tasks: TaskView[];
  created_at: string;
}

export interface TrackerUsageInfo {
  model: string;
  provider: string;
  duration_ms: number;
  input_tokens: number;
  output_tokens: number;
  estimated_cost_usd: number | null;
  from_demo_cache: boolean;
}

export interface TrackerAssessResponse {
  project: TrackedProjectDetail;
  usage: TrackerUsageInfo;
}

export interface TrackerProjectListResponse {
  projects: TrackedProjectListItem[];
  seeded: number;
  ai_requests_per_assessment: number;
}

export interface WeeklyReportContent {
  executive_summary: string;
  highlights: string[];
  concerns: string[];
  risks: string[];
  recommended_actions: string[];
}

export interface WeeklyReportResponse {
  generated_at: string;
  project_count: number;
  content: WeeklyReportContent;
  project_facts: TrackedProjectListItem[];
  usage: TrackerUsageInfo;
}

/* ------------------------------------------------------------------------- *
 * Project 9 — AI Ops Command Center (`/api/command-center`)
 *
 * An aggregator. Every signal here was produced by another project and is
 * re-read on each request; this project stores only the narrative it writes.
 * `link` is what makes it an aggregator rather than a second dashboard — every
 * item points back at whichever project owns it (Section 17).
 * ------------------------------------------------------------------------- */

export type SignalSeverity = "critical" | "warning" | "info";
export type SignalSource = "tracker" | "workflows" | "travel_ops" | "dashboard";

export interface SignalView {
  id: string;
  source: SignalSource;
  source_label: string;
  severity: SignalSeverity;
  title: string;
  detail: string;
  link: string;
}

export interface SourceView {
  source: SignalSource;
  label: string;
  available: boolean;
  detail: string;
  signal_count: number;
  link: string;
}

export interface BriefAction {
  action: string;
  signal_id: string | null;
}

export interface BriefView {
  id: string;
  summary: string;
  actions: BriefAction[];
  generated_at: string;
  /** How many per-source counts moved since generation. 0 means current. */
  changed_since: number;
  unavailable_sources: string[];
}

export interface CommandCenterResponse {
  collected_at: string;
  signals: SignalView[];
  sources: SourceView[];
  brief: BriefView | null;
  critical_count: number;
  warning_count: number;
  info_count: number;
  ai_requests_per_brief: number;
  dashboard_dataset: string;
}

export interface GenerateBriefResponse {
  brief: BriefView;
  usage: TrackerUsageInfo;
}
