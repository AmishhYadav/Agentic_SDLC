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
      <nav>
        <button type="button" onClick={() => setActiveTab("run")}>
          Run
        </button>
        <button type="button" onClick={() => setActiveTab("team")}>
          Team
        </button>
      </nav>
      {activeTab === "run" ? <RunPage /> : <TeamPage />}
    </div>
  );
}

export default App;
