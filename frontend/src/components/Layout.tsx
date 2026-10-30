import { motion } from "motion/react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, NavLink, useLocation, useNavigate, useOutlet } from "react-router-dom";
import { api } from "../api/client";
import type { Usage } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { fmtNum, planLabel } from "../lib";
import { CommandPalette, type Command } from "./Palette";
import { EASE, SPRING, useTheme, type ThemeChoice } from "./fx";
import { Avatar, Icon, Meter, type IconName } from "./ui";

interface Item { to: string; label: string; icon: IconName }
const GROUPS: { label: string; items: Item[] }[] = [
  { label: "Learn", items: [
    { to: "/app", label: "Dashboard", icon: "home" }, { to: "/tutor", label: "Tutor chat", icon: "chat" },
    { to: "/ask", label: "Ask documents", icon: "search" }, { to: "/lessons", label: "Lessons", icon: "book" },
    { to: "/quizzes", label: "Quizzes", icon: "quiz" } ] },
  { label: "Library", items: [
    { to: "/documents", label: "Documents", icon: "file" }, { to: "/memory", label: "Memory", icon: "bookmark" },
    { to: "/progress", label: "Progress", icon: "chart" } ] },
  { label: "Account", items: [
    { to: "/usage", label: "Usage", icon: "gauge" }, { to: "/billing", label: "Plans and billing", icon: "card" },
    { to: "/profile", label: "Profile and privacy", icon: "user" } ] },
];
const ADMIN_GROUP = { label: "Admin", items: [{ to: "/admin", label: "Diagnostics", icon: "shield" as IconName }] };

export function Logo({ onDark = false }: { onDark?: boolean }) {
  return (
    <span className={`logo${onDark ? " logo-dark" : ""}`}>
      <svg width="28" height="28" viewBox="0 0 32 32" aria-hidden="true">
        <rect width="32" height="32" rx="9" fill="#3355FF" />
        <circle cx="16" cy="14.5" r="6" fill="#FFC933" />
        <path d="M8.5 25h15" stroke="#fff" strokeWidth="2.2" strokeLinecap="round" opacity=".92" />
      </svg>
      <span>Lumina AI Tutor</span>
    </span>
  );
}

function UsageChip() {
  const loc = useLocation();
  const [u, setU] = useState<Usage["current"] | null>(null);
  useEffect(() => {
    let alive = true;
    api.get<Usage>("/usage").then((r) => alive && setU(r.current)).catch(() => alive && setU(null));
    return () => { alive = false; };
  }, [loc.pathname]);
  if (!u) return null;
  return (
    <div className="plan-chip">
      <div className="plan-chip-top"><strong>{planLabel(u.plan_id)} plan</strong>{u.plan_id === "free" && <Link to="/billing">Upgrade</Link>}</div>
      <Meter value={u.tokens_used} max={u.limit} label="Tokens used this month" />
      <small>{fmtNum(u.tokens_used)} of {fmtNum(u.limit)} tokens used</small>
    </div>
  );
}

