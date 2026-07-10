import { useEffect, useRef, useState } from "react";
import DiffView from "../components/DiffView";
import {
  applyPlan,
  approveRun,
  editPlan,
  getRun,
  startRun,
  type EditResponse,
  type Plan,
  type PushReport,
  type RiskReport,
  type RunResponse,
  type SmokeTest,
} from "../lib/runClient";

type UiStatus = RunResponse["status"] | "idle";

const POLL_INTERVAL_MS = 2000;

const EXAMPLE_INSTRUCTIONS = [
  "reassign <task> to <name>",
  "split <task>",
  "change estimate of <task> to 8",
  "remove <task>",
];

function riskBadgeClass(level: RiskReport["level"] | undefined): string {
  switch (level) {
    case "low":
      return "badge badge-low";
    case "medium":
      return "badge badge-medium";
    case "high":
      return "badge badge-high";
    default:
      return "badge";
  }
}

function severityBadgeClass(severity: string): string {
  switch (severity) {
    case "low":
      return "badge badge-low badge-sm";
    case "medium":
      return "badge badge-medium badge-sm";
    case "high":
      return "badge badge-high badge-sm";
    default:
      return "badge badge-sm";
  }
}

function pushStatusClass(status: string): string {
  switch (status) {
    case "created":
      return "badge badge-low badge-sm";
    case "assignment_unresolved":
      return "badge badge-medium badge-sm";
    case "create_failed":
    case "link_failed":
      return "badge badge-high badge-sm";
    case "not_implemented":
      // Expected simulated-push result in demo mode — keep neutral, not error-red.
      return "badge badge-sm";
    default:
      return "badge badge-sm";
  }
}

/**
 * Main demo flow, step 2: start a planning run, review the AI-generated
 * plan + risk panel, iterate on it via chat-driven edits with a diff
 * preview, approve, and watch the ADO push report land.
 */
