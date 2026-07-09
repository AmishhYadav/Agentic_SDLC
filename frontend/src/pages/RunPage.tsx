import { useEffect, useRef, useState } from "react";
import {
  approveRun,
  getRun,
  startRun,
  type Plan,
  type PushReport,
  type RunResponse,
} from "../lib/runClient";

type UiStatus = RunResponse["status"] | "idle";

const POLL_INTERVAL_MS = 2000;

/**
 * Demo-only page (D-07/D-08): a Start button, a polling status indicator,
 * a plain-text stub plan render, and an Approve button. No styling/polish,
 * no config or team forms — this exists solely to prove the interrupt/
 * resume flow through a real browser UI instead of curl.
 */
export default function RunPage() {
  const [runId, setRunId] = useState<string | null>(null);
  const [status, setStatus] = useState<UiStatus>("idle");
  const [plan, setPlan] = useState<Plan | null>(null);
  const [pushReport, setPushReport] = useState<PushReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  const pollHandleRef = useRef<ReturnType<typeof setInterval> | null>(null);

  function applyRunResponse(res: RunResponse) {
    setRunId(res.run_id);
    setStatus(res.status);
    setPlan(res.plan);
    setPushReport(res.push_report);
  }

  function stopPolling() {
    if (pollHandleRef.current !== null) {
      clearInterval(pollHandleRef.current);
      pollHandleRef.current = null;
    }
  }

  // Poll GET /runs/{id} on a fixed interval while a run is in flight.
  // Stop as soon as the server reports "completed". Pitfall 3 fix: the
  // client treats each poll response as the source of truth, never an
  // assumption derived from client-side state alone.
  useEffect(() => {
    if (!runId || status === "completed" || status === "idle") {
      stopPolling();
      return;
    }

    pollHandleRef.current = setInterval(async () => {
      try {
        const res = await getRun(runId);
        applyRunResponse(res);
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      }
    }, POLL_INTERVAL_MS);

    return () => stopPolling();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId, status]);

  async function handleStart() {
    setError(null);
    try {
      const res = await startRun();
      applyRunResponse(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function handleApprove() {
    if (!runId || status !== "awaiting_review") {
      // Approve must only fire once the client has confirmed
      // awaiting_review via a real poll response (Pitfall 3 regression
      // guard) — this branch should be unreachable since the button is
      // hidden otherwise, but guard defensively anyway.
      return;
    }
    setError(null);
    try {
      const res = await approveRun(runId);
      applyRunResponse(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  const isRunInProgress = status !== "idle" && status !== "completed";

  return (
    <div>
      <h1>Run Demo (Phase 1 thin slice)</h1>

      <p>Status: {status}</p>

      {error && <p>Error: {error}</p>}

      <button type="button" onClick={handleStart} disabled={isRunInProgress}>
        Start
      </button>

      {plan && (
        <div>
          <h2>Plan</h2>
          {plan.epics.map((epic) => (
            <div key={epic.id}>
              <h3>Epic: {epic.title}</h3>
              <ul>
                {epic.tasks.map((task) => (
                  <li key={task.id}>
                    {task.title} — assignee: {task.suggested_assignee} —
                    estimate: {task.estimate_hours}h
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}

      {status === "awaiting_review" && (
        <button type="button" onClick={handleApprove}>
          Approve
        </button>
      )}

      {pushReport && (
        <div>
          <h2>Push Report</h2>
          <p>All succeeded: {String(pushReport.all_succeeded)}</p>
          <ul>
            {pushReport.items.map((item) => (
              <li key={item.item_id}>
                {item.item_id} — status: {item.status} — ado_work_item_id:{" "}
                {item.ado_work_item_id ?? "none"} — detail:{" "}
                {item.detail ?? "none"}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
