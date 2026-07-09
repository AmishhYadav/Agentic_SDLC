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

export interface RunResponse {
  run_id: string;
  status: "running" | "awaiting_review" | "completed" | "not_found";
  plan: Plan | null;
  push_report: PushReport | null;
}

async function parseRunResponse(res: Response): Promise<RunResponse> {
  if (!res.ok) {
    throw new Error(`Request failed with status ${res.status}`);
  }
  return (await res.json()) as RunResponse;
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
