import { useState } from "react";
import type { Citation } from "../api/types";

/** Each citation is a real retrieved chunk: filename, page and the exact stored passage. */
export function Citations({ citations }: { citations: Citation[] }) {
  const [open, setOpen] = useState<string | null>(null);
  if (!citations.length) return null;
  return (
    <ul className="cites" aria-label="Sources">
      {citations.map((c) => {
        const isOpen = open === c.chunk_id;
        const panel = `cite-${c.chunk_id}`;
        return (
          <li key={c.chunk_id}>
            <button className="cite-chip" aria-expanded={isOpen} aria-controls={panel}
              onClick={() => setOpen(isOpen ? null : c.chunk_id)}>
              <span className="cite-id">{c.cite_id}</span>
              <span className="cite-name">{c.filename}{c.page ? `, page ${c.page}` : ""}</span>
            </button>
            {isOpen && (
              <blockquote id={panel} className="passage">
                {c.section && <strong>{c.section}</strong>}
                <p>{c.passage}</p>
                <small>Match score {c.score.toFixed(2)}</small>
              </blockquote>
            )}
          </li>
        );
      })}
    </ul>
  );
}
