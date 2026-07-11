import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
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

// The fixed pipeline the graph walks (build.py): connect → read repo →
// generate → assign/score → human review → push. The two repo-ingestion nodes
// (greenfield/brownfield) are collapsed into one "read repo" row since only one
// ever runs per repo_mode.
type StageState =
  | "done"
  | "active"
  | "awaiting"
  | "pending"
  | "failed"
  | "skipped";

interface StageDef {
  key: string;
  label: string;
  hint: string;
}

const PIPELINE_STAGES: StageDef[] = [
  {
    key: "ingest_config",
    label: "Connect ADO & GitHub",
    hint: "Verify the ADO PAT (smoke test) and load repo settings",
  },
  {
    key: "read_repo",
    label: "Read the repository",
    hint: "Greenfield reads the docs; brownfield indexes the codebase for RAG",
  },
  {
    key: "generate_plan",
    label: "Generate the plan (AI)",
    hint: "Draft epics → skill-tagged, estimated tasks",
  },
  {
    key: "assign_and_score",
    label: "Assign & score risk",
    hint: "Load-balance tasks across the team and compute the risk score",
  },
  {
    key: "compose_plan_document",
    label: "Compose plan document",
    hint: "Write the professional, detailed implementation plan document",
  },
  {
    key: "human_review",
    label: "Your review",
    hint: "Pause so you can edit and approve before anything is pushed",
  },
  {
    key: "push_to_ado",
    label: "Push to Azure DevOps",
    hint: "Create assigned work items (simulated in demo mode)",
  },
];

const HUMAN_REVIEW_IDX = PIPELINE_STAGES.findIndex(
  (s) => s.key === "human_review",
);

const STAGE_ICONS: Record<StageState, string> = {
  done: "✓",
  active: "●",
  awaiting: "▶",
  pending: "○",
  failed: "✗",
  skipped: "–",
};

function normalizeStage(stage: string | null): string | null {
  if (stage === "read_docs_greenfield" || stage === "ingest_brownfield") {
    return "read_repo";
  }
  return stage;
}

// Map the run's overall status + the backend's current_stage (the node the
// graph is about to run / paused inside) onto a per-row state for the checklist.
function computeStageStates(
  status: UiStatus,
  currentStage: string | null,
): StageState[] {
  const activeKey = normalizeStage(currentStage);
  const activeIdx = activeKey
    ? PIPELINE_STAGES.findIndex((s) => s.key === activeKey)
    : -1;

  return PIPELINE_STAGES.map((_, idx) => {
    if (status === "blocked_smoke_test_failed") {
      return idx === 0 ? "failed" : "skipped";
    }
    if (status === "failed") {
      // The run crashed at activeIdx (the node it was about to run / inside).
      if (activeIdx === -1) return idx === 0 ? "failed" : "skipped";
      if (idx < activeIdx) return "done";
      if (idx === activeIdx) return "failed";
      return "skipped";
    }
    if (status === "completed") return "done";
    if (status === "awaiting_review") {
      if (idx < HUMAN_REVIEW_IDX) return "done";
      if (idx === HUMAN_REVIEW_IDX) return "awaiting";
      return "pending";
    }
    // status === "running" (or transient): lean on current_stage.
    if (activeIdx === -1) return "pending";
    if (idx < activeIdx) return "done";
    if (idx === activeIdx) return "active";
    return "pending";
  });
}

