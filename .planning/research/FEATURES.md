# Feature Research

**Domain:** AI-assisted project planning / sprint planning / developer onboarding (connecting ADO + GitHub)
**Researched:** 2026-07-09
**Confidence:** MEDIUM

Confidence is MEDIUM overall: the *category* (AI work breakdown, AI risk flags, AI codebase onboarding, diff-preview chat editing, AI-assisted work-item creation) is well established across Jira, Linear, ClickUp, Asana, GitHub Copilot, and dedicated codebase-RAG tools (Bloop, Greptile, Cursor @codebase), verified via WebSearch across multiple independent sources (see Sources). No single competitor combines all five pieces this project combines (repo-aware planning + skill/load assignment + deterministic risk + chat-diff edit + ADO push), so the *combination* is the differentiator, not any individual piece — that combination claim is inferred, not directly sourced.

## Feature Landscape

### Table Stakes (Users Expect These)

For a demo audience of engineering leads who already use Jira/Linear/Azure Boards and have seen GitHub Copilot Edits or Cursor, these are the features whose absence makes the demo feel broken or behind current expectations.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Connect to ADO + GitHub (config-based) | Every AI-PM tool (Jira AI, TachyonGPT, Copilot4DevOps) starts by connecting to the org's actual tracker; a tool that only works in a sandbox feels like a toy | LOW | Already scoped as single shared PAT, no OAuth — this is the cheapest version of "connect," appropriate for 2-day build |
| Team roster with skills/experience | Every skill-matching feature (ClickUp Intelligent Task Assigning, Linear Triage Intelligence) is built on structured profile data; without it, "skill-aware assignment" has nothing to reason over | LOW | Simple form/CRUD; no need for org-chart import or SSO-based directory lookup |
| Epic → task breakdown | This is the single most common "AI PM" feature across the market (Jira AI work breakdown, TachyonGPT, Copilot4DevOps bulk creation) — a planning tool that can't decompose an epic isn't a planning tool | MEDIUM | LLM call with structured output (JSON schema); the "well-formed hierarchy" part (parent/child correctness) is the fiddly bit, not the LLM call itself |
| Per-task estimate (hours/days) | Every sprint-planning tool (Monday dev, Jira, Asana) surfaces effort estimates next to tasks; missing estimates makes "load balancing" impossible to demo credibly | LOW-MEDIUM | LLM-generated estimate is fine for MVP; no need for historical-velocity-based estimation (that's how Monday/Jira do it "for real" but requires historical data this MVP doesn't have) |
| Task tagged with required skill | Precondition for any assignment logic; without it, "suggested assignee" is just round-robin | LOW | Just another structured field on the LLM's task-generation output |
| Suggested assignee per task | This is the headline feature of ClickUp Intelligent Task Assigning and Linear Triage Intelligence — "who should do this" is expected, not novel | MEDIUM | Straightforward skill-match scoring function; complexity is in combining skill-match + load (see Differentiators) |
| Editable plan before commit | Every competitor (Jira AI work breakdown, GitHub Copilot Edits) lets you accept/edit/decline suggestions rather than silently applying them — un-editable AI output is broadly considered untrustworthy | LOW-MEDIUM | Direct in-UI edit (change assignee/estimate/task text) is a standard editable table/form; low complexity if plan is just state in React |
| Push to tracker as real work items | The entire point of TachyonGPT, Copilot4DevOps, and AI Work Item Assistant is closing the loop into the tracker — an AI plan that stays in a chat window and never becomes a ticket is a non-starter for an engineering-lead demo | MEDIUM | ADO REST API (Work Items API) is well documented; complexity is mapping epic/task hierarchy + fields (assignee, estimate) correctly, and doing it in bulk without partial-failure headaches |
| Basic "why" for AI suggestions | Explainability is called out repeatedly (Linear Triage Intelligence explicitly explains its suggestions; AI risk-scoring literature stresses explainability for trust) — an unexplained AI number reads as a black box | LOW | One extra LLM-generated sentence per flagged risk; already in scope as "AI-written explanation" |

