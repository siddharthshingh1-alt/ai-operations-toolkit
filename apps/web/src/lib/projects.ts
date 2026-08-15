import type { ProjectSummary } from "@aiops/types";

/**
 * The nine projects, in the build order from CLAUDE.md Section 8.
 *
 * `status` is the single source of truth for what the UI claims is working.
 * A project stays `planned` until it genuinely ships — nothing here should
 * ever describe a capability the repo does not have.
 */
export const PROJECTS: ProjectSummary[] = [
  {
    slug: "ai-sop-generator",
    name: "AI SOP Generator",
    jdRequirement: "Document and standardize scalable operational processes",
    description:
      "Turns messy operational knowledge into standardized, searchable SOPs, with version diffing and citation-backed semantic search.",
    status: "shipped",
    phase: 1,
  },
  {
    slug: "ai-operations-dashboard",
    name: "AI Operations Dashboard",
    jdRequirement: "Build dashboards; analyze operational data",
    description:
      "Upload a CSV or Excel file and get KPI cards, charts, trend and anomaly detection, with observations kept separate from hypotheses.",
    status: "shipped",
    phase: 2,
  },
  {
    slug: "ai-travel-operations",
    name: "AI Travel Operations",
    jdRequirement: "Identify operational bottlenecks and solve them using AI",
    description:
      "The flagship. A working simulation of B2B travel operations: bookings, delays, incidents, refunds, and a travel-agent partner view.",
    status: "shipped",
    phase: 3,
  },
  {
    slug: "ai-workflow-builder",
    name: "AI Workflow Builder",
    jdRequirement: "Build AI-assisted workflows and automations",
    description:
      "A visual editor on top of the shared workflow engine, with a full execution log for every run.",
    status: "planned",
    phase: 4,
  },
  {
    slug: "ai-project-tracker",
    name: "AI Project Tracker",
    jdRequirement: "Own projects from planning to implementation; build trackers",
    description:
      "Projects, tasks, owners, deadlines, and blockers, with an AI health assessment that explains why it chose each status.",
    status: "planned",
    phase: 5,
  },
  {
    slug: "ai-report-generator",
    name: "AI Report Generator",
    jdRequirement: "Analyze operational data and identify improvements",
    description:
      "Daily, weekly, and monthly operational reports exported to PDF, Markdown, and HTML, reusing the dashboard's analysis.",
    status: "planned",
    phase: 6,
  },
  {
    slug: "ai-operations-inbox",
    name: "AI Operations Inbox",
    jdRequirement: "Build AI-assisted automations",
    description:
      "Classifies, summarizes, and drafts replies to operational email. Nothing is ever sent without explicit human approval.",
    status: "planned",
    phase: 7,
  },
  {
    slug: "ai-ops-command-center",
    name: "AI Ops Command Center",
    jdRequirement: "Collaborate cross-functionally to drive execution",
    description:
      "Aggregates KPIs, workflows, tasks, alerts, and inbox items into one daily Ops Brief. Every item links back to its source project.",
    status: "planned",
    phase: 8,
  },
  {
    slug: "ai-meeting-assistant",
    name: "AI Meeting Assistant",
    jdRequirement: "Collaborate cross-functionally (stretch goal)",
    description:
      "Turns a transcript or recording into decisions, action items, owners, and deadlines. Built only after the core projects ship.",
    status: "planned",
    phase: 9,
  },
];

export function projectsByPhase(): ProjectSummary[] {
  return [...PROJECTS].sort((a, b) => a.phase - b.phase);
}
