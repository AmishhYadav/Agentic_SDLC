import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  askCodebase,
  getCodebaseStatus,
  reindexCodebase,
  type CodebaseSource,
  type CodebaseStatus,
} from "../lib/codebaseClient";

interface ChatTurn {
  question: string;
  answer: string | null; // null while the answer is in flight
  sources: CodebaseSource[];
}

const EXAMPLE_QUESTIONS = [
  "Where is the risk score computed?",
  "How does the human-review interrupt work?",
  "What does push_to_ado do in demo mode?",
];

/**
 * Step 3: a retrieval-augmented chat over the pre-indexed codebase. The index
 * is built once (script or the Build/Rebuild button) and persisted server-side;
 * each question is embedded, matched against the index, and answered by the LLM
 * grounded in the retrieved files (falling back to listing the relevant files
 * when the LLM is unavailable).
 */
export default function CodebasePage() {
  const [status, setStatus] = useState<CodebaseStatus | null>(null);
  const [repo, setRepo] = useState("");
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const [reindexing, setReindexing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const threadRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    getCodebaseStatus()
      .then((s) => {
        setStatus(s);
        // Pre-fill the repo box if the current index came from a GitHub repo
        // ("owner/name" — not a local filesystem path).
        if (s.root && !s.root.startsWith("/") && s.root.includes("/")) {
          setRepo(s.root);
        }
      })
      .catch((err) => setError(err instanceof Error ? err.message : String(err)));
  }, []);

  useEffect(() => {
    // Keep the newest turn in view as the conversation grows.
    threadRef.current?.scrollTo({ top: threadRef.current.scrollHeight });
  }, [turns]);

  async function handleAsk() {
    const q = question.trim();
    if (!q || asking) return;
    setError(null);
    setAsking(true);
    setQuestion("");
    const idx = turns.length;
    setTurns((prev) => [...prev, { question: q, answer: null, sources: [] }]);
    try {
      const res = await askCodebase(q);
      setTurns((prev) =>
        prev.map((t, i) =>
          i === idx ? { ...t, answer: res.answer, sources: res.sources } : t,
        ),
      );
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setTurns((prev) =>
        prev.map((t, i) =>
          i === idx ? { ...t, answer: `Error: ${message}` } : t,
        ),
      );
    } finally {
      setAsking(false);
    }
  }

  async function handleReindex() {
    setError(null);
    setReindexing(true);
    try {
      const next = await reindexCodebase(repo);
      setStatus(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setReindexing(false);
    }
  }

  const indexed = status?.indexed === true;

  return (
    <div className="page">
      <h1>Ask the codebase</h1>
      <p className="step-hint">
        Step 3 of 3 — ask questions about this project's code. Answers are
        grounded in a pre-built index of the repository and cite the files they
        draw from.
      </p>

      {error && <p className="error-text">Error: {error}</p>}

      <section className="card">
        <h2>Index</h2>
        <p className="muted small-caption">
          Enter a GitHub repo to clone, embed, and chat with. Leave blank to use
          the configured source (env <code>GITHUB_REPO</code>, or this project).
          Building a large repo can take a bit — for a snappy demo, pre-build it
          with <code>scripts/build_codebase_index.py</code>.
        </p>
        <div className="row">
          <input
            className="text-input"
            placeholder="owner/repo  (e.g. octocat/Hello-World)"
            value={repo}
            onChange={(e) => setRepo(e.target.value)}
            disabled={reindexing}
          />
          <button
            type="button"
            className="btn btn-primary"
            onClick={handleReindex}
            disabled={reindexing}
          >
            {reindexing
              ? "Building…"
              : indexed
                ? "Rebuild index"
                : "Build index"}
          </button>
        </div>
        {indexed ? (
          <div className="meta-row">
            {status?.root && <span className="tag">source: {status.root}</span>}
            <span className="tag">{status?.file_count} files</span>
            <span className="tag">{status?.chunk_count} chunks</span>
            <span className="tag">embedder: {status?.embedder}</span>
            {status?.built_at && (
              <span className="tag">built {status.built_at.slice(0, 16)}</span>
            )}
          </div>
        ) : (
          <p className="muted">No index yet — build one to start asking.</p>
        )}
      </section>

      <section className="card">
        <h2>Chat</h2>
        <p className="muted small-caption">
          AI-generated answers — verify against the cited files. Examples:{" "}
          {EXAMPLE_QUESTIONS.join(" · ")}
        </p>

        {turns.length > 0 && (
          <div className="chat-thread" ref={threadRef}>
            {turns.map((turn, i) => (
              <div key={i} className="chat-turn">
                <div className="chat-msg chat-msg-user">
                  <span className="chat-role">You</span>
                  <div className="chat-text">{turn.question}</div>
                </div>
                <div className="chat-msg chat-msg-bot">
                  <span className="chat-role">Codebase</span>
                  <div className="chat-text">
                    {turn.answer === null ? (
                      <span className="muted">Searching the codebase…</span>
                    ) : (
                      <div className="markdown-body">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                          {turn.answer}
                        </ReactMarkdown>
                      </div>
                    )}
                    {turn.sources.length > 0 && (
                      <div className="chat-sources">
                        {turn.sources.map((s) => (
                          <span key={s.path} className="source-chip mono">
                            {s.path}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        <div className="row">
          <input
            className="text-input"
            placeholder={
              indexed
                ? "e.g. where is the plan JSON schema defined?"
                : "Build the index first to start asking"
            }
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleAsk();
            }}
            disabled={!indexed || asking}
          />
          <button
            type="button"
            className="btn btn-primary"
            onClick={handleAsk}
            disabled={!indexed || asking || !question.trim()}
          >
            {asking ? "Asking…" : "Send"}
          </button>
        </div>
      </section>
    </div>
  );
}