### Differentiators (Competitive Advantage)

These are not standard in any single competitor product researched. They are where this MVP's demo should spend its "wow" budget.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Skill-based auto-assignment **combined with current load** | Competitors do skill-matching (ClickUp) or capacity/workload views (Asana) but rarely combine "who has the right skill AND has room" into one automatic suggestion in the same planning pass — this is the single most concrete "AI did the PM's job" moment in the demo | MEDIUM-HIGH | Needs: (1) skill-match score per task/person, (2) a load number per person (sum of hours already assigned — from ADO if brownfield project already has items, or just from this run's plan if greenfield), (3) a combining function (e.g., weighted score = skill_match − load_penalty). For 2 days: keep it a simple deterministic formula, not an optimizer/solver (no linear programming, no simulated annealing) — greedy assignment in task order is sufficient and demoable |
| Deterministic risk score + AI-only-explains (not AI-scores) | Directly addresses a known trust gap in AI risk tooling — sources note "explainability is essential for building trust" and that deterministic rules should sit *under* the AI layer, not be replaced by it. Most competitor "AI risk flags" (Jira AI, sprint-risk blogs) are opaque LLM judgments with no deterministic backbone, which is a differentiator to call out explicitly in the demo narrative ("the number is real, the sentence is generated") | LOW-MEDIUM | The scoring itself is simple arithmetic (e.g., gap = required-skill count with zero/low-experience coverage, or overallocation delta) — genuinely low complexity. The one LLM call to phrase it is trivial. This is a cheap feature that reads as sophisticated because of the deterministic/generative split, not because the math is hard |
| Codebase-RAG onboarding summary (brownfield) | This is table stakes *in the standalone codebase-onboarding tool category* (Bloop, Greptile, Cursor @codebase, "Onboard") but a genuine differentiator *inside a planning tool* — no mainstream PM tool ingests the actual repo to inform task generation and give a human-readable "here's what exists" briefing before planning starts | HIGH | Requires: repo clone/fetch, chunking, embedding (NVIDIA embeddings), vector store, retrieval, summary generation. This is the highest-complexity item in the whole feature set for a 2-day build — budget carefully. Greenfield-first demo strategy is the correct hedge: it proves the flow without requiring this to be flawless on day 1 |
| Plan editing via LLM chat with diff preview before accept | Chat-driven edits exist in dev tools (GitHub Copilot Edits, Cursor) but essentially nowhere in PM/planning tools researched — bringing "diff review UX" from code editors into a project-plan context is novel for this domain | MEDIUM-HIGH | The diff-preview *pattern* is well-proven (red/green, accept/reject) in code editors, so the UX is not novel to invent — but plan diffs (task added/removed/reassigned/re-estimated) need a bespoke diff renderer since it's structured data, not text. Complexity is in (a) LLM tool-calling to propose structured plan mutations, (b) computing + rendering the diff, (c) accept/reject wiring back into plan state |
| One-way push into ADO with correct assignee/estimate mapping | Not differentiating vs. TachyonGPT/Copilot4DevOps on the "push tasks" mechanic itself, but differentiating in that the push happens automatically as the terminal step of an AI-authored, human-approved plan (closed loop) rather than a standalone "generate work item text" utility | MEDIUM | REST calls are the easy part; correctly mapping epic→task parent/child links, Original Estimate field, and AssignedTo (by email/ID) is where bugs live. Treat as differentiator only because of *when* it fires (closing the loop), not because the API work itself is novel |
| LangGraph interrupt/resume for human-in-the-loop review | Not a "feature" a user sees directly, but it's what makes edit-and-resume (direct edit or chat edit) feel like one coherent flow instead of a page reload / new session — worth naming because it's an architectural differentiator that enables the UX differentiators above | MEDIUM | This is plumbing, but plumbing that determines whether "edit the plan and continue where you left off" is smooth or janky. Already decided in PROJECT.md; flagged here because FEATURES and ARCHITECTURE overlap on this point |

