import { AnimatePresence, motion } from "motion/react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { EASE } from "./fx";
import { Icon, type IconName } from "./ui";

export interface Command { id: string; label: string; hint: string; icon: IconName; to: string }

/** Ctrl/Cmd+K quick navigation. Every entry is a real route; nothing here calls the API. */
export function CommandPalette({ open, onClose, commands }: { open: boolean; onClose: () => void; commands: Command[] }) {
  const nav = useNavigate();
  const [q, setQ] = useState("");
  const [sel, setSel] = useState(0);
  const input = useRef<HTMLInputElement>(null);
  const results = useMemo(() => {
    const t = q.trim().toLowerCase();
    return t ? commands.filter((c) => `${c.label} ${c.hint}`.toLowerCase().includes(t)) : commands;
  }, [q, commands]);

  useEffect(() => { if (open) { setQ(""); setSel(0); setTimeout(() => input.current?.focus(), 30); } }, [open]);
  useEffect(() => { setSel(0); }, [q]);

  const go = (c: Command | undefined) => { if (!c) return; onClose(); nav(c.to); };
  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") { e.preventDefault(); setSel((s) => Math.min(results.length - 1, s + 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setSel((s) => Math.max(0, s - 1)); }
    else if (e.key === "Enter") { e.preventDefault(); go(results[sel]); }
    else if (e.key === "Escape") { e.preventDefault(); onClose(); }
  };

  return (
    <AnimatePresence>
      {open && (
        <motion.div className="pal-scrim" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.16 }}
          onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
          <motion.div className="pal" role="dialog" aria-modal="true" aria-label="Jump to a page" onKeyDown={onKey}
            initial={{ opacity: 0, y: -12, scale: 0.97 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: -8, scale: 0.98 }} transition={{ duration: 0.2, ease: EASE }}>
            <div className="pal-in"><Icon name="search" size={18} />
              <input ref={input} value={q} onChange={(e) => setQ(e.target.value)} placeholder="Jump to a page or action" aria-label="Search pages"
                role="combobox" aria-expanded="true" aria-controls="pal-list" aria-activedescendant={results[sel] ? `pal-${results[sel].id}` : undefined} />
              <span className="kbd">Esc</span></div>
            {results.length === 0 ? <p className="pal-empty">Nothing matches “{q}”.</p> : (
              <ul className="pal-list" id="pal-list" role="listbox">
                {results.map((c, n) => (
                  <li key={c.id} role="presentation">
                    <button id={`pal-${c.id}`} role="option" aria-selected={n === sel} onMouseEnter={() => setSel(n)} onClick={() => go(c)}>
                      <Icon name={c.icon} size={18} />{c.label}<small>{c.hint}</small>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
