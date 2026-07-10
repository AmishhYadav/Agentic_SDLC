"""Built-in sample project brief for DEMO_MODE greenfield planning.

Used only as a fallback by read_docs_greenfield when DEMO_MODE is on and no
real GitHub repo/docs are configured, so the plan/assign/risk/edit demo works
end-to-end with zero external connectivity. A real GITHUB_REPO with docs always
takes precedence; non-demo runs still honestly block on missing docs.

The headings/keywords below are deliberately spread across the skill taxonomy
(auth, api, frontend, database, devops, testing, docs) so the offline planner,
assignment, and risk scoring all produce a rich, demo-worthy result.
"""

SAMPLE_PROJECT_BRIEF = """# TaskFlow — Team Project Planning SaaS

TaskFlow is a lightweight SaaS that helps engineering teams plan projects,
assign work, and track delivery. This brief describes the first release.

## Authentication and Accounts
Users sign up with email and password, verify their email, and log in.
Support password reset and OAuth login with Google. Sessions use short-lived
access tokens plus refresh tokens.

## Core API
A REST API exposes projects, tasks, and assignments. Endpoints must be
documented and versioned. The API validates all input and returns consistent
error shapes. Rate limiting protects public endpoints.

## Web Frontend Dashboard
A responsive dashboard lists projects and their tasks in a board view. Users
can create tasks, drag them between columns, assign them to teammates, and
filter by assignee. The UI shows a per-person workload summary.

## Data Model and Storage
Persist users, projects, tasks, and assignments in a relational database with
migrations. Model task dependencies and estimates. Add indexes for the common
board and assignee queries.

## Integrations
Sync tasks to external issue trackers and post assignment updates to a team
chat channel via webhooks.

## Testing and Quality
Automated unit and integration tests cover the API and assignment logic.
Add end-to-end tests for the critical signup-to-task-assignment flow.

## Deployment and Operations
Containerize the services and deploy via a CI/CD pipeline. Add health checks,
structured logging, and basic metrics dashboards.

## Documentation
Write API reference docs and a short onboarding guide for new engineers.
"""
