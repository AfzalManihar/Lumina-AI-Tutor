import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { api, errorText, setAccessToken } from "../api/client";
import type { User } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { Button, Card, ErrorBanner, Field, Notice, PageHeader, TextInput } from "../components/ui";

export function Profile() {
  const { user, setUser } = useAuth();
  const nav = useNavigate();
  const [name, setName] = useState(user?.name ?? "");
  const [topic, setTopic] = useState(user?.settings.learning_topic ?? "");
  const [memoryOn, setMemoryOn] = useState(user?.settings.memory_enabled ?? true);
  const [ok, setOk] = useState<string | null>(null); const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [oldPw, setOldPw] = useState(""); const [newPw, setNewPw] = useState("");
  const [pwErr, setPwErr] = useState<string | null>(null); const [pwOk, setPwOk] = useState<string | null>(null);

  async function saveProfile(e: FormEvent) {
    e.preventDefault(); setErr(null); setOk(null); setBusy(true);
    try {
      const u = await api.patch<User>("/users/me", { name, settings: { memory_enabled: memoryOn, learning_topic: topic } });
      setUser(u); setOk("Saved.");
    } catch (x) { setErr(errorText(x)); } finally { setBusy(false); }
  }
  async function changePw(e: FormEvent) {
    e.preventDefault(); setPwErr(null); setPwOk(null);
    try { await api.post("/users/me/password", { old_password: oldPw, new_password: newPw }); setPwOk("Password changed. Other devices were signed out."); setOldPw(""); setNewPw(""); }
    catch (x) { setPwErr(errorText(x)); }
  }
  async function signOutEverywhere() {
    try { await api.post("/auth/logout-all"); setAccessToken(null); nav("/login"); window.location.reload(); } catch (x) { setErr(errorText(x)); }
  }
  return (
    <>
      <PageHeader title="Profile and privacy" />
      <Card title="Profile and preferences">
        <form onSubmit={saveProfile}>
          <ErrorBanner message={err} />{ok && <Notice tone="ok">{ok}</Notice>}
          <Field label="Email">{(id) => <TextInput id={id} value={user?.email ?? ""} readOnly />}</Field>
          <Field label="Name">{(id) => <TextInput id={id} maxLength={100} value={name} onChange={(e) => setName(e.target.value)} />}</Field>
          <Field label="Current learning topic">{(id) => <TextInput id={id} maxLength={120} value={topic} onChange={(e) => setTopic(e.target.value)} />}</Field>
          <label className="check"><input type="checkbox" checked={memoryOn} onChange={(e) => setMemoryOn(e.target.checked)} />
            <span>Allow Lumina to save and use memories (you can review them on the Memory page)</span></label>
          <p className="field-hint">When off, no memory is read, suggested or saved. Existing memories are kept until you delete them.</p>
          <Button type="submit" loading={busy}>Save changes</Button>
        </form>
      </Card>
      <Card title="Change password">
        <form onSubmit={changePw}>
          <ErrorBanner message={pwErr} />{pwOk && <Notice tone="ok">{pwOk}</Notice>}
          <Field label="Current password">{(id) => <TextInput id={id} type="password" autoComplete="current-password" required value={oldPw} onChange={(e) => setOldPw(e.target.value)} />}</Field>
          <Field label="New password" hint="At least 8 characters.">{(id, d) => <TextInput id={id} aria-describedby={d} type="password" autoComplete="new-password" required minLength={8} value={newPw} onChange={(e) => setNewPw(e.target.value)} />}</Field>
          <Button type="submit" disabled={!oldPw || newPw.length < 8}>Change password</Button>
        </form>
      </Card>
      <Card title="Sessions">
        <p>Sign out of every device where you are logged in.</p>
        <Button variant="secondary" onClick={signOutEverywhere}>Sign out everywhere</Button>
      </Card>
    </>
  );
}
