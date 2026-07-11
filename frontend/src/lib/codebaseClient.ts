/**
 * Typed fetch wrappers around the /codebase routes (codebase RAG chat).
 *
 * Same relative-path convention as runClient/teamClient so Vite's dev proxy
 * forwards to the backend without CORS setup.
 */

export interface CodebaseStatus {
  indexed: boolean;
  embedder?: string;
  file_count?: number;
  chunk_count?: number;
  languages?: Record<string, number>;
  built_at?: string;
  root?: string;
}

export interface CodebaseSource {
  path: string;
  language: string;
}

export interface AskResponse {
  answer: string;
  sources: CodebaseSource[];
}

export async function getCodebaseStatus(): Promise<CodebaseStatus> {
  const res = await fetch("/codebase/status");
  if (!res.ok) {
    throw new Error(`Request failed with status ${res.status}`);
  }
  return (await res.json()) as CodebaseStatus;
}

export async function askCodebase(question: string): Promise<AskResponse> {
  const res = await fetch("/codebase/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
  if (!res.ok) {
    throw new Error(`Request failed with status ${res.status}`);
  }
  return (await res.json()) as AskResponse;
}

export async function reindexCodebase(
  githubRepo?: string,
): Promise<CodebaseStatus> {
  const res = await fetch("/codebase/reindex", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ github_repo: githubRepo?.trim() || null }),
  });
  const data = (await res.json()) as CodebaseStatus & { error?: string };
  if (!res.ok) {
    throw new Error(data.error || `Request failed with status ${res.status}`);
  }
  return data;
}
