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
