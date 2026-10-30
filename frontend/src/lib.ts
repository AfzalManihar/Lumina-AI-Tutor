export const fmtDate = (iso?: string | null) => (iso ? new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" }) : "—");
export const fmtDateTime = (iso?: string | null) => (iso ? new Date(iso).toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "—");
export const fmtNum = (n: number) => n.toLocaleString("en-IN");
export const fmtBytes = (n: number) => (n < 1024 ? `${n} B` : n < 1048576 ? `${(n / 1024).toFixed(1)} KB` : `${(n / 1048576).toFixed(1)} MB`);
export const fmtPrice = (inr: number) => (inr === 0 ? "Free" : `₹${inr.toLocaleString("en-IN")}`);

/** Human labels for REAL backend workflow states only. Unknown names are shown as-is. */
const STEP_LABELS: Record<string, string> = {
  understand: "Understood the request", route: "Chose a capability", plan: "Planned subtasks",
  retrieve: "Retrieved sources", retrieval: "Checked retrieval results", generate: "Generated an answer",
  verify: "Verified the response", verification: "Checked claims against sources", correct: "Revised the draft",
  synthesize: "Prepared the final answer", done: "Finished", clarify: "Asked for clarification",
  quiz_created: "Created a quiz", failure: "Stopped safely",
};
export function stepLabel(name: string): string {
  if (name.startsWith("tool:")) return `Used tool: ${name.slice(5).replace(/_/g, " ")}`;
  return STEP_LABELS[name] ?? name;
}
export const planLabel = (id: string) => id.charAt(0).toUpperCase() + id.slice(1);
