import { api } from "../api/client";
import type { Diagnostics, Traces } from "../api/types";
import { Badge, Card, ErrorBanner, Loading, PageHeader } from "../components/ui";
import { useLoad } from "../hooks";

function TraceCard() {
  const { data, error } = useLoad(() => api.get<Traces>("/admin/traces?limit=15"));
  return (
    <Card title="Recent traces" actions={data ? <span className="muted">off-topic refused: {data.guardrails.refused_off_topic} · injection blocked: {data.guardrails.refused_injection}</span> : undefined}>
      <ErrorBanner message={error} />
      {data && data.items.length === 0 && <p className="muted">No traces yet. They appear after the first tutor request and are kept for 30 days. Only names, timings and counts are stored, never prompts or answers.</p>}
      {data && data.items.length > 0 && (
        <div className="tablewrap"><table><thead><tr><th>When</th><th>Workflow</th><th>Latency</th><th>Tokens</th><th>Steps</th><th>Result</th></tr></thead>
          <tbody>{data.items.map((t) => (
            <tr key={t.trace_id}><td>{new Date(t.created_at).toLocaleTimeString("en-IN")}</td><td>{t.workflow}</td><td>{Math.round(t.latency_ms)} ms</td><td>{t.tokens}</td>
              <td><small>{t.spans.map((s) => s.name.replace("guardrail:", "")).join(" → ")}</small></td>
              <td>{t.error_category ? <Badge tone="warn">{t.error_category}</Badge> : <Badge tone="ok">ok</Badge>}</td></tr>))}</tbody></table></div>
      )}
    </Card>
  );
}

export function Admin() {
  const { data, error, loading, reload } = useLoad(() => api.get<Diagnostics>("/admin/diagnostics"));
  return (
    <>
      <PageHeader title="Admin diagnostics">Read-only. Secrets are reported only as configured or not configured, never shown.</PageHeader>
      <ErrorBanner message={error} onRetry={reload} />
      {loading && !data && <Loading label="Loading diagnostics" />}
      {data && (
        <div className="grid2">
          <Card title="System">
            <p>Database: <Badge tone={data.database === "up" ? "ok" : "warn"}>{data.database}</Badge></p>
            <ul className="plain">{Object.entries(data.counts).map(([k, v]) => <li key={k}>{k.replace(/_/g, " ")}: {v}</li>)}</ul>
          </Card>
          <Card title="Integrations">
            <ul className="plain">{Object.entries(data.integrations).map(([k, v]) => (
              <li key={k}><strong>{k}</strong> <small className="muted">{Object.entries(v).map(([a, b]) => `${a}=${String(b)}`).join(", ")}</small></li>))}</ul>
          </Card>
          <Card title="Workflow limits">
            <ul className="plain">{Object.entries(data.limits).map(([k, v]) => <li key={k}>{k.replace(/_/g, " ")}: {v}</li>)}</ul>
          </Card>
          <Card title="Tool registry">
            <ul className="plain">{data.tools.map((t) => (
              <li key={t.name}><strong>{t.name}</strong> <Badge tone={t.read_only ? "ok" : "warn"}>{t.read_only ? "read-only" : "write"}</Badge>{t.requires_approval && <> <Badge>needs approval</Badge></>}
                <br /><small className="muted">{t.description} (timeout {t.timeout_s}s)</small></li>))}</ul>
          </Card>
        </div>
      )}
      <div style={{ marginTop: "1.1rem" }}><TraceCard /></div>
    </>
  );
}
