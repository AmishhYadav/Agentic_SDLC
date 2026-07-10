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
    <div className="page">
      <h1>Team</h1>
      <p className="step-hint">
        Step 1 of 2 — add your team members here so the plan generated on the
        Run tab can auto-assign skill-tagged tasks to real people.
      </p>

      {error && <p className="error-text">Error: {error}</p>}

      <section className="card">
        <h2>{editingId ? "Edit member" : "Add member"}</h2>
        <div className="form-grid">
          <input
            className="text-input"
            placeholder="Name"
            value={form.name}
            onChange={(e) => updateFormField("name", e.target.value)}
          />
          <input
            className="text-input"
            placeholder="Email"
            value={form.email}
            onChange={(e) => updateFormField("email", e.target.value)}
          />
          <input
            className="text-input"
            placeholder="Designation"
            value={form.designation}
            onChange={(e) => updateFormField("designation", e.target.value)}
          />
          <input
            className="text-input"
            placeholder="Skills"
            value={form.skills}
            onChange={(e) => updateFormField("skills", e.target.value)}
          />
          <select
            className="text-input"
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
        </div>
        <div className="row">
          <button type="button" className="btn btn-primary" onClick={handleAddOrSave}>
            {editingId ? "Save" : "Add"}
          </button>
          {editingId && (
            <button type="button" className="btn btn-secondary" onClick={handleCancelEdit}>
              Cancel
            </button>
          )}
        </div>
      </section>

      <section className="card">
        <h2>Members ({members.length})</h2>
        {members.length === 0 && <p className="muted">No team members yet.</p>}
        <ul className="member-list">
          {members.map((member) => (
            <li key={member.id} className="member-card">
              <div>
                <strong>{member.name}</strong>{" "}
                <span className="tag">{member.experience_level}</span>
                <div className="muted">
                  {member.email} · {member.designation}
                </div>
                <div className="muted">{member.skills}</div>
              </div>
              <div className="row">
                <button type="button" className="btn" onClick={() => handleEdit(member)}>
                  Edit
                </button>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => handleRemove(member.id)}
                >
                  Remove
                </button>
              </div>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
