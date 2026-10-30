import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { api, errorText } from "../api/client";
import type { Memory, MemoryList } from "../api/types";
import { Badge, Button, Card, Confirm, EmptyState, ErrorBanner, Field, Loading, Notice, PageHeader, Select, TextInput } from "../components/ui";
import { useLoad } from "../hooks";
import { fmtDate } from "../lib";

const TYPES = ["preference", "goal", "topic", "progress_summary", "fact"] as const;

export function MemoryPage() {
  const { data, error, loading, reload } = useLoad(() => api.get<MemoryList>("/memory", { limit: 100 }));
  const [text, setText] = useState(""); const [type, setType] = useState<string>("preference");
  const [editing, setEditing] = useState<string | null>(null); const [editText, setEditText] = useState("");
  const [confirm, setConfirm] = useState<string | null>(null); const [confirmAll, setConfirmAll] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function run(fn: () => Promise<unknown>) {
    setErr(null);
    try { await fn(); await reload(); } catch (e) { setErr(errorText(e)); }
  }
  const add = (e: FormEvent) => { e.preventDefault(); void run(async () => { await api.post("/memory", { text, type, source: "user_manual" }); setText(""); }); };
  const save = (m: Memory) => run(async () => { await api.patch(`/memory/${m.id}`, { text: editText }); setEditing(null); });

  return (
    <>
      <PageHeader title="Saved memory">Only things you save or approve are stored. Memories are used to personalise answers and can be edited or deleted at any time.</PageHeader>
      <ErrorBanner message={err ?? error} onRetry={error ? reload : undefined} />
      {data && !data.enabled && <Notice tone="warn">Memory is turned off, so nothing is saved or used. Change this in <Link to="/profile">Profile and privacy</Link>.</Notice>}
      <Card title="Add a memory">
        <form onSubmit={add} className="row">
          <Field label="What should Lumina remember?" hint="Do not include passwords or payment details; they are rejected.">{(id, d) => <TextInput id={id} aria-describedby={d} required minLength={3} maxLength={500} value={text} onChange={(e) => setText(e.target.value)} />}</Field>
          <Field label="Type">{(id) => <Select id={id} value={type} onChange={(e) => setType(e.target.value)}>{TYPES.map((t) => <option key={t} value={t}>{t.replace("_", " ")}</option>)}</Select>}</Field>
          <Button type="submit" disabled={text.trim().length < 3 || (data ? !data.enabled : false)}>Save</Button>
        </form>
      </Card>
      <Card title={`Your memories${data ? ` (${data.total})` : ""}`} actions={data && data.total > 0 ? (
        confirmAll ? <Confirm message="Delete ALL memories?" yesLabel="Delete all" onYes={() => { setConfirmAll(false); void run(() => api.del("/memory")); }} onNo={() => setConfirmAll(false)} />
          : <Button variant="ghost" onClick={() => setConfirmAll(true)}>Delete all</Button>) : undefined}>
        {loading && !data && <Loading label="Loading memories" />}
        {data?.items.length === 0 && <EmptyState title="Nothing saved yet">Add one above, or approve a suggestion when the tutor offers to remember something.</EmptyState>}
        {data?.items.map((m) => (
          <div key={m.id} className="memory-item">
            <div style={{ flex: 1 }}>
              {editing === m.id ? (
                <form onSubmit={(e) => { e.preventDefault(); void save(m); }} className="row">
                  <Field label="Edit memory">{(id) => <TextInput id={id} autoFocus minLength={3} maxLength={500} value={editText} onChange={(e) => setEditText(e.target.value)} />}</Field>
                  <Button type="submit" disabled={editText.trim().length < 3}>Save</Button>
                  <Button variant="ghost" type="button" onClick={() => setEditing(null)}>Cancel</Button>
                </form>
              ) : (<>
                <p style={{ margin: 0 }}>{m.text}</p>
                <small className="muted"><Badge>{m.type.replace("_", " ")}</Badge> {m.source.replace("_", " ")} · {fmtDate(m.updated_at)}</small>
              </>)}
            </div>
            {editing !== m.id && (confirm === m.id
              ? <Confirm message="Delete this memory?" onYes={() => { setConfirm(null); void run(() => api.del(`/memory/${m.id}`)); }} onNo={() => setConfirm(null)} />
              : <span className="actions">
                  <Button variant="ghost" onClick={() => { setEditing(m.id); setEditText(m.text); }}>Edit</Button>
                  <Button variant="ghost" onClick={() => setConfirm(m.id)}>Delete</Button>
                </span>)}
          </div>
        ))}
      </Card>
    </>
  );
}