export default function RunPage() {
  const [runId, setRunId] = useState<string | null>(null);
  const [status, setStatus] = useState<UiStatus>("idle");
  const [plan, setPlan] = useState<Plan | null>(null);
  const [pushReport, setPushReport] = useState<PushReport | null>(null);
  const [smokeTest, setSmokeTest] = useState<SmokeTest | null>(null);
  const [repoMode, setRepoMode] = useState<string | null>(null);
  const [risk, setRisk] = useState<RiskReport | null>(null);
  const [teamCount, setTeamCount] = useState<number | null>(null);
  const [onboardingSummary, setOnboardingSummary] = useState<string | null>(null);
  const [demoMode, setDemoMode] = useState<boolean | null>(null);
  const [smokeTestPassed, setSmokeTestPassed] = useState<boolean | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [instruction, setInstruction] = useState("");
  const [proposal, setProposal] = useState<EditResponse | null>(null);
  const [editLoading, setEditLoading] = useState(false);
  const [approveLoading, setApproveLoading] = useState(false);

  const pollHandleRef = useRef<ReturnType<typeof setInterval> | null>(null);

  function applyRunResponse(res: RunResponse) {
    setRunId(res.run_id);
    setStatus(res.status);
    setPlan(res.plan);
    setPushReport(res.push_report);
    setSmokeTest(res.smoke_test);
    setRepoMode(res.repo_mode);
    setRisk(res.risk);
    setTeamCount(res.team_count);
    setOnboardingSummary(res.onboarding_summary);
    setDemoMode(res.demo_mode);
    setSmokeTestPassed(res.smoke_test_passed);
  }

  function stopPolling() {
    if (pollHandleRef.current !== null) {
      clearInterval(pollHandleRef.current);
      pollHandleRef.current = null;
    }
  }

  // Poll GET /runs/{id} while a run is in flight; stop once the server
  // reports a terminal state (completed or blocked). Each poll response is
  // treated as the source of truth, never assumed from client state alone.
  useEffect(() => {
    const inFlight =
      status === "running" || status === "awaiting_review";

    if (!runId || !inFlight) {
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
    setProposal(null);
    try {
      const res = await startRun();
      applyRunResponse(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function handleApprove() {
    if (!runId || status !== "awaiting_review") {
      return;
    }
    setError(null);
    setApproveLoading(true);
    try {
      const res = await approveRun(runId);
      applyRunResponse(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setApproveLoading(false);
    }
  }

  async function handleProposeEdit() {
    if (!runId || !instruction.trim()) return;
    setError(null);
    setEditLoading(true);
    try {
      const res = await editPlan(runId, instruction.trim());
      setProposal(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setEditLoading(false);
    }
  }

  async function handleAccept() {
    if (!runId || !proposal) return;
    setError(null);
    try {
      const res = await applyPlan(runId, proposal.proposed_plan);
      applyRunResponse(res);
      setProposal(null);
      setInstruction("");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  function handleReject() {
    setProposal(null);
  }

  const isRunInProgress = status === "running" || status === "awaiting_review";
  const isBlocked = status === "blocked_smoke_test_failed";

  return (
    <div className="page">
      <h1>Run</h1>
      <p className="step-hint">
        Step 2 of 2 — generate, review, and push the implementation plan. Set
        up your team on the Team tab first so the plan can assign work.
      </p>

      <section className="card">
        <h2>Connection &amp; status</h2>
        {error && <p className="error-text">Error: {error}</p>}

        <div className="row">
          <button
            type="button"
            className="btn btn-primary"
            onClick={handleStart}
            disabled={isRunInProgress}
          >
            {isRunInProgress ? "Run in progress…" : "Start Run"}
          </button>
          <span className="status-text">
            Status: <strong>{status}</strong>
          </span>
        </div>

        {runId && (
          <div className="meta-row">
            {repoMode && <span className="tag">repo mode: {repoMode}</span>}
            {teamCount !== null && (
              <span className="tag">team size: {teamCount}</span>
            )}
          </div>
        )}

        {smokeTest && (
          <div className="smoke-test">
            <h3>ADO PAT smoke test</h3>
            <p>
              Overall:{" "}
              <span className={smokeTest.passed ? "ok-text" : "fail-text"}>
                {smokeTest.passed ? "passed" : "failed"}
              </span>
            </p>
            <ul className="check-list">
              {smokeTest.checks.map((c, i) => (
                <li key={i}>
                  <span className={c.passed ? "ok-text" : "fail-text"}>
                    {c.passed ? "✓" : "✗"}
                  </span>{" "}
                  {c.check}
                  {c.reason && <span className="muted"> — {c.reason}</span>}
                </li>
              ))}
            </ul>
          </div>
        )}

        {demoMode === true && smokeTestPassed === false && !isBlocked && (
          <div className="banner banner-demo">
            <strong>Demo mode — ADO not connected (no valid PAT).</strong>
            <p>
              Planning works normally; the ADO push is simulated. Add a valid
              PAT and set <code>DEMO_MODE=false</code> to push work items for
              real.
            </p>
          </div>
        )}

        {isBlocked && (
          <div className="banner banner-danger">
            <strong>Run blocked: ADO PAT smoke test failed.</strong>
            <p>
              The Azure DevOps personal access token could not be verified in
              this environment (it may be absent or expired). This is an
              expected state for a local demo without live ADO credentials —
              the pipeline stops here rather than generating a plan it can't
              push. Configure a valid <code>ADO_PAT</code> in <code>.env</code>{" "}
              and start a new run to proceed.
            </p>
          </div>
        )}
      </section>

      {!isBlocked && onboardingSummary && onboardingSummary.trim() !== "" && (
        <section className="card">
          <h2>Codebase onboarding summary</h2>
          <p className="muted small-caption">
            AI-generated — verify before relying.
          </p>
          <pre className="onboarding-text">{onboardingSummary}</pre>
        </section>
      )}

      {!isBlocked && plan && (
        <section className="card">
          <h2>AI-generated plan (review &amp; edit before pushing)</h2>
          {plan.epics.map((epic) => (
            <div key={epic.id} className="epic">
              <h3>{epic.title}</h3>
              {epic.description && <p className="muted">{epic.description}</p>}
              <ul className="task-list">
                {epic.tasks.map((task) => (
                  <li key={task.id} className="task-card">
                    <div className="task-title">{task.title}</div>
                    <div className="task-meta">
                      <span
                        className={
                          task.suggested_assignee
                            ? "assignee-badge"
                            : "assignee-badge assignee-unassigned"
                        }
                      >
                        {task.suggested_assignee || "unassigned"}
                      </span>
                      <span className="tag">{task.estimate_hours}h</span>
                      {task.skill_tag && (
                        <span className="tag">{task.skill_tag}</span>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </section>
      )}

      {!isBlocked && risk && (
        <section className="card">
          <h2>Risk</h2>
          <div className="row">
            <span className={riskBadgeClass(risk.level)}>
              {risk.level.toUpperCase()} · {risk.score}
            </span>
          </div>
          <p>{risk.narrative}</p>
          <p className="muted small-caption">
            AI-suggested — verify before relying on this.
          </p>
          {risk.items.length > 0 && (
            <ul className="risk-list">
              {risk.items.map((item, i) => (
                <li key={i}>
                  <span className={severityBadgeClass(item.severity)}>
                    {item.severity}
                  </span>{" "}
                  <strong>{item.skill}</strong> — {item.hours_at_risk}h at risk
                  <div className="muted">{item.detail}</div>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {!isBlocked && status === "awaiting_review" && (
        <section className="card">
          <h2>Edit plan via chat</h2>
          <p className="muted small-caption">
            Examples: {EXAMPLE_INSTRUCTIONS.join(" · ")}
          </p>
          <div className="row">
            <input
              className="text-input"
              placeholder="e.g. reassign Setup CI to Priya"
              value={instruction}
              onChange={(e) => setInstruction(e.target.value)}
              disabled={editLoading || !!proposal}
            />
            <button
              type="button"
              className="btn"
              onClick={handleProposeEdit}
              disabled={editLoading || !instruction.trim() || !!proposal}
            >
              {editLoading ? "Proposing…" : "Propose edit"}
            </button>
          </div>

          {proposal && (
            <div className="proposal">
              <p className="proposal-note">{proposal.note}</p>
              <DiffView diff={proposal.diff} />
              <div className="row">
                <button type="button" className="btn btn-primary" onClick={handleAccept}>
                  Accept
                </button>
                <button type="button" className="btn btn-secondary" onClick={handleReject}>
                  Reject
                </button>
              </div>
            </div>
          )}
        </section>
      )}

      {!isBlocked && status === "awaiting_review" && !proposal && (
        <section className="card">
          <button
            type="button"
            className="btn btn-approve"
            onClick={handleApprove}
            disabled={approveLoading}
          >
            {approveLoading ? "Approving…" : "Approve plan & push to ADO"}
          </button>
        </section>
      )}

      {pushReport && (
        <section className="card">
          <h2>ADO push report</h2>
          <p>
            All succeeded:{" "}
            <span className={pushReport.all_succeeded ? "ok-text" : "fail-text"}>
              {String(pushReport.all_succeeded)}
            </span>
          </p>
          {!pushReport.all_succeeded && (
            <p className="muted small-caption">
              Item failures due to a missing/expired ADO PAT are expected in
              this environment.
            </p>
          )}
          <ul className="push-list">
            {pushReport.items.map((item) => (
              <li key={item.item_id}>
                <span className={pushStatusClass(item.status)}>{item.status}</span>{" "}
                <span className="mono">{item.item_id}</span>
                {item.ado_work_item_id !== null && (
                  <span className="muted"> — ADO #{item.ado_work_item_id}</span>
                )}
                {item.detail && <div className="muted">{item.detail}</div>}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
