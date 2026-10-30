import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { Progress } from "../api/types";
import { Card, EmptyState, ErrorBanner, Loading, Meter, PageHeader } from "../components/ui";
import { useLoad } from "../hooks";
import { fmtDateTime } from "../lib";

export function ProgressPage() {
  const { data, error, loading, reload } = useLoad(() => api.get<Progress>("/progress"));
  return (
    <>
      <PageHeader title="Learning progress">Computed from your lessons and quiz attempts.</PageHeader>
      <ErrorBanner message={error} onRetry={reload} />
      {loading && !data && <Loading label="Loading progress" />}
      {data && data.topics.length === 0 && data.recent_activity.length === 0 && (
        <Card><EmptyState title="No activity yet" action={<Link className="btn btn-secondary" to="/quizzes">Take a quiz</Link>}>Create a lesson or complete a quiz and it will be tracked here.</EmptyState></Card>
      )}
      {data && (data.topics.length > 0 || data.recent_activity.length > 0) && (
        <div className="grid2">
          <Card title="Summary">
            <p className="big">{data.lessons_completed} <small>lessons</small></p>
            <p className="big">{data.quizzes_taken} <small>quiz attempts</small></p>
            <p className="muted">{data.average_quiz_percent !== null ? `Average score ${data.average_quiz_percent}%` : "No quiz scores yet"}</p>
          </Card>
          <Card title="By topic">
            {data.topics.map((t) => (
              <div key={t.topic} className="bar-row">
                <span title={t.topic}>{t.topic}</span>
                <Meter value={t.best_percent ?? 0} max={100} label={`Best score for ${t.topic}`} />
                <span>{t.best_percent !== null ? `${t.best_percent}%` : "no quiz"}</span>
              </div>
            ))}
          </Card>
          <Card title="Study history">
            <ul className="plain">{data.recent_activity.map((a, i) => (
              <li key={i}>{a.type.replace(/_/g, " ")}{a.topic ? `: ${a.topic}` : ""}{a.percent !== null && a.percent !== undefined ? ` (${a.percent}%)` : ""} <span className="muted">{fmtDateTime(a.created_at)}</span></li>))}</ul>
          </Card>
        </div>
      )}
    </>
  );
}
