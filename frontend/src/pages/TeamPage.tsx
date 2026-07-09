import { useEffect, useState } from "react";
import {
  createMember,
  deleteMember,
  listMembers,
  updateMember,
  type TeamMember,
} from "../lib/teamClient";

type FormState = Omit<TeamMember, "id">;

const EMPTY_FORM: FormState = {
  name: "",
  email: "",
  designation: "",
  skills: "",
  experience_level: "mid",
};

/**
 * Demo-grade (unstyled, matching RunPage.tsx's minimalism) team roster page:
 * add/edit/remove team members before planning starts (TEAM-01/TEAM-02).
 * Fetches the list once on mount — roster changes are user-driven, not
 * async-graph-driven like RunPage, so no polling is needed.
 */
export default function TeamPage() {
  const [members, setMembers] = useState<TeamMember[]>([]);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  function refetch() {
    listMembers()
      .then(setMembers)
      .catch((err) => setError(err instanceof Error ? err.message : String(err)));
  }

  useEffect(() => {
    refetch();
  }, []);

  function updateFormField<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function handleAddOrSave() {
    setError(null);
    try {
      if (editingId) {
        await updateMember(editingId, form);
      } else {
        await createMember(form);
      }
      setForm(EMPTY_FORM);
      setEditingId(null);
      refetch();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  function handleEdit(member: TeamMember) {
    setEditingId(member.id);
    setForm({
      name: member.name,
      email: member.email,
      designation: member.designation,
      skills: member.skills,
      experience_level: member.experience_level,
    });
  }

  function handleCancelEdit() {
    setEditingId(null);
    setForm(EMPTY_FORM);
  }

  async function handleRemove(id: string | null) {
    if (!id) return;
    setError(null);
    try {
      await deleteMember(id);
      if (editingId === id) {
        handleCancelEdit();
      }
      refetch();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  return (
    <div>
      <h1>Team Roster</h1>

      {error && <p>Error: {error}</p>}

      <div>
        <h2>{editingId ? "Edit member" : "Add member"}</h2>
        <input
          placeholder="Name"
          value={form.name}
          onChange={(e) => updateFormField("name", e.target.value)}
        />
        <input
          placeholder="Email"
          value={form.email}
          onChange={(e) => updateFormField("email", e.target.value)}
        />
        <input
          placeholder="Designation"
          value={form.designation}
          onChange={(e) => updateFormField("designation", e.target.value)}
        />
        <input
          placeholder="Skills"
          value={form.skills}
          onChange={(e) => updateFormField("skills", e.target.value)}
        />
        <select
          value={form.experience_level}
          onChange={(e) =>
            updateFormField(
              "experience_level",
              e.target.value as FormState["experience_level"],
            )
          }
        >
          <option value="junior">junior</option>
          <option value="mid">mid</option>
          <option value="senior">senior</option>
          <option value="lead">lead</option>
        </select>
        <button type="button" onClick={handleAddOrSave}>
          {editingId ? "Save" : "Add"}
        </button>
        {editingId && (
          <button type="button" onClick={handleCancelEdit}>
            Cancel
          </button>
        )}
      </div>

      <div>
        <h2>Members</h2>
        <ul>
          {members.map((member) => (
            <li key={member.id}>
              {member.name} — {member.email} — {member.designation} —{" "}
              {member.skills} — {member.experience_level}{" "}
              <button type="button" onClick={() => handleEdit(member)}>
                Edit
              </button>
              <button type="button" onClick={() => handleRemove(member.id)}>
                Remove
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
