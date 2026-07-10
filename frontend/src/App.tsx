import { useState } from "react";
import RunPage from "./pages/RunPage";
import TeamPage from "./pages/TeamPage";

/**
 * No routing library in this MVP (D-01/CONTEXT.md discretion: no config
 * form, no router set up in Phase 1) — a minimal in-app tab switch is
 * sufficient for a 2-day MVP with two pages.
 */
function App() {
  const [activeTab, setActiveTab] = useState<"run" | "team">("run");

  return (
    <div>
      <nav className="tab-nav">
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
      </nav>
      {activeTab === "run" ? <RunPage /> : <TeamPage />}
    </div>
  );
}

export default App;
