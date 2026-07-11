import { useState } from "react";
import CodebasePage from "./pages/CodebasePage";
import RunPage from "./pages/RunPage";
import TeamPage from "./pages/TeamPage";

/**
 * No routing library in this MVP (D-01/CONTEXT.md discretion: no config
 * form, no router set up in Phase 1) — a minimal in-app tab switch is
 * sufficient for a 2-day MVP with two pages.
 */
function App() {
  const [activeTab, setActiveTab] = useState<"run" | "team" | "codebase">(
    "team",
  );

  return (
    <div className="app">
      <header className="app-header">
        <div className="app-brand">
          <svg
            className="app-mark"
            viewBox="0 0 24 24"
            aria-hidden="true"
            focusable="false"
          >
            <g fill="currentColor">
              <rect x="10.7" y="1" width="2.6" height="22" rx="1.3" />
              <rect
                x="10.7"
                y="1"
                width="2.6"
                height="22"
                rx="1.3"
                transform="rotate(45 12 12)"
              />
              <rect
                x="10.7"
                y="1"
                width="2.6"
                height="22"
                rx="1.3"
                transform="rotate(90 12 12)"
              />
              <rect
                x="10.7"
                y="1"
                width="2.6"
                height="22"
                rx="1.3"
                transform="rotate(135 12 12)"
              />
            </g>
          </svg>
          <span className="app-brand-text">
            <span className="app-name">Project Planning &amp; Onboarding</span>
            <span className="app-tagline">
              Connect ADO + GitHub → skill-aware plan → assigned work items
            </span>
          </span>
        </div>
      </header>

      <nav className="tab-nav" aria-label="Workflow steps">
        <button
          type="button"
          className={activeTab === "team" ? "tab-btn tab-btn-active" : "tab-btn"}
          onClick={() => setActiveTab("team")}
        >
          1. Team
        </button>
        <button
          type="button"
          className={activeTab === "run" ? "tab-btn tab-btn-active" : "tab-btn"}
          onClick={() => setActiveTab("run")}
        >
          2. Run
        </button>
        <button
          type="button"
          className={
            activeTab === "codebase" ? "tab-btn tab-btn-active" : "tab-btn"
          }
          onClick={() => setActiveTab("codebase")}
        >
          3. Ask codebase
        </button>
      </nav>

      <main className="app-main">
        {activeTab === "run" && <RunPage />}
        {activeTab === "team" && <TeamPage />}
        {activeTab === "codebase" && <CodebasePage />}
      </main>
    </div>
  );
}

export default App;
