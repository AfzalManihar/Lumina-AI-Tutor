import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { Usage } from "../api/types";
import { Card, EmptyState, ErrorBanner, Loading, Meter, Notice, PageHeader } from "../components/ui";
import { useLoad } from "../hooks";
import { fmtNum, planLabel } from "../lib";

export function UsagePage() {
  const { data, error, loading, reload } = useLoad(() => api.get<Usage>("/usage"));
  const c = data?.current;
  const features = c ? Object.entries(c.by_feature).sort((a, b) => b[1] - a[1]) : [];
  const maxHist = data ? Math.max(1, ...data.history.map((h) => h.tokens_used)) : 1;
  return (
    <>
      <PageHeader title="Monthly usage">Token usage is metered on the server and enforced against your plan.</PageHeader>
      <ErrorBanner message={error} onRetry={reload} />
      {loading && !data && <Loading label="Loading usage" />}
      {c && (
        <div className="grid2">
          <Card title={`This month (${c.period})`}>
            <p className="big">{fmtNum(c.tokens_used)} <small>of {fmtNum(c.limit)} tokens</small></p>
            <Meter value={c.tokens_used} max={c.limit} label="Tokens used this month" />
            <p className="muted">{fmtNum(c.remaining)} remaining · {c.requests} requests · {planLabel(c.plan_id)} plan</p>
            {c.remaining <= 0 && <Notice tone="warn">Your allowance is used up. AI features are paused until next month, or <Link to="/billing">upgrade your plan</Link>.</Notice>}
          </Card>
          <Card title="By feature">
            {features.length === 0 ? <EmptyState title="No usage yet">Use the tutor, lessons or quizzes and the breakdown appears here.</EmptyState> : (
              <ul className="plain">{features.map(([f, n]) => <li key={f}>{f.replace(/_/g, " ")}: {fmtNum(n)} tokens</li>)}</ul>)}
          </Card>
          <Card title="Last months">
            {data!.history.length === 0 ? <EmptyState title="No history" /> : (
              <div className="bars" role="img" aria-label={data!.history.map((h) => `${h.period}: ${h.tokens_used} tokens`).join(", ")} style={{ marginBottom: "1.6rem" }}>
                {[...data!.history].reverse().map((h) => <div key={h.period} style={{ height: `${Math.max(2, (h.tokens_used / maxHist) * 100)}%` }} title={`${h.period}: ${fmtNum(h.tokens_used)}`}><span>{h.period.slice(5)}</span></div>)}
              </div>)}
          </Card>
        </div>
      )}
    </>
  );
}
