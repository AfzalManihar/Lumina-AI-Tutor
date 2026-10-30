import { useEffect, useId, useState, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "ghost" | "danger";
export function Button({ variant = "primary", loading, children, disabled, ...rest }:
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; loading?: boolean }) {
  return (
    <button className={`btn btn-${variant}`} disabled={disabled || loading} aria-busy={loading || undefined} {...rest}>
      {loading && <Spinner small />}{children}
    </button>
  );
}

export function Spinner({ small, label = "Loading" }: { small?: boolean; label?: string }) {
  return <span className={`spinner${small ? " spinner-sm" : ""}`} role="status" aria-label={label} />;
}

export function Field({ label, hint, error, children }: { label: string; hint?: string; error?: string | null; children: (id: string, describedBy?: string) => ReactNode }) {
  const id = useId();
  const desc = error ? `${id}-err` : hint ? `${id}-hint` : undefined;
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      {children(id, desc)}
      {error ? <p className="field-error" id={`${id}-err`} role="alert">{error}</p> : hint ? <p className="field-hint" id={`${id}-hint`}>{hint}</p> : null}
    </div>
  );
}
export const TextInput = (p: InputHTMLAttributes<HTMLInputElement>) => <input className="input" {...p} />;
export const TextArea = (p: TextareaHTMLAttributes<HTMLTextAreaElement>) => <textarea className="input" {...p} />;
export const Select = (p: SelectHTMLAttributes<HTMLSelectElement>) => <select className="input" {...p} />;

export function ErrorBanner({ message, onRetry }: { message: string | null; onRetry?: () => void }) {
  if (!message) return null;
  return (
    <div className="banner banner-error" role="alert">
      <span>{message}</span>
      {onRetry && <Button variant="ghost" onClick={onRetry}>Try again</Button>}
    </div>
  );
}
export const Notice = ({ children, tone = "info" }: { children: ReactNode; tone?: "info" | "warn" | "ok" }) => <div className={`banner banner-${tone}`} role="status">{children}</div>;

export function EmptyState({ title, children, action, icon = "sparkle" }: { title: string; children?: ReactNode; action?: ReactNode; icon?: IconName }) {
  return <div className="empty"><span className="empty-icon" aria-hidden="true"><Icon name={icon} size={20} /></span><h3>{title}</h3>{children && <p>{children}</p>}{action}</div>;
}

export function Loading({ label = "Loading" }: { label?: string }) {
  return <div className="loading"><Spinner label={label} /><span>{label}…</span></div>;
}

export function Badge({ tone = "neutral", children }: { tone?: "neutral" | "ok" | "warn" | "mark"; children: ReactNode }) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}

export function Card({ title, actions, children, className = "" }: { title?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`card ${className}`}>
      {(title || actions) && <header className="card-head">{title && <h2>{title}</h2>}{actions}</header>}
      {children}
    </section>
  );
}

export function PageHeader({ title, children, actions }: { title: string; children?: ReactNode; actions?: ReactNode }) {
  return (
    <header className="page-head">
      <div><h1>{title}</h1>{children && <p className="lede">{children}</p>}</div>
      {actions && <div className="page-actions">{actions}</div>}
    </header>
  );
}

function useGrow(target: number): number {
  const [v, setV] = useState(0);
  useEffect(() => { const t = setTimeout(() => setV(target), 90); return () => clearTimeout(t); }, [target]);
  return v;
}

export function Meter({ value, max, label }: { value: number; max: number; label: string }) {
  const pct = max > 0 ? Math.min(100, Math.round((value / max) * 100)) : 0;
  const shown = useGrow(pct);
  return (
    <div className="meter" role="meter" aria-label={label} aria-valuemin={0} aria-valuemax={max} aria-valuenow={value}>
      <div className={`meter-fill${pct >= 90 ? " meter-hot" : ""}`} style={{ width: `${shown}%` }} />
    </div>
  );
}

/** Inline confirmation for destructive actions; focus moves to the confirm button. */
export function Confirm({ message, onYes, onNo, yesLabel = "Delete" }: { message: string; onYes: () => void; onNo: () => void; yesLabel?: string }) {
  return (
    <div className="confirm" role="alertdialog" aria-label={message}>
      <span>{message}</span>
      <Button variant="danger" autoFocus onClick={onYes}>{yesLabel}</Button>
      <Button variant="ghost" onClick={onNo}>Cancel</Button>
    </div>
  );
}