### Anti-Features (Commonly Requested, Often Problematic)

Features that appear in mature competitor products or that a stakeholder might ask for mid-demo, but that would blow the 2-day budget or add risk without adding proof-of-concept value. Some of these are already explicitly out of scope in PROJECT.md; included here for completeness with the "why problematic" reasoning, plus a few not yet called out.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|------------------|-------------|
| Two-way ADO sync (read back status/changes) | Feels "incomplete" without it — real tools like Unito emphasize 2-way sync as a selling point | Reconciliation logic (conflict resolution, field-mapping drift, webhook or polling infra) is a multi-week problem on its own; irrelevant to proving the planning flow | One-way push only (already scoped); mention verbally that sync-back is "next" |
| RBAC / multi-user auth / SSO | Every enterprise tool (Jira, ADO itself) has it; a demo viewer may ask "how do permissions work" | Auth/identity is orthogonal complexity that eats a large fraction of a 2-day budget for zero demo value (single lead, local use) | Single shared PAT, no login (already scoped) |
| Multi-repo / multi-project support | Real orgs have many repos; feels limiting to hardcode one | Multiplies the RAG ingestion, planning-context, and push-mapping surface area; doesn't change what's being proven | One ADO project + one GitHub repo per run (already scoped) |
| Optimizer/solver-based assignment (e.g., linear programming for optimal load balance) | "AI project planning" superficially sounds like a scheduling-optimization problem, and load-balancing literature (round robin, token-based, LP) suggests real algorithms exist | Massive overkill for a team of a handful of people and a couple dozen tasks; adds a dependency (solver library) and tuning risk for a result a simple greedy/weighted-score assignment achieves just as convincingly in a demo | Greedy skill-match + load-penalty scoring, assign in task order (see Differentiators row above) |
| Historical-velocity-based estimation | Jira/Monday tout "estimates based on historical data" as a mature feature | This MVP has no historical sprint data to train on (greenfield project, or brownfield repo with no prior ADO history in this tool) — building a velocity model would be fabricating rigor | LLM-generated estimate directly from task description + complexity heuristics; label it clearly as an AI estimate, not a data-driven one |
| Continuous/real-time re-planning as code changes | AI coding assistants make "always up to date" feel expected | Requires webhooks/polling on the repo and re-running RAG + planning on every commit — a live system, not a plan-once tool | Planning is a discrete, triggered flow (connect → read → generate → approve → push); re-running is a manual "generate again" action, not automatic |
| Fine-grained diff at the field level for every possible plan mutation (rich merge/undo history) | Code-editor diff UX (Zed, VS Code Copilot Edits) supports chunk-level accept/reject and multi-step undo | Building a general-purpose structured-diff/undo engine is its own project; the plan object is small enough that a full "before/after" comparison per chat turn is sufficient | Diff preview at the plan-object level (tasks added/removed/changed) with a single accept/reject per chat turn, not per-field granularity |
| Full org directory / SSO-based skill import (e.g., pull skills from GitHub contribution history or ADO history automatically) | Would feel "smarter" than manual entry — sources note repo-aware tools can infer expertise from commit history | Inferring skills from commit history is itself a research problem (attribution, staleness, false signals) and not needed to prove the core flow; manual entry is fast and controllable for a demo | Manual team entry (name/designation/skills/experience) — already scoped |
| Notifications / Slack / Teams integration on push | Every mature PM tool announces work-item creation somewhere | Pure surface-area addition with no bearing on whether the core planning flow works | Skip entirely; the ADO board itself is the "notification" (items just appear) |

## Feature Dependencies

