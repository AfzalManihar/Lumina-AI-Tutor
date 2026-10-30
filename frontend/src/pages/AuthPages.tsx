import { motion } from "motion/react";
import { useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { errorText } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { Logo } from "../components/Layout";
import { EASE, Stars } from "../components/fx";
import { Button, ErrorBanner, Field, Icon, TextInput } from "../components/ui";

function Shell({ title, sub, children, foot }: { title: string; sub: string; children: React.ReactNode; foot: React.ReactNode }) {
  return (
    <div className="auth">
      <aside className="auth-art" aria-hidden="true">
        <Stars count={60} />
        <div className="auth-rings"><i /><i /><i /></div>
        <Logo onDark />
        <div className="auth-visual">
          <motion.div className="av-card" initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.9, ease: EASE, delay: 0.2 }}>
            <small>Biology notes.pdf, page 2</small>
            <p>Plants lose water through stomata, which also admit carbon dioxide.</p>
            <p className="av-lit">The Calvin cycle takes place in the stroma of the chloroplast.</p>
            <p>The light-dependent reactions occur in the thylakoid membranes.</p>
          </motion.div>
          <motion.span className="av-chip" initial={{ opacity: 0, scale: 0.7 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: 1, type: "spring", stiffness: 300, damping: 20 }}><b>S1</b>Biology notes.pdf, page 2</motion.span>
        </div>
        <div>
          <p className="auth-quote">Answers from your own notes, with the passage to prove it.</p>
          <ul>
            <li><Icon name="link" size={16} />Every claim links to a page</li>
            <li><Icon name="shield" size={16} />Your documents stay on your account</li>
            <li><Icon name="bookmark" size={16} />Memory only saves what you approve</li>
          </ul>
        </div>
      </aside>
      <main className="auth-pane">
        <div className="auth-card">
          <Link to="/" aria-label="Lumina home" className="auth-logo"><Logo /></Link>
          <h1>{title}</h1>
          <p className="auth-sub">{sub}</p>
          {children}
          <p className="auth-foot">{foot}</p>
        </div>
      </main>
    </div>
  );
}

export function Login() {
  const { user, login } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState(""); const [pw, setPw] = useState("");
  const [err, setErr] = useState<string | null>(null); const [busy, setBusy] = useState(false);
  if (user) return <Navigate to="/app" replace />;
  async function submit(e: FormEvent) {
    e.preventDefault(); setErr(null); setBusy(true);
    try { await login(email, pw); nav("/app"); } catch (x) { setErr(errorText(x)); } finally { setBusy(false); }
  }
  return (
    <Shell title="Sign in" sub="Pick up where you left off." foot={<>New here? <Link to="/register">Create an account</Link></>}>
      <form onSubmit={submit} noValidate>
        <ErrorBanner message={err} />
        <Field label="Email">{(id) => <TextInput id={id} type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />}</Field>
        <Field label="Password">{(id) => <TextInput id={id} type="password" autoComplete="current-password" required value={pw} onChange={(e) => setPw(e.target.value)} />}</Field>
        <Button type="submit" loading={busy} disabled={!email || !pw}>Sign in</Button>
      </form>
    </Shell>
  );
}

export function Register() {
  const { user, register } = useAuth();
  const nav = useNavigate();
  const [name, setName] = useState(""); const [email, setEmail] = useState(""); const [pw, setPw] = useState("");
  const [err, setErr] = useState<string | null>(null); const [busy, setBusy] = useState(false);
  if (user) return <Navigate to="/app" replace />;
  const weak = pw.length > 0 && (pw.length < 8 || !/[A-Za-z]/.test(pw) || !/\d/.test(pw));
  async function submit(e: FormEvent) {
    e.preventDefault(); setErr(null); setBusy(true);
    try { await register(email, pw, name); nav("/app"); } catch (x) { setErr(errorText(x)); } finally { setBusy(false); }
  }
  return (
    <Shell title="Create your account" sub="Free to start. No card needed." foot={<>Already registered? <Link to="/login">Sign in</Link></>}>
      <form onSubmit={submit} noValidate>
        <ErrorBanner message={err} />
        <Field label="Name (optional)">{(id) => <TextInput id={id} autoComplete="name" value={name} maxLength={100} onChange={(e) => setName(e.target.value)} />}</Field>
        <Field label="Email">{(id) => <TextInput id={id} type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />}</Field>
        <Field label="Password" hint="At least 8 characters, with a letter and a digit." error={weak ? "Password is too weak" : null}>
          {(id, d) => <TextInput id={id} aria-describedby={d} type="password" autoComplete="new-password" required value={pw} onChange={(e) => setPw(e.target.value)} />}
        </Field>
        <Button type="submit" loading={busy} disabled={!email || !pw || weak}>Create account</Button>
      </form>
    </Shell>
  );
}