const ICONS = {
  home: "M3 11l9-8 9 8v9a1 1 0 01-1 1h-5v-6H9v6H4a1 1 0 01-1-1z",
  chat: "M21 12a8 8 0 01-11.6 7.1L3 21l1.9-5.4A8 8 0 1121 12z",
  file: "M14 3H7a2 2 0 00-2 2v14a2 2 0 002 2h10a2 2 0 002-2V8zM14 3v5h5M9 13h6M9 17h6",
  search: "M11 4a7 7 0 100 14 7 7 0 000-14zM21 21l-4.3-4.3",
  book: "M4 5a2 2 0 012-2h13v16H6a2 2 0 00-2 2zM4 19a2 2 0 012-2h13",
  quiz: "M9 11l3 3 8-8M20 12v7a2 2 0 01-2 2H6a2 2 0 01-2-2V7a2 2 0 012-2h9",
  chart: "M4 20V10M10 20V4M16 20v-8M22 20H2",
  bookmark: "M6 3h12a1 1 0 011 1v17l-7-4-7 4V4a1 1 0 011-1z",
  gauge: "M12 14l4-4M4.9 19a9 9 0 1114.2 0",
  card: "M3 6a2 2 0 012-2h14a2 2 0 012 2v12a2 2 0 01-2 2H5a2 2 0 01-2-2zM3 10h18",
  user: "M12 12a4 4 0 100-8 4 4 0 000 8zM4 21a8 8 0 0116 0",
  shield: "M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z",
  upload: "M12 16V4M7 9l5-5 5 5M4 20h16",
  send: "M22 2L11 13M22 2l-7 20-4-9-9-4z",
  menu: "M4 6h16M4 12h16M4 18h16",
  x: "M6 6l12 12M18 6L6 18",
  sparkle: "M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8zM19 16l.8 2.2L22 19l-2.2.8L19 22l-.8-2.2L16 19l2.2-.8z",
  logout: "M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4M16 17l5-5-5-5M21 12H9",
  plus: "M12 5v14M5 12h14",
  trash: "M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3",
  refresh: "M20 11a8 8 0 10-2.3 5.7M20 4v7h-7",
  chevron: "M6 9l6 6 6-6",
  check: "M5 13l4 4L19 7",
  alert: "M12 8v5M12 17h.01M10.3 3.9L2.4 18a2 2 0 001.7 3h15.8a2 2 0 001.7-3L13.7 3.9a2 2 0 00-3.4 0z",
  link: "M10 14a4 4 0 005.7 0l3-3a4 4 0 00-5.7-5.7l-1 1M14 10a4 4 0 00-5.7 0l-3 3a4 4 0 005.7 5.7l1-1",
} as const;
export type IconName = keyof typeof ICONS;

/** Inline stroke icons (no icon dependency). Decorative unless a label is given. */
export function Icon({ name, size = 18, label }: { name: IconName; size?: number; label?: string }) {
  return (
    <svg className="icon" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
      strokeLinecap="round" strokeLinejoin="round" role={label ? "img" : undefined} aria-label={label} aria-hidden={label ? undefined : true}>
      <path d={ICONS[name]} />
    </svg>
  );
}

/** Circular progress ring. Shows exactly the value passed in. */
export function Ring({ value, max, label, children }: { value: number; max: number; label: string; children?: ReactNode }) {
  const pct = max > 0 ? Math.min(1, value / max) : 0;
  const grown = useGrow(pct);
  const r = 52, c = 2 * Math.PI * r;
  return (
    <div className="ring" role="meter" aria-label={label} aria-valuemin={0} aria-valuemax={max} aria-valuenow={value}>
      <svg viewBox="0 0 120 120" aria-hidden="true">
        <circle className="ring-track" cx="60" cy="60" r={r} />
        <circle className={`ring-fill${pct >= 0.9 ? " ring-hot" : ""}`} cx="60" cy="60" r={r} strokeDasharray={`${c * grown} ${c}`} transform="rotate(-90 60 60)" />
      </svg>
      <div className="ring-center">{children}</div>
    </div>
  );
}

export function Avatar({ name }: { name: string }) {
  const initials = (name || "?").trim().split(/\s+/).slice(0, 2).map((p) => p[0]?.toUpperCase() ?? "").join("") || "?";
  return <span className="avatar" aria-hidden="true">{initials}</span>;
}
