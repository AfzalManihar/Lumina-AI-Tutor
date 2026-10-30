import { useState } from "react";
import { api, errorText } from "../api/client";
import type { Order, Payment, Plan, Subscription } from "../api/types";
import { Badge, Button, Card, Confirm, EmptyState, ErrorBanner, Loading, Notice, PageHeader } from "../components/ui";
import { useLoad } from "../hooks";
import { fmtDate, fmtNum, fmtPrice, planLabel } from "../lib";

interface RazorpaySuccess { razorpay_order_id: string; razorpay_payment_id: string; razorpay_signature: string }
interface RazorpayInstance { open: () => void; on: (ev: string, cb: (r: { error?: { description?: string } }) => void) => void }
declare global { interface Window { Razorpay?: new (opts: Record<string, unknown>) => RazorpayInstance } }

/** Loads Razorpay's hosted checkout script only when the student chooses to pay. */
function loadCheckout(): Promise<void> {
  if (window.Razorpay) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = "https://checkout.razorpay.com/v1/checkout.js"; s.async = true;
    s.onload = () => resolve(); s.onerror = () => reject(new Error("Could not load the payment window. Check your connection."));
    document.body.appendChild(s);
  });
}

export function Billing() {
  const plans = useLoad(() => api.get<{ plans: Plan[] }>("/billing/plans"));
  const sub = useLoad(() => api.get<Subscription>("/billing/subscription"));
  const hist = useLoad(() => api.get<{ items: Payment[] }>("/billing/history", { limit: 50 }));
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null); const [msg, setMsg] = useState<string | null>(null);
  const [confirmCancel, setConfirmCancel] = useState(false);

  const refresh = async () => { await Promise.all([sub.reload(), hist.reload()]); };

  async function buy(plan: Plan) {
    setErr(null); setMsg(null); setBusy(plan.id);
    try {
      const order = await api.post<Order>("/billing/orders", { plan_id: plan.id });
      await loadCheckout();
      await new Promise<void>((resolve) => {
        const rz = new window.Razorpay!({
          key: order.key_id, order_id: order.order_id, amount: order.amount, currency: order.currency, name: "Lumina AI Tutor",
          description: `${plan.name} plan`,
          // The browser only relays Razorpay's signed response; the server verifies it before granting access.
          handler: async (r: RazorpaySuccess) => {
            try {
              await api.post("/billing/verify", r);
              setMsg(`Payment verified. Your ${plan.name} plan is active.`);
            } catch (e) { setErr(errorText(e)); }
            await refresh(); resolve();
          },
          modal: { ondismiss: () => { setMsg("Checkout closed. You have not been charged unless a payment completed; the status below shows the result."); void refresh(); resolve(); } },
        });
        rz.on("payment.failed", (r) => { setErr(r.error?.description ?? "The payment failed. You can try again."); void refresh(); });
        rz.open();
      });
    } catch (e) { setErr(errorText(e)); } finally { setBusy(null); }
  }

  async function cancel() {
    setConfirmCancel(false); setErr(null);
    try { await api.post("/billing/cancel"); setMsg("Your plan will not renew. You keep access until it expires."); await sub.reload(); }
    catch (e) { setErr(errorText(e)); }
  }
  const current = sub.data?.plan_id ?? "free";
  return (
    <>
      <PageHeader title="Plans and billing">Paid access is granted only after the server verifies the payment signature or a signed webhook from Razorpay.</PageHeader>
      <ErrorBanner message={err ?? plans.error ?? sub.error} onRetry={plans.error ? plans.reload : undefined} />
      {msg && <Notice tone="ok">{msg}</Notice>}
      {sub.data && (
        <Card title="Your subscription">
          <p className="big">{planLabel(sub.data.plan_id)}</p>
          <p className="muted">{sub.data.status === "active" ? `Active until ${fmtDate(sub.data.expires_at)}${sub.data.cancel_at_period_end ? ". Will not renew." : "."}` : "You are on the free plan."}</p>
          {sub.data.status === "active" && !sub.data.cancel_at_period_end && (confirmCancel
            ? <Confirm message="Stop renewal? You keep access until the end date." yesLabel="Stop renewal" onYes={cancel} onNo={() => setConfirmCancel(false)} />
            : <Button variant="secondary" onClick={() => setConfirmCancel(true)}>Cancel renewal</Button>)}
        </Card>
      )}
      {plans.loading && !plans.data && <Loading label="Loading plans" />}
      <div className="plan-row">
        {plans.data?.plans.map((p) => (
          <article key={p.id} className={`plan${p.id === current ? " current" : ""}`}>
            <h2>{p.name} {p.id === current && <Badge tone="ok">Current</Badge>}</h2>
            <p className="price">{p.price_inr === 0 ? "₹0" : fmtPrice(p.price_inr)}<small>{p.price_inr > 0 ? " for 30 days" : " forever"}</small></p>
            <ul><li>{fmtNum(p.monthly_token_limit)} tokens per month</li><li>Up to {p.max_documents} documents</li>{p.features.filter((f) => !/documents?$/i.test(f)).map((f) => <li key={f}>{f}</li>)}</ul>
            {p.price_inr > 0 && <Button loading={busy === p.id} disabled={busy !== null} onClick={() => buy(p)}>{p.id === current ? "Extend" : "Choose"} {p.name}</Button>}
          </article>
        ))}
      </div>
      <Card title="Billing history">
        {hist.loading && !hist.data && <Loading label="Loading history" />}
        {hist.data?.items.length === 0 && <EmptyState title="No payments yet" />}
        {!!hist.data?.items.length && (
          <div className="tablewrap"><table>
            <thead><tr><th>Date</th><th>Plan</th><th>Amount</th><th>Status</th><th>Order</th></tr></thead>
            <tbody>{hist.data.items.map((p) => (
              <tr key={p.order_id}><td>{fmtDate(p.created_at)}</td><td>{planLabel(p.plan_id)}</td><td>₹{(p.amount / 100).toLocaleString("en-IN")}</td>
                <td><Badge tone={p.status === "succeeded" ? "ok" : p.status === "pending" ? "neutral" : "warn"}>{p.status}</Badge></td><td><code>{p.order_id}</code></td></tr>))}</tbody>
          </table></div>)}
      </Card>
    </>
  );
}
