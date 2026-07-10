/**
 * Renders a unified diff string (as produced by the backend's /runs/{id}/edit
 * endpoint) with per-line coloring. No diff-computation happens client-side —
 * the backend is the source of truth for the diff text; this component only
 * presents it.
 */
export default function DiffView({ diff }: { diff: string }) {
  const lines = diff.split("\n");

  function lineClass(line: string): string {
    if (line.startsWith("+++") || line.startsWith("---")) return "diff-line diff-file";
    if (line.startsWith("+")) return "diff-line diff-add";
    if (line.startsWith("-")) return "diff-line diff-remove";
    if (line.startsWith("@@")) return "diff-line diff-hunk";
    return "diff-line";
  }

  return (
    <pre className="diff-block">
      {lines.map((line, i) => (
        <div key={i} className={lineClass(line)}>
          {line.length > 0 ? line : " "}
        </div>
      ))}
    </pre>
  );
}