export function Layout() {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const loc = useLocation();
  const [drawer, setDrawer] = useState(false);
  const [menu, setMenu] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const groups = user?.role === "admin" ? [...GROUPS, ADMIN_GROUP] : GROUPS;
  const outlet = useOutlet();
  const [theme, setTheme] = useTheme();
  const [pal, setPal] = useState(false);
  const commands: Command[] = useMemo(() => [
    ...groups.flatMap((g) => g.items.map((i) => ({ id: i.to.slice(1) || "home", label: i.label, hint: g.label, icon: i.icon, to: i.to }))),
    { id: "new-chat", label: "Start a new chat", hint: "Action", icon: "plus" as IconName, to: "/tutor" },
    { id: "upload", label: "Upload a document", hint: "Action", icon: "upload" as IconName, to: "/documents" },
  ], [groups]);

  useEffect(() => { setDrawer(false); setMenu(false); }, [loc.pathname]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") { setDrawer(false); setMenu(false); }
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setPal((v) => !v); }
    };
    const onClick = (e: MouseEvent) => { if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenu(false); };
    document.addEventListener("keydown", onKey); document.addEventListener("mousedown", onClick);
    return () => { document.removeEventListener("keydown", onKey); document.removeEventListener("mousedown", onClick); };
  }, []);

  const here = groups.flatMap((g) => g.items.map((i) => ({ ...i, group: g.label }))).find((i) => (i.to === "/app" ? loc.pathname === "/app" : loc.pathname.startsWith(i.to)));
  const displayName = user?.name || user?.email || "";

  return (
    <div className="app">
      <a className="skip" href="#main">Skip to content</a>
      <aside className={`sidebar${drawer ? " sidebar-open" : ""}`} id="sidebar">
        <div className="sb-brand"><Link to="/app" aria-label="Lumina dashboard"><Logo onDark /></Link></div>
        <nav aria-label="Main" className="sb-nav">
          {groups.map((g) => (
            <div key={g.label} className="sb-group">
              <p className="sb-label">{g.label}</p>
              {g.items.map((i) => (
                <NavLink key={i.to} to={i.to} end={i.to === "/app"} className={({ isActive }) => `sb-link${isActive ? " active" : ""}`}>
                  {({ isActive }) => (<>
                    {isActive && <motion.span layoutId="sb-pill" className="sb-pill" transition={SPRING}><i className="sb-pill-bar" /></motion.span>}
                    <Icon name={i.icon} size={18} /><span>{i.label}</span>
                  </>)}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>
        <UsageChip />
      </aside>
      {drawer && <button className="scrim" aria-label="Close menu" onClick={() => setDrawer(false)} />}

      <div className="app-body">
        <header className="topbar">
          <button className="icon-btn tb-menu" aria-label="Open menu" aria-expanded={drawer} aria-controls="sidebar" onClick={() => setDrawer((v) => !v)}>
            <Icon name={drawer ? "x" : "menu"} size={20} />
          </button>
          <p className="crumb">{here ? <><span>{here.group}</span><Icon name="chevron" size={12} /><strong>{here.label}</strong></> : null}</p>
          <div className="tb-right">
            <button className="search-btn" onClick={() => setPal(true)} aria-label="Search pages and actions"><Icon name="search" size={16} /><span>Jump to</span><kbd className="kbd">Ctrl K</kbd></button>
            <Link className="btn btn-primary btn-sm" to="/tutor"><Icon name="plus" size={16} /><span>New chat</span></Link>
            <div className="usermenu" ref={menuRef}>
              <button className="userbtn" aria-haspopup="menu" aria-expanded={menu} onClick={() => setMenu((v) => !v)}>
                <Avatar name={displayName} /><span className="who" title={user?.email}>{displayName}</span><Icon name="chevron" size={14} />
              </button>
              {menu && (
                <div className="menu" role="menu">
                  <p className="menu-id"><strong>{user?.name || "Signed in"}</strong><small>{user?.email}</small></p>
                  <Link role="menuitem" to="/profile"><Icon name="user" size={16} />Profile and privacy</Link>
                  <Link role="menuitem" to="/billing"><Icon name="card" size={16} />Plans and billing</Link>
                  <div className="menu-sep" /><p className="menu-cap">Theme</p>
                  <div className="theme-seg" role="group" aria-label="Theme">
                    {(["system", "light", "dark"] as ThemeChoice[]).map((t) => (
                      <button key={t} aria-pressed={theme === t} onClick={() => setTheme(t)}>{t[0].toUpperCase() + t.slice(1)}</button>))}
                  </div>
                  <div className="menu-sep" />
                  <button role="menuitem" onClick={async () => { await logout(); nav("/"); }}><Icon name="logout" size={16} />Sign out</button>
                </div>
              )}
            </div>
          </div>
        </header>
        <main id="main" className="main" tabIndex={-1}>
          <motion.div key={loc.pathname} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3, ease: EASE }}>{outlet}</motion.div>
        </main>
        <CommandPalette open={pal} onClose={() => setPal(false)} commands={commands} />
      </div>
    </div>
  );
}