```
Team roster (skills/experience)
    └──requires──> Skill-tagged tasks (epic breakdown)
                       └──requires──> Skill-based assignee suggestion
                                          └──enhances──> Load-aware assignment (needs current load per person)
                                                             └──requires──> Reading existing ADO assignments (brownfield)
                                                                                OR running plan's own running total (greenfield, first run)

Skill-tagged tasks + Team roster
    └──requires──> Deterministic risk score (skill-coverage gap calculation)
                       └──enhances──> AI-written risk explanation (LLM call over the deterministic score)

Repo connection (GitHub)
    └──branches──> Greenfield: read docs ──feeds──> Epic/task generation
    └──branches──> Brownfield: codebase RAG ──produces──> Onboarding summary ──feeds──> Epic/task generation

Editable plan (direct edit)
    └──shares state with──> Editable plan (LLM chat + diff preview)
                                 └──requires──> LangGraph interrupt/resume (human-in-the-loop pause point)

Approved plan (post-edit-loop)
    └──requires──> One-way ADO push (epics→tasks with assignee + estimate mapped)
```

### Dependency Notes

- **Load-aware assignment requires reading current load, which has two different sources depending on path:** For a **brownfield** project, "current load" should ideally reflect real existing ADO work-item assignments (pull existing items assigned to each team member). For a **greenfield** project, there is no prior ADO history to read, so "load" can only be the running total *within this plan generation* (assign task 1, increment that person's load, then assign task 2 accounting for the new total). Building the "read existing ADO assignments" path adds an extra ADO API round-trip and mapping step — for a 2-day MVP, it is reasonable to implement load-awareness only as within-plan running total for both paths, and treat "pull real existing ADO workload" as a stretch enhancement, not a blocker. Flag this explicitly to whoever scopes phases: the PROJECT.md description ("who is already assigned work") implies real ADO load-reading, which is the higher-complexity interpretation.
- **Deterministic risk score requires skill-tagged tasks and team roster to exist first** — it's a pure function over (required skills across all tasks) vs. (skills present in team), so it cannot be built or demoed before task generation and team entry are working.
- **AI-written risk explanation enhances but does not gate the risk score** — the deterministic number should render even if the LLM explanation call fails or is slow; don't make the explanation a hard dependency of showing the risk flag at all (resilience note, not a feature per se).
- **Direct edit and chat edit should share the same underlying plan-state mutation path** — if the diff-preview/accept flow for chat edits and the direct-edit form both funnel into the same "apply mutation to plan state" function, it avoids building two divergent edit systems in a 2-day window.
- **Onboarding summary (brownfield) and epic/task generation both consume the same RAG index** — building retrieval once and using it for both the summary and as planning context avoids redundant embedding/retrieval work.
- **ADO push requires the plan to be in its final, human-approved state** — it should only be reachable after the edit loop is explicitly exited (approval action), not auto-triggered, since it's the one irreversible/external-effect step in the whole flow.

## MVP Definition

### Launch With (v1 — the 2-day build)

- [ ] Connect ADO project + GitHub repo via config (shared PAT) — required to have any real data to plan against
- [ ] Team roster entry (name, designation, skills, experience) — required input for all downstream skill/load logic
- [ ] Greenfield doc-read path — primary demo path per PROJECT.md; lower complexity than brownfield RAG, de-risks the core flow
- [ ] Epic → task breakdown with skill tag + hours/days estimate — the visible "AI planning" moment
- [ ] Skill-match + within-plan-load-aware assignee suggestion (greedy scoring, not an optimizer) — the headline differentiator; keep the algorithm simple
- [ ] Deterministic skill-coverage risk score + one-sentence AI explanation — cheap to build, high trust payoff
- [ ] Direct plan editing (edit task/assignee/estimate in the UI) — table stakes; also the fallback if chat editing runs short on time
- [ ] LLM chat edit with diff preview + accept — the second differentiator; scope the diff to plan-object level, not field-level granularity
- [ ] One-way push to ADO (epics + tasks, assignee, estimate mapped) — the flow's payoff moment; without it nothing was proven end-to-end

### Add After Validation (v1.x)

- [ ] Brownfield codebase RAG + onboarding summary — keep as a supported path (per PROJECT.md) but treat as the first thing to cut/simplify if day-1 runs long, since greenfield alone proves the flow
- [ ] Reading real existing ADO workload (not just within-plan running total) for load-aware assignment — upgrade once the simpler running-total version is proven
- [ ] Field-level diff granularity in chat-edit review — add once basic accept/reject-whole-diff is working and there's time left

### Future Consideration (v2+)

- [ ] Two-way ADO sync — explicitly out of scope per PROJECT.md; large surface area
- [ ] RBAC / multi-user / auth — explicitly out of scope per PROJECT.md
- [ ] Multi-repo support — explicitly out of scope per PROJECT.md
- [ ] Optimizer-based assignment (solver/LP) — defer until greedy scoring is proven insufficient in practice
- [ ] Historical-velocity estimation — defer until there's actual historical data (multiple runs/sprints) to learn from
- [ ] Skill inference from commit history / GitHub activity — interesting but a research project in itself

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Connect ADO + GitHub (config) | HIGH | LOW | P1 |
| Team roster entry | HIGH | LOW | P1 |
| Greenfield doc-read path | HIGH | LOW-MEDIUM | P1 |
| Epic→task breakdown (skill+estimate tagged) | HIGH | MEDIUM | P1 |
| Skill-match + load-aware assignment (greedy) | HIGH | MEDIUM-HIGH | P1 |
| Deterministic risk score + AI explanation | HIGH | LOW-MEDIUM | P1 |
| Direct plan edit | HIGH | LOW-MEDIUM | P1 |
| Chat edit with diff preview | MEDIUM-HIGH | MEDIUM-HIGH | P1 |
| One-way ADO push | HIGH | MEDIUM | P1 |
| LangGraph interrupt/resume plumbing | MEDIUM (invisible but enabling) | MEDIUM | P1 |
| Brownfield codebase RAG + onboarding summary | MEDIUM-HIGH | HIGH | P2 |
| Real ADO-workload-based load reading | MEDIUM | MEDIUM | P2 |
| Field-level diff granularity | LOW | MEDIUM | P3 |
| Optimizer/solver assignment | LOW (for this scale) | HIGH | P3 (skip) |
| Historical-velocity estimation | LOW (no data yet) | MEDIUM-HIGH | P3 (skip) |

**Priority key:**
- P1: Must have for the 2-day demo
- P2: Should have if time allows; safe to cut without breaking the core story
- P3: Nice to have, future consideration — actively avoid in the 2-day window

## Competitor Feature Analysis

| Feature | Jira AI / Atlassian Intelligence | Linear (Triage Intelligence) / ClickUp / TachyonGPT | Our Approach |
|---------|-----------------------------------|------------------------------------------------------|--------------|
| Epic → task breakdown | Suggests child work items from a parent item; accept/edit/decline per item | ClickUp Intelligent Task Assigning assigns by expertise/availability/workload; TachyonGPT auto-generates epics/features/stories/tasks in ADO directly | Same core capability (LLM-generated hierarchy), but ours is driven by an actual repo read (docs or codebase), not just a manually typed epic title |
| Skill/assignee suggestion | Not skill-explicit; more activity/pattern based | Linear explains *why* it suggested an assignee (historical pattern); ClickUp explicitly factors expertise + availability + workload | Ours explicitly combines structured skill tags + explicit team skill/experience data + within-plan load — more structured/explainable than pattern-based suggestion, but simpler (no historical pattern learning) |
| Risk flags | AI risk/backlog analysis exists in Jira AI but is described as opaque LLM judgment, no clear deterministic backbone in sources found | Not clearly present as a named feature in researched tools | Ours is the clearest differentiator here: deterministic skill-gap math + LLM only for the explanation sentence — directly addresses the explainability/trust gap noted across risk-AI sources |
| Codebase-aware planning | None found — Jira/Linear/ClickUp/Asana are tracker-native, not repo-aware | Separate category entirely (Bloop, Greptile, Cursor @codebase, "Onboard") — these tools understand code but don't feed a project plan | Ours is the only researched approach that pipes repo/codebase understanding directly into task generation — genuine differentiator, but also the highest-complexity item to build in 2 days |
| Chat-based plan editing with diff review | Not found in PM tools; ubiquitous in code editors (Copilot Edits, Cursor, Zed) | Not found in PM tools | Ours imports the code-editor diff-review pattern into a plan-editing context — proven UX pattern, novel application |
| Push to tracker | TachyonGPT and Copilot4DevOps push directly into ADO as their core mechanic | N/A (Linear/ClickUp are trackers themselves, not external planners) | Same mechanic (ADO Work Items REST API), but ours is the terminal step of a longer AI-authored + human-approved pipeline, not a standalone "generate ticket text" utility |

## Sources

- [The Best AI-Assisted Sprint Planning Tools for Agile Teams | Zenhub Blog](https://www.zenhub.com/blog-posts/the-7-best-ai-assisted-sprint-planning-tools-for-agile-teams-in-2025) — MEDIUM confidence (WebSearch, vendor blog)
- [AI Sprint Planning Tools: Jira, Linear, GitHub & Beyond | Augment Code](https://www.augmentcode.com/tools/ai-sprint-planning-tools-jira-linear-github) — MEDIUM confidence
- [Onboarding to a 'legacy' codebase with the help of AI — Martin Fowler](https://martinfowler.com/articles/exploring-gen-ai/09-ai-help-onboarding-codebase.html) — MEDIUM-HIGH confidence (respected engineering source)
- [7 AI Tools for Codebase Onboarding and Understanding — Security Boulevard](https://securityboulevard.com/2026/06/7-ai-tools-for-codebase-onboarding-and-understanding/) — MEDIUM confidence
- [How to Use AI to Onboard Into a Codebase Faster](https://newsletter.eng-leadership.com/p/how-to-use-ai-to-onboard-into-a-codebase) — MEDIUM confidence
- [AI Agents in TPRM: Deterministic Automation, ML Intelligence, and Generative AI Explained — ProcessUnity](https://www.processunity.com/resources/blogs/ai-agents-tprm-types/) — MEDIUM confidence, supports deterministic-layer-under-AI pattern
- [Using AI for risk assessment? Be aware of probabilistic drift](https://resilienceforward.com/using-ai-for-risk-assessment-be-aware-of-the-issue-of-probabilistic-drift/) — LOW-MEDIUM confidence (single blog), used only to corroborate the explainability/trust theme, not as sole basis
- [Introducing TachyonGPT: An AI Copilot for Generating Work Items in Azure DevOps — Medium/Neudesic](https://medium.com/neudesic-innovation/introducing-tachyongpt-an-ai-copilot-for-generating-work-items-in-azure-devops-5a9ce1cbfe72) — MEDIUM confidence
- [Copilot4DevOps — AI chat bulk work item creation](https://copilot4devops.com/detailed-guide-on-azure-devops-work-items/) — MEDIUM confidence
- [AI Work Item Assistant in Azure DevOps Boards — VS Marketplace](https://marketplace.visualstudio.com/items?itemName=MS-DAW-TCA.workitem-assistant-extension-external) — MEDIUM-HIGH confidence (official Microsoft extension listing)
- [Review AI-generated code edits — VS Code Docs](https://code.visualstudio.com/docs/copilot/chat/review-code-edits) — HIGH confidence (official docs)
- [GitHub Copilot Edits in Visual Studio — Microsoft Learn](https://learn.microsoft.com/en-us/visualstudio/ide/copilot-edits?view=visualstudio) — HIGH confidence (official docs)
- [Get out of tickets and into your work faster with AI in Jira — Atlassian](https://www.atlassian.com/blog/artificial-intelligence/ai-jira-issues) — HIGH confidence (official vendor)
- Not independently verified for this project's exact feature *combination* (repo-aware planning + skill/load assignment + deterministic risk + chat-diff editing + ADO push in one flow) — no single product matches this bundle in the tools surfaced; treat the "differentiator" claims as reasoned synthesis from adjacent-category evidence, not a direct competitor match.

---
*Feature research for: AI-assisted project planning & onboarding dashboard (ADO + GitHub)*
*Researched: 2026-07-09*
