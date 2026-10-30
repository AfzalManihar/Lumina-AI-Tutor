import { motion } from "motion/react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { Dashboard as D } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { useLoad } from "../hooks";
import { fmtDate, fmtDateTime, fmtNum, planLabel } from "../lib";
import { CountUp, EASE, Skeleton } from "../components/fx";
import { Badge, Card, EmptyState, ErrorBanner, Icon, Meter, PageHeader, Ring } from "../components/ui";

const plural = (n: number, w: string) => `${n} ${w}${n === 1 ? "" : "s"}`;

const list = { hidden: {}, show: { transition: { staggerChildren: 0.07, delayChildren: 0.05 } } };
const item = { hidden: { opacity: 0, y: 16 }, show: { opacity: 1, y: 0, transition: { duration: 0.5, ease: EASE } } };

function DashSkeleton() {
  return (
    <div aria-busy="true" aria-label="Loading your dashboard">
      <div className="stat-grid">
        {[0, 1, 2, 3].map((n) => (
          <div key={n} className="tile">
            <Skeleton w={34} h={34} r={10} />
            <Skeleton w="50%" h={14} style={{ marginTop: 10 }} />
            <Skeleton w="70%" h={28} style={{ marginTop: 8 }} />
            <Skeleton w="85%" h={12} style={{ marginTop: 10 }} />
          </div>
        ))}
      </div>
      <div className="dash-cols">
        {[0, 1, 2, 3].map((n) => (
          <div key={n}>
            <div className="card">
              <Skeleton w="40%" h={16} />
              <Skeleton h={44} style={{ marginTop: 16 }} />
              <Skeleton h={44} style={{ marginTop: 10 }} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

const FEATURE_LABEL: Record<string, string> = { chat: "Tutor chat", quiz: "Quizzes", lesson: "Lessons", ask: "Ask documents" };
const FEATURE_COLORS = ["#5b7bff", "#ffc933", "#5ed3a6", "#a78bfa", "#ff8d93"];

function ActivityCard({ data }: { data: D }) {
  const feats = Object.entries(data.usage.by_feature).filter(([, v]) => v > 0).sort((a, b) => b[1] - a[1]);
  const total = feats.reduce((n, [, v]) => n + v, 0);
  const scores = [...data.recent_quiz_results].reverse();
  return (
    <Card title="Activity" actions={<Link to="/usage">Usage details</Link>}>
      <div className="act">
        <div>
          <h3 className="act-h">Where your tokens went</h3>
          {total === 0 ? <p className="muted">No usage yet this month.</p> : (<>
            <div className="stack" role="img" aria-label={feats.map(([k, v]) => `${FEATURE_LABEL[k] ?? k} ${Math.round((v / total) * 100)} percent`).join(", ")}>
              {feats.map(([k, v], n) => (<motion.i key={k} style={{ background: FEATURE_COLORS[n % 5] }} initial={{ width: 0 }} animate={{ width: `${(v / total) * 100}%` }} transition={{ duration: 0.9, ease: EASE, delay: 0.2 + n * 0.1 }} />))}
            </div>
            <ul className="legend">{feats.map(([k, v], n) => (<li key={k}><i style={{ background: FEATURE_COLORS[n % 5] }} />{FEATURE_LABEL[k] ?? k}<b>{fmtNum(v)}</b></li>))}</ul>
          </>)}
        </div>
        <div>
          <h3 className="act-h">Recent quiz scores</h3>
          {scores.length === 0 ? <p className="muted">Take a quiz to see your scores here.</p> : (
            <div className="qbars" role="img" aria-label={scores.map((r) => `${r.topic} ${r.percent} percent`).join(", ")}>
              {scores.map((r, n) => (
                <div key={n} className="qbar-col"><span>{r.percent}%</span>
                  <div className="qbar-track"><motion.i initial={{ height: 0 }} animate={{ height: `${Math.max(6, r.percent)}%` }} transition={{ duration: 0.8, ease: EASE, delay: 0.25 + n * 0.08 }} /></div>
                  <small>{r.topic}</small></div>
              ))}
            </div>
          )}
        </div>
      </div>
    </Card>
  );
}

function greeting(): string {
  const h = new Date().getHours();
  return h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
}

export function Dashboard() {
  const { user } = useAuth();
  const { data, error, loading, reload } = useLoad(() => api.get<D>("/dashboard"));
  const first = (user?.name || "").split(" ")[0];
  return (
    <>
      <PageHeader title={`${greeting()}${first ? `, ${first}` : ""}`}
        actions={<>
          <Link className="btn btn-outline" to="/documents"><Icon name="upload" size={16} />Upload document</Link>
          <Link className="btn btn-primary" to="/tutor"><Icon name="chat" size={16} />Ask the tutor</Link>
        </>}>Here is where your studying stands today.</PageHeader>
      <ErrorBanner message={error} onRetry={reload} />
      {loading && !data && <DashSkeleton />}
      {data && (
        <>
          <motion.div className="band" initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, ease: EASE }}>
            <div>
              <p className="band-k">{data.recent_conversations[0] ? "Pick up where you left off" : "Start here"}</p>
              <h2>{data.recent_conversations[0] ? data.recent_conversations[0].title || "Untitled chat" : "Ask your first question"}</h2>
              <p className="muted">{data.recent_conversations[0] ? `${plural(data.recent_conversations[0].message_count, "message")}, last active ${fmtDateTime(data.recent_conversations[0].updated_at)}` : "Upload a document or just ask. Answers from your documents come with the passage attached."}</p>
            </div>
            <Link className="btn btn-lumen" to={data.recent_conversations[0] ? `/tutor?c=${data.recent_conversations[0].id}` : "/tutor"}>{data.recent_conversations[0] ? "Continue chat" : "Open tutor"}</Link>
          </motion.div>
          <motion.div className="stat-grid" variants={list} initial="hidden" animate="show">
            <motion.section variants={item} className="tile tile-usage" aria-label="Monthly usage">
              <Ring value={data.usage.tokens_used} max={data.usage.limit} label="Tokens used this month">
                <strong>{data.usage.limit > 0 ? Math.round((data.usage.tokens_used / data.usage.limit) * 100) : 0}%</strong><small>used</small>
              </Ring>
              <div>
                <h2>Monthly usage</h2>
                <p className="tile-big"><CountUp value={data.usage.tokens_used} /></p>
                <p className="muted">of {fmtNum(data.usage.limit)} tokens in {data.usage.period}</p>
                <Link to="/usage" className="tile-link">View breakdown</Link>
              </div>
            </motion.section>
            <motion.section variants={item} className="tile" aria-label="Subscription">
              <span className="tile-icon"><Icon name="card" size={18} /></span>
              <h2>Plan</h2>
              <p className="tile-big">{planLabel(data.subscription.plan_id)}</p>
              <p className="muted">{data.subscription.status === "active" ? `Active until ${fmtDate(data.subscription.expires_at)}${data.subscription.cancel_at_period_end ? ", will not renew" : ""}` : "No paid plan"}</p>
              <Link to="/billing" className="tile-link">{data.subscription.status === "active" ? "Manage plan" : "See upgrades"}</Link>
            </motion.section>
            <motion.section variants={item} className="tile" aria-label="Quiz average">
              <span className="tile-icon"><Icon name="quiz" size={18} /></span>
              <h2>Quiz average</h2>
              <p className="tile-big">{data.progress.average_quiz_percent !== null ? <CountUp value={data.progress.average_quiz_percent} format={(n) => `${Math.round(n * 10) / 10}%`} /> : "None yet"}</p>
              <p className="muted">{plural(data.progress.quizzes_taken, "attempt")}, {plural(data.progress.lessons_completed, "lesson")}</p>
              <Link to="/progress" className="tile-link">Open progress</Link>
            </motion.section>
            <motion.section variants={item} className="tile" aria-label="Documents">
              <span className="tile-icon"><Icon name="file" size={18} /></span>
              <h2>Documents</h2>
              <p className="tile-big"><CountUp value={data.documents.total} /></p>
              <p className="muted">{data.documents.total === 0 ? "Nothing uploaded yet" : "in your library"}</p>
              <Link to="/documents" className="tile-link">Open library</Link>
            </motion.section>
          </motion.div>

          <ActivityCard data={data} />

          <motion.div className="dash-cols" variants={list} initial="hidden" animate="show">
            <motion.div variants={item}>
              <Card title="Continue studying" actions={<Link to="/tutor">All chats</Link>}>
                {data.recent_conversations.length === 0 ? (
                  <EmptyState title="No conversations yet" icon="chat" action={<Link className="btn btn-primary" to="/tutor">Ask your first question</Link>}>Start a chat and it will be saved here so you can pick it up later.</EmptyState>
                ) : (
                  <ul className="rows">{data.recent_conversations.map((c) => (
                    <li key={c.id}><Link to={`/tutor?c=${c.id}`} className="row-link"><span className="row-ico"><Icon name="chat" size={16} /></span>
                      <span className="row-main"><strong>{c.title || "Untitled"}</strong><small>{plural(c.message_count, "message")}, {fmtDateTime(c.updated_at)}</small></span><Icon name="chevron" size={14} /></Link></li>))}</ul>
                )}
              </Card>
            </motion.div>

            <motion.div variants={item}>
              <Card title="Recent quiz results" actions={<Link to="/quizzes">Quizzes</Link>}>
                {data.recent_quiz_results.length === 0 ? (
                  <EmptyState title="No quiz results" icon="quiz" action={<Link className="btn btn-outline" to="/quizzes">Take a quiz</Link>}>Scores appear here after you submit a quiz.</EmptyState>
                ) : (
                  <ul className="rows">{data.recent_quiz_results.map((r, i) => (
                    <li key={i} className="score-row"><div><strong>{r.topic}</strong><small>{fmtDate(r.created_at)}</small></div>
                      <div className="score-bar"><Meter value={r.percent} max={100} label={`${r.topic} score`} /><span>{r.score}/{r.total}</span></div></li>))}</ul>
                )}
              </Card>
            </motion.div>

            <motion.div variants={item}>
              <Card title="Topics you are studying" actions={<Link to="/progress">Details</Link>}>
                {data.progress.topics.length === 0 ? (
                  <EmptyState title="Nothing tracked yet" icon="chart" action={<Link className="btn btn-outline" to="/lessons">Create a lesson</Link>}>Complete a lesson or quiz and your topics show up here.</EmptyState>
                ) : (
                  <ul className="rows">{data.progress.topics.slice(0, 5).map((t) => (
                    <li key={t.topic} className="score-row"><div><strong>{t.topic}</strong><small>{plural(t.lessons, "lesson")}, {plural(t.quiz_attempts, "quiz")}</small></div>
                      <div className="score-bar">{t.best_percent !== null ? <><Meter value={t.best_percent} max={100} label={`Best score for ${t.topic}`} /><span>{t.best_percent}%</span></> : <Badge>No quiz yet</Badge>}</div></li>))}</ul>
                )}
              </Card>
            </motion.div>

            <motion.div variants={item}>
              <Card title="Saved documents" actions={<Link to="/documents">Library</Link>}>
                {data.documents.total === 0 ? (
                  <EmptyState title="No documents" icon="file" action={<Link className="btn btn-outline" to="/documents">Upload a document</Link>}>Upload a PDF, TXT or Markdown file to ask questions about it.</EmptyState>
                ) : (
                  <ul className="rows">{data.documents.recent.map((d) => (
                    <li key={d.id}><Link to="/ask" className="row-link"><span className="row-ico"><Icon name="file" size={16} /></span>
                      <span className="row-main"><strong>{d.filename}</strong><small>Added {fmtDate(d.created_at)}</small></span>
                      <Badge tone={d.status === "ready" ? "ok" : "warn"}>{d.status}</Badge></Link></li>))}</ul>
                )}
              </Card>
            </motion.div>
          </motion.div>
        </>
      )}
    </>
  );
}
