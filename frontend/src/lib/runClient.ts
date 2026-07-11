/**
 * Typed fetch wrappers around Plan 01-01's FastAPI run routes.
 *
 * This is the single place HTTP calls to the backend are made — components
 * must call these functions, not `fetch` directly. Requests are made against
 * relative paths (`/runs`, ...) so Vite's dev server proxy (see
 * vite.config.ts) forwards them to the backend without any CORS setup.
 *
 * The TypeScript interfaces below are a parallel declaration of the same JSON
 * contract the backend's Pydantic models (`backend/app/models/plan.py`)
 * produce — mirrored here per CLAUDE.md's "shared shape" rule applied at the
 * API boundary, not a second source of truth for backend logic.
 */

export interface Task {
  id: string;
  title: string;
  description: string;
  suggested_assignee: string;
  estimate_hours: number;
  skill_tag: string | null;
  depends_on: string[];
}

export interface Epic {
  id: string;
  title: string;
  description: string;
  tasks: Task[];
}

export interface Plan {
  epics: Epic[];
}

export interface PushResultItem {
  item_id: string;
  ado_work_item_id: number | null;
  status: "created" | "assignment_unresolved" | "create_failed" | "link_failed" | "not_implemented";
  detail: string | null;
}

export interface PushReport {
  items: PushResultItem[];
  all_succeeded: boolean;
}

export interface RiskItem {
  skill: string;
  hours_at_risk: number;
  severity: "low" | "medium" | "high";
  detail: string;
}

export interface RiskReport {
  score: number;
  level: "low" | "medium" | "high";
  items: RiskItem[];
  narrative: string;
}

export interface SmokeTestCheck {
  check: string;
  passed: boolean;
  reason: string | null;
}

export interface SmokeTest {
  passed: boolean;
  checks: SmokeTestCheck[];
}

export interface RunResponse {
  run_id: string;
  status:
    | "running"
    | "awaiting_review"
    | "completed"
    | "not_found"
    | "blocked_smoke_test_failed"
    | "failed";
  plan: Plan | null;
  push_report: PushReport | null;
  smoke_test: SmokeTest | null;
  smoke_test_passed: boolean | null;
  repo_mode: string | null;
  risk: RiskReport | null;
  team_count: number | null;
  onboarding_summary: string | null;
  /** Professional markdown plan document rendered from the plan JSON; null until composed. */
  plan_document: string | null;
  demo_mode: boolean | null;
  /** Raw LangGraph node the run is about to execute / paused inside; null once settled. */
  current_stage: string | null;
  /** Set only when status is "failed": the background-run crash message. */
  error?: string | null;
}

export interface EditResponse {
  current_plan: Plan;
  proposed_plan: Plan;
  diff: string;
  note: string;
  risk: RiskReport;
}

async function parseRunResponse(res: Response): Promise<RunResponse> {
  if (!res.ok) {
    throw new Error(`Request failed with status ${res.status}`);
  }
  return (await res.json()) as RunResponse;
}

async function parseEditResponse(res: Response): Promise<EditResponse> {
  if (!res.ok) {
    throw new Error(`Request failed with status ${res.status}`);
  }
  return (await res.json()) as EditResponse;
}

export async function startRun(): Promise<RunResponse> {
  const res = await fetch("/runs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
  return parseRunResponse(res);
}

export async function getRun(runId: string): Promise<RunResponse> {
  const res = await fetch(`/runs/${runId}`);
  return parseRunResponse(res);
}

export async function approveRun(runId: string): Promise<RunResponse> {
  const res = await fetch(`/runs/${runId}/resume`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ approved: true }),
  });
  return parseRunResponse(res);
}

export async function editPlan(
  runId: string,
  instruction: string,
): Promise<EditResponse> {
  const res = await fetch(`/runs/${runId}/edit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ instruction }),
  });
  return parseEditResponse(res);
}

export async function applyPlan(
  runId: string,
  plan: Plan,
): Promise<RunResponse> {
  const res = await fetch(`/runs/${runId}/apply`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ plan }),
  });
  return parseRunResponse(res);
}