function stageStatusLabel(state: StageState): string | null {
  switch (state) {
    case "active":
      return " — in progress…";
    case "awaiting":
      return " — waiting for you";
    case "done":
      return " — done";
    case "failed":
      return " — failed";
    default:
      return null;
  }
}

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
  const [planDocument, setPlanDocument] = useState<string | null>(null);
  const [demoMode, setDemoMode] = useState<boolean | null>(null);
  const [smokeTestPassed, setSmokeTestPassed] = useState<boolean | null>(null);
  const [currentStage, setCurrentStage] = useState<string | null>(null);
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
    setPlanDocument(res.plan_document);
    setDemoMode(res.demo_mode);
    setSmokeTestPassed(res.smoke_test_passed);
    setCurrentStage(res.current_stage);
    if (res.status === "failed" && res.error) {
      setError(res.error);
    }
  }

  // Abandon the current run and return to a clean slate — the escape hatch for
  // a run that crashed or got stuck (so the disabled Start Run button, gated on
  // an in-flight run, doesn't trap the lead on a dead run).
  function handleReset() {
    stopPolling();
    setRunId(null);
    setStatus("idle");
    setPlan(null);
    setPushReport(null);
    setSmokeTest(null);
    setRepoMode(null);
    setRisk(null);
    setTeamCount(null);
    setOnboardingSummary(null);
    setPlanDocument(null);
    setDemoMode(null);
    setSmokeTestPassed(null);
    setCurrentStage(null);
    setProposal(null);
    setInstruction("");
    setError(null);
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

  function handleDownloadDocument() {
    if (!planDocument) return;
    const blob = new Blob([planDocument], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "implementation-plan.md";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  const isRunInProgress = status === "running" || status === "awaiting_review";
  const isBlocked = status === "blocked_smoke_test_failed";
  const stageStates = computeStageStates(status, currentStage);

  return (
    <div className="page">
      <h1>Run</h1>
      <p className="step-hint">
        Step 2 of 2 — generate, review, and push the implementation plan. Set
        up your team on the Team tab first so the plan can assign work.
      </p>

      <section className="card">
        <h2>Connection &amp; status</h2>
        {error && status !== "failed" && (
          <p className="error-text">Error: {error}</p>
        )}

        {status === "idle" && (
          <p className="muted small-caption">
            <strong>Start Run</strong> kicks off the pipeline below — connect →
            read repo → generate plan → assign &amp; score risk → pause for your
            review → push to ADO. It runs in the background and this panel
            updates live, so you can watch each step. Without a valid ADO PAT
            (demo mode) the plan is still generated end-to-end; only the final
            push to Azure DevOps is simulated — nothing is written to ADO.
          </p>
        )}

        <div className="row">
          <button
            type="button"
            className="btn btn-primary"
            onClick={handleStart}
            disabled={isRunInProgress}
          >
            {isRunInProgress ? "Run in progress…" : "Start Run"}
          </button>
          {runId && (
            <button
              type="button"
              className="btn btn-secondary"
              onClick={handleReset}
            >
              Start over
            </button>
          )}
          <span className="status-text">
            Status: <strong>{status}</strong>
          </span>
        </div>

        {status === "failed" && (
          <div className="banner banner-danger">
            <strong>Run failed.</strong>
            <p>
              The run stopped unexpectedly{error ? `: ${error}` : "."} Click{" "}
              <strong>Start over</strong>, then <strong>Start Run</strong> to try
              again.
            </p>
          </div>
        )}

        {runId && (
          <div className="meta-row">
            {repoMode && <span className="tag">repo mode: {repoMode}</span>}
            {teamCount !== null && (
              <span className="tag">team size: {teamCount}</span>
            )}
          </div>
        )}

        {runId && (
          <div className="pipeline">
            <h3>What's happening</h3>
            <ol className="pipeline-steps">
              {PIPELINE_STAGES.map((stage, idx) => {
                const state = stageStates[idx];
                const note = stageStatusLabel(state);
                return (
                  <li
                    key={stage.key}
                    className={`pipeline-step pipeline-step-${state}`}
                  >
                    <span className="pipeline-icon" aria-hidden="true">
                      {STAGE_ICONS[state]}
                    </span>
                    <span className="pipeline-body">
                      <span className="pipeline-label">
                        {stage.label}
                        {note && <span className="pipeline-note">{note}</span>}
                      </span>
                      <span className="pipeline-hint">{stage.hint}</span>
                    </span>
                  </li>
                );
              })}
            </ol>
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

      {!isBlocked && planDocument && (
        <section className="card">
          <div className="doc-header">
            <h2>Implementation plan document</h2>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={handleDownloadDocument}
            >
              Download .md
            </button>
          </div>
          <p className="muted small-caption">
            AI-generated — verify before relying on this.
          </p>
          <div className="markdown-body">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {planDocument}
            </ReactMarkdown>
          </div>
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
