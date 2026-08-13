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
