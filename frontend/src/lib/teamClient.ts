/**
 * Typed fetch wrappers around Plan 02-02's FastAPI /team CRUD routes.
 *
 * Mirrors runClient.ts's pattern exactly: relative-path `fetch` calls
 * (`/team`, `/team/{id}`) so Vite's dev-server proxy forwards them to the
 * backend without any CORS setup, and a TeamMember interface that mirrors
 * backend/app/models/team.py's TeamMember Pydantic model field-for-field.
 *
 * The roster is independent of any run — these calls never touch /runs.
 */

export interface TeamMember {
  id: string | null;
  name: string;
  email: string;
  designation: string;
  skills: string;
  experience_level: "junior" | "mid" | "senior" | "lead";
}

async function parseTeamMemberResponse(res: Response): Promise<TeamMember> {
  if (!res.ok) {
    throw new Error(`Request failed with status ${res.status}`);
  }
  return (await res.json()) as TeamMember;
}

export async function listMembers(): Promise<TeamMember[]> {
  const res = await fetch("/team");
  if (!res.ok) {
    throw new Error(`Request failed with status ${res.status}`);
  }
  return (await res.json()) as TeamMember[];
}

export async function createMember(
  member: Omit<TeamMember, "id">,
): Promise<TeamMember> {
  const res = await fetch("/team", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(member),
  });
  return parseTeamMemberResponse(res);
}

export async function updateMember(
  id: string,
  member: Omit<TeamMember, "id">,
): Promise<TeamMember> {
  const res = await fetch(`/team/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(member),
  });
  return parseTeamMemberResponse(res);
}

export async function deleteMember(id: string): Promise<void> {
  const res = await fetch(`/team/${id}`, { method: "DELETE" });
  if (!res.ok) {
    throw new Error(`Request failed with status ${res.status}`);
  }
}
