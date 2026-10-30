import type { Step } from "../api/types";
import { stepLabel } from "../lib";

const SHOWN = new Set(["understand", "retrieve", "generate", "verify", "correct", "plan", "clarify", "synthesize"]);

/** Renders ONLY steps the backend actually recorded for this request. */
export function StepList({ steps }: { steps?: Step[] }) {
  const shown = (steps ?? []).filter((s) => SHOWN.has(s.name) || s.name.startsWith("tool:"));
  if (!shown.length) return null;
  return (
    <details className="steps">
      <summary>How this answer was made ({shown.length} steps)</summary>
      <ol>
        {shown.map((s, i) => (
          <li key={i} className={s.status !== "ok" ? "step-bad" : undefined}>
            {stepLabel(s.name)}{s.status !== "ok" ? ` (${s.status})` : ""}
          </li>
        ))}
      </ol>
    </details>
  );
}
