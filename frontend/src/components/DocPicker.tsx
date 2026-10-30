import type { Doc } from "../api/types";

export function DocPicker({ docs, selected, onChange }: { docs: Doc[]; selected: string[]; onChange: (ids: string[]) => void }) {
  const ready = docs.filter((d) => d.status === "ready");
  if (!ready.length) return <p className="field-hint">No ready documents yet.</p>;
  const toggle = (id: string) => onChange(selected.includes(id) ? selected.filter((x) => x !== id) : [...selected, id]);
  return (
    <fieldset className="docpicker">
      <legend>Documents to use</legend>
      {ready.map((d) => (
        <label key={d.id} className="check">
          <input type="checkbox" checked={selected.includes(d.id)} onChange={() => toggle(d.id)} />
          <span>{d.filename}</span>
        </label>
      ))}
    </fieldset>
  );
}
