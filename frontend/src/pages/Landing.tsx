import { AnimatePresence, motion, useInView, useMotionValueEvent, useReducedMotion, useScroll, useSpring, useTransform } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { Plan } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { Logo } from "../components/Layout";
import { EASE, Magnetic, Reveal, SPRING, SpotCard, Stars, WordReveal, WordRise } from "../components/fx";
import { Icon, type IconName } from "../components/ui";
import { fmtNum, fmtPrice } from "../lib";

/* The demo uses fixed sample text and is labelled as an example. It makes no network calls. */
const SAMPLE = [
  { id: "p1", text: "Plants lose water through stomata, which also admit carbon dioxide for photosynthesis." },
  { id: "p2", text: "The Calvin cycle takes place in the stroma of the chloroplast. Rubisco catalyses the first major step of carbon fixation." },
  { id: "p3", text: "The light-dependent reactions occur in the thylakoid membranes and produce ATP and NADPH." },
];
const QUESTIONS: { q: string; a: string; hit: string | null }[] = [
  { q: "Where does the Calvin cycle happen?", a: "In the stroma of the chloroplast.", hit: "p2" },
  { q: "What do the light reactions produce?", a: "ATP and NADPH.", hit: "p3" },
  { q: "Who discovered rubisco?", a: "Your notes don’t say who discovered rubisco, so I can’t answer that from this document.", hit: null },
];

/** Plays once on load (typed question, passage lights up, answer appears), then replays when a question is chosen. */
function EvidenceDemo() {
  const reduce = useReducedMotion();
  const [i, setI] = useState(0);
  const [typed, setTyped] = useState(0);
  const [stage, setStage] = useState<0 | 1 | 2>(0);
  const first = useRef(true);
  const cur = QUESTIONS[i];

  useEffect(() => {
    if (reduce) { setTyped(cur.q.length); setStage(2); return; }
    setTyped(0); setStage(0);
    const timers: number[] = []; let iv = 0;
    const startAt = first.current ? 1300 : 80; first.current = false;
    timers.push(window.setTimeout(() => {
      let n = 0;
      iv = window.setInterval(() => {
        n += 1; setTyped(n);
        if (n >= cur.q.length) {
          window.clearInterval(iv);
          timers.push(window.setTimeout(() => setStage(1), 380), window.setTimeout(() => setStage(2), 1250));
        }
      }, 26);
    }, startAt));
    return () => { window.clearInterval(iv); timers.forEach((t) => window.clearTimeout(t)); };
  }, [i, reduce, cur.q.length]);

  return (
    <figure className="demo" aria-label="Interactive example with sample text">
      <div className="demo-doc">
        <p className="demo-file"><Icon name="file" size={14} />Biology notes.pdf, page 2</p>
        {SAMPLE.map((p) => (<p key={`${p.id}-${i}`} className={`demo-para${stage >= 1 && cur.hit === p.id ? " lit" : ""}`}>{p.text}</p>))}
      </div>
      <div className="demo-chat">
        <div className="demo-qs" role="group" aria-label="Try a question">
          {QUESTIONS.map((x, n) => (
            <button key={x.q} type="button" className={`chip${n === i ? " chip-on" : ""}`} aria-pressed={n === i} onClick={() => setI(n)}>{x.q}</button>
          ))}
        </div>
        <div className="demo-user" aria-live="off"><span>{cur.q.slice(0, typed)}</span>{stage === 0 && !reduce && <span className="caret caret-light" />}</div>
        <div className="demo-slot" aria-live="polite">
          <AnimatePresence mode="wait">
            {stage === 2 && (
              <motion.div key={i} className="demo-answer" initial={reduce ? false : { opacity: 0, y: 10, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0 }} transition={{ duration: 0.35, ease: EASE }}>
                {cur.hit ? <span className="badge badge-lumen">From your document</span> : <span className="badge badge-warn">Not in your document</span>}
                <p><WordReveal text={cur.a} /></p>
                {cur.hit && (
                  <motion.span className="cite-chip" initial={reduce ? false : { opacity: 0, scale: 0.6 }} animate={{ opacity: 1, scale: 1 }}
                    transition={{ ...SPRING, delay: reduce ? 0 : 0.5 }}><span className="cite-id">S1</span>Biology notes.pdf, page 2</motion.span>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
      <figcaption>Sample text, not live data. Pick a question to see the passage behind the answer.</figcaption>
    </figure>
  );
}

const TOUR: { id: string; label: string; img: string; title: string; body: string }[] = [
  { id: "dash", label: "Dashboard", img: "/preview/dashboard.webp", title: "Your studying at a glance", body: "Usage, quiz scores, topics and recent chats, all read from your own account." },
  { id: "chat", label: "Tutor chat", img: "/preview/chat.webp", title: "Answers with the passage attached", body: "Open any citation to read the exact text and page it came from. Follow-up questions are one click away." },
  { id: "docs", label: "Documents", img: "/preview/documents.webp", title: "Your library, indexed privately", body: "Upload PDF, TXT or Markdown. Re-index or delete a file whenever you like." },
];

function ProductTour() {
  const [tab, setTab] = useState(0);
  const reduce = useReducedMotion();
  const t = TOUR[tab];
  return (
    <div className="tour">
      <div className="tour-tabs" role="tablist" aria-label="Product tour">
        {TOUR.map((x, n) => (
          <button key={x.id} role="tab" aria-selected={n === tab} className={`tour-tab${n === tab ? " on" : ""}`} onClick={() => setTab(n)}>
            {n === tab && <motion.span layoutId="tour-ind" className="tour-ind" transition={SPRING} />}<span>{x.label}</span>
          </button>
        ))}
      </div>
      <p className="tour-copy" aria-live="polite"><strong>{t.title}.</strong> {t.body}</p>
      <div className="tour-frame" role="tabpanel">
        <AnimatePresence mode="wait">
          <motion.img key={t.id} src={t.img} alt={`${t.label} screen with sample data`} width={1366} height={860} loading="lazy"
            initial={reduce ? false : { opacity: 0, y: 14, scale: 0.985 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.38, ease: EASE }} />
        </AnimatePresence>
      </div>
      <p className="tour-note">Preview built from sample data.</p>
    </div>
  );
}

const FAQ = [
  ["Does Lumina answer from the internet?", "No. When you pick documents, answers come only from those documents. Without documents the tutor answers from general knowledge and labels the answer that way."],
  ["Which files can I upload?", "PDF, TXT and Markdown, up to 10 MB each by default. Scanned PDFs with no text and password-protected PDFs are rejected with a clear message."],
  ["Can the AI still be wrong?", "Yes. That is why every document-based claim carries a citation you can open and read. Check anything important against your source."],
  ["How does payment work?", "Plans are billed in INR through Razorpay. Your plan is activated only after our server verifies the payment, never from the browser alone."],
  ["Who can see my documents and chats?", "They are stored against your account and every request is checked for ownership. You can delete documents, conversations and memories whenever you like."],
] as const;

function FaqItem({ q, a }: { q: string; a: string }) {
  const [open, setOpen] = useState(false);
  const id = `faq-${q.length}-${a.length}`;
  return (
    <div className="faq-item">
      <h3><button aria-expanded={open} aria-controls={id} onClick={() => setOpen((v) => !v)}>{q}<motion.span animate={{ rotate: open ? 180 : 0 }} transition={{ duration: 0.25 }}><Icon name="chevron" size={18} /></motion.span></button></h3>
      <AnimatePresence initial={false}>
        {open && (<motion.div id={id} role="region" initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.3, ease: EASE }} style={{ overflow: "hidden" }}><p>{a}</p></motion.div>)}
      </AnimatePresence>
    </div>
  );
}


function QuizMock() {
  const ref = useRef<HTMLDivElement>(null);
  const seen = useInView(ref, { once: true, margin: "-60px" });
  const opts = ["Thylakoid membrane", "Stroma", "Cytoplasm"];
  return (
    <div ref={ref} className="mock-quiz" aria-hidden="true">
      <p>Where does the Calvin cycle occur?</p>
      {opts.map((o, n) => (<span key={o} className={`mq-opt${seen && n === 1 ? " mq-right" : ""}`}>{o}{seen && n === 1 && <Icon name="check" size={14} />}</span>))}
    </div>
  );
}


const SUBJECTS = ["Biology", "Organic chemistry", "Calculus", "World history", "Constitutional law", "Microeconomics", "Physics", "Anatomy", "Statistics", "Literature", "Computer networks", "Accounting"];
function Marquee({ reverse = false }: { reverse?: boolean }) {
  const row = [...SUBJECTS, ...SUBJECTS];
  return (
    <div className={`ob-marq${reverse ? " rev" : ""}`} aria-hidden="true">
      <div className="ob-marq-track">{row.map((s, n) => <span key={n}><i />{s}</span>)}</div>
    </div>
  );
}

const STORY: { icon: IconName; title: string; body: string }[] = [
  { icon: "upload", title: "Drop in your material", body: "Textbooks, class notes, articles. Lumina extracts the text and indexes it for your account only." },
  { icon: "chat", title: "Ask like you'd ask a friend", body: "Ask a question, request a lesson, or generate a quiz at the difficulty you choose." },
  { icon: "check", title: "See the proof", body: "Open any citation to read the exact passage and page. If your notes don't answer it, you're told." },
];
const FILES = [["Biology notes.pdf", "62 passages"], ["Algebra chapter 3.pdf", "97 passages"], ["Revision summary.md", "18 passages"]];

function StoryStage({ step }: { step: number }) {
  return (
    <div className="ob-stage glow" aria-hidden="true">
      <div className="ob-stage-bar"><i /><i /><i /><span>{["Library", "Tutor chat", "Citation"][step]}</span></div>
      <AnimatePresence mode="wait">
        <motion.div key={step} className="ob-stage-body" initial={{ opacity: 0, y: 18, filter: "blur(6px)" }} animate={{ opacity: 1, y: 0, filter: "blur(0px)" }} exit={{ opacity: 0, y: -12, filter: "blur(4px)" }} transition={{ duration: 0.4, ease: EASE }}>
          {step === 0 && FILES.map(([f, c], n) => (
            <div key={f} className="ob-file"><Icon name="file" size={18} /><div><strong>{f}</strong><span className="ob-bar"><motion.i initial={{ width: 0 }} animate={{ width: "100%" }} transition={{ duration: 1.1, delay: 0.2 + n * 0.25, ease: EASE }} /></span></div>
              <motion.em initial={{ opacity: 0, scale: 0.7 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: 1.1 + n * 0.25 }}>{c}</motion.em></div>
          ))}
          {step === 1 && (<>
            <div className="ob-q">Where does the Calvin cycle happen?</div>
            <div className="ob-think"><i /><i /><i /><span>Searching your notes</span></div>
            <div className="ob-q ob-q2">Quiz me on this</div>
          </>)}
          {step === 2 && (<>
            <span className="badge badge-lumen">From your document</span>
            <p className="ob-ans">The Calvin cycle takes place in the stroma of the chloroplast <b>S1</b></p>
            <blockquote className="ob-pass"><small>Biology notes.pdf, page 2</small>The Calvin cycle takes place in the <mark>stroma of the chloroplast</mark>. Rubisco catalyses the first major step of carbon fixation.</blockquote>
          </>)}
        </motion.div>
      </AnimatePresence>
      <p className="ob-stage-note">Illustration with sample text</p>
    </div>
  );
}

function Story() {
  const ref = useRef<HTMLElement>(null);
  const [step, setStep] = useState(0);
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start start", "end end"] });
  useMotionValueEvent(scrollYProgress, "change", (v) => setStep(Math.max(0, Math.min(2, Math.floor(v * 3)))));
  const fill = useSpring(scrollYProgress, { stiffness: 120, damping: 30 });
  return (
    <section id="how" className="ob-story" ref={ref}>
      <div className="ob-stick">
        <div className="ob-wrap ob-story-grid">
          <div>
            <p className="ob-kicker">How it works</p>
            <h2 className="ob-h2">From a stack of PDFs to <em>answers you can verify.</em></h2>
            <ol className="ob-steps">
              {STORY.map((s, n) => (
                <li key={s.title} className={n === step ? "on" : n < step ? "done" : ""}>
                  <span className="ob-step-ico"><Icon name={n < step ? "check" : s.icon} size={18} /></span>
                  <div><h3>{s.title}</h3><p>{s.body}</p></div>
                </li>
              ))}
            </ol>
            <div className="ob-prog" aria-hidden="true"><motion.i style={{ scaleX: fill }} /></div>
          </div>
          <StoryStage step={step} />
        </div>
      </div>
    </section>
  );
}

export function Landing() {
  const { user } = useAuth();
  const reduce = useReducedMotion();
  const [plans, setPlans] = useState<Plan[] | null>(null);
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => { api.publicGet<{ plans: Plan[] }>("/billing/plans").then((r) => setPlans(r.plans)).catch(() => setPlans(null)); }, []);
  useEffect(() => { const f = () => setScrolled(window.scrollY > 8); f(); window.addEventListener("scroll", f, { passive: true }); return () => window.removeEventListener("scroll", f); }, []);

  const { scrollYProgress } = useScroll();
  const bar = useSpring(scrollYProgress, { stiffness: 140, damping: 30 });
  const heroRef = useRef<HTMLElement>(null);
  const { scrollYProgress: hp } = useScroll({ target: heroRef, offset: ["start start", "end start"] });
  const tilt = useTransform(hp, [0, 0.6], reduce ? [0, 0] : [14, 0]);
  const scl = useTransform(hp, [0, 0.6], reduce ? [1, 1] : [0.94, 1]);
  const f1 = useTransform(hp, [0, 1], reduce ? [0, 0] : [0, -120]);
  const f2 = useTransform(hp, [0, 1], reduce ? [0, 0] : [0, -60]);
  const f3 = useTransform(hp, [0, 1], reduce ? [0, 0] : [0, -170]);

  const cta = user ? "/app" : "/register";
  const freePlan = plans?.find((p) => p.price_inr === 0);
  return (
    <div className="ob">
      <motion.div className="scroll-bar" style={{ scaleX: bar }} aria-hidden="true" />
      <Stars />
      <header className={`ob-nav${scrolled ? " scrolled" : ""}`}>
        <div className="ob-nav-in">
          <Link to="/" aria-label="Lumina home"><Logo onDark /></Link>
          <nav aria-label="Page sections" className="ob-links"><a href="/" onClick={(e) => { e.preventDefault(); window.scrollTo({ top: 0, behavior: reduce ? "auto" : "smooth" }); }}>Home</a><a href="#tour">Product</a><a href="#how">How it works</a><a href="#features">Features</a>{plans && <a href="#pricing">Pricing</a>}<a href="#faq">FAQ</a></nav>
          <div className="ob-auth">
            {user ? <Link className="btn btn-primary btn-sm" to="/app">Open dashboard</Link> : <>
              <Link className="btn btn-ghost btn-sm" to="/login">Sign in</Link>
              <Link className="btn btn-primary btn-sm" to="/register">Start free</Link></>}
          </div>
        </div>
      </header>

      <section className="ob-hero" ref={heroRef}>
        <div className="ob-beam" aria-hidden="true"><i /><i /></div>
        <div className="ob-wrap ob-hero-in">
          <motion.p className="ob-pill" initial={reduce ? false : { opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, ease: EASE }}>
            <span className="ob-dot" />An AI tutor that shows its sources
          </motion.p>
          <h1 className="ob-h1">
            <span className="ob-l"><WordRise text="Study from your notes." delay={0.15} /></span>
            <span className="ob-l ob-grad"><WordRise text="Get the proof." delay={0.55} /></span>
          </h1>
          <motion.p className="ob-sub" initial={reduce ? false : { opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7, ease: EASE, delay: 0.95 }}>
            Upload your PDFs and class notes. Lumina answers from them, lights up the exact passage it used, and tells you plainly when your documents don’t have the answer.
          </motion.p>
          <motion.div className="ob-cta" initial={reduce ? false : { opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7, ease: EASE, delay: 1.1 }}>
            <Magnetic><Link className="btn btn-primary btn-lg" to={cta}>{user ? "Open dashboard" : "Start free"}</Link></Magnetic>
            <a className="btn btn-glass btn-lg" href="#tour">See the product</a>
          </motion.div>
          {freePlan && <p className="ob-note">Free plan: {fmtNum(freePlan.monthly_token_limit)} tokens a month. No card needed.</p>}

          <div className="ob-stagewrap">
            <motion.div className="ob-float ob-f1 glow" style={{ y: f1 }} initial={reduce ? false : { opacity: 0, x: -30 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 1.5, duration: 0.8, ease: EASE }}><span className="cite-chip"><span className="cite-id">S1</span>Biology notes.pdf, page 2</span></motion.div>
            <motion.div className="ob-float ob-f2 glow" style={{ y: f2 }} initial={reduce ? false : { opacity: 0, x: 30 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 1.7, duration: 0.8, ease: EASE }}><Icon name="quiz" size={16} />Quiz score <b>4/5</b></motion.div>
            <motion.div className="ob-float ob-f3 glow" style={{ y: f3 }} initial={reduce ? false : { opacity: 0, x: 30 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 1.9, duration: 0.8, ease: EASE }}><Icon name="alert" size={16} />Not in your document</motion.div>
            <motion.div className="ob-window" style={{ rotateX: tilt, scale: scl }} initial={reduce ? false : { opacity: 0, y: 60 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 1.1, ease: EASE, delay: 0.5 }}>
              <div className="ob-window-bar"><i /><i /><i /><span>lumina.app / tutor</span></div>
              <EvidenceDemo />
            </motion.div>
          </div>
        </div>
      </section>

      <section className="ob-marq-sec" aria-label="Works with any subject">
        <p className="ob-kicker ob-center">Bring any subject. Lumina reads whatever you upload.</p>
        <Marquee /><Marquee reverse />
      </section>

      <section id="tour" className="ob-section">
        <div className="ob-wrap">
          <Reveal><p className="ob-kicker">Inside the product</p><h2 className="ob-h2">A calm workspace <em>built around your material.</em></h2></Reveal>
          <Reveal delay={0.1}><ProductTour /></Reveal>
        </div>
      </section>

      <Story />

      <section id="features" className="ob-section">
        <div className="ob-wrap">
          <Reveal><p className="ob-kicker">Trust, by design</p><h2 className="ob-h2">Built so you can <em>trust what you read.</em></h2></Reveal>
          <div className="bento">
            <Reveal className="bento-a"><SpotCard className="ob-card">
              <h3>Every answer shows its source</h3>
              <p>Citations carry the file name, page and the stored passage, not a paraphrase from the model. Claims that no passage supports are removed before you see the answer.</p>
              <div className="mock-cite"><span className="cite-chip"><span className="cite-id">S1</span>Biology notes.pdf, page 2</span>
                <blockquote className="passage"><p>The Calvin cycle takes place in the stroma of the chloroplast.</p></blockquote></div>
            </SpotCard></Reveal>
            <Reveal className="bento-b" delay={0.08}><SpotCard className="ob-card">
              <h3>Lessons and quizzes from your material</h3>
              <p>Pick a topic and difficulty, or build from your documents. The answer key is revealed only after you submit.</p>
              <QuizMock />
            </SpotCard></Reveal>
            <Reveal className="bento-c" delay={0.08}><SpotCard className="ob-card">
              <h3>You decide what it remembers</h3>
              <p>Nothing is saved unless you approve it. View, edit or delete memories any time, or switch memory off.</p>
            </SpotCard></Reveal>
            <Reveal className="bento-d" delay={0.12}><SpotCard className="ob-card ob-card-lit">
              <Icon name="alert" size={22} />
              <div><h3>It says when it doesn’t know</h3><p>If retrieval finds nothing relevant, you get an honest “not enough evidence” message instead of an improvised answer.</p></div>
            </SpotCard></Reveal>
          </div>
        </div>
      </section>

      {plans && plans.length > 0 && (
        <section id="pricing" className="ob-section">
          <div className="ob-wrap">
            <Reveal><p className="ob-kicker">Pricing</p><h2 className="ob-h2">Simple plans, <em>in rupees.</em></h2></Reveal>
            <div className="price-row">
              {plans.map((p, n) => (
                <Reveal key={p.id} delay={n * 0.08}>
                  <SpotCard className={`ob-card price-card${p.id === "pro" ? " price-feature" : ""}`}>
                    {p.id === "pro" && <span className="ob-tag">Most chosen</span>}
                    <h3>{p.name}</h3>
                    <p className="price">{p.price_inr === 0 ? "₹0" : fmtPrice(p.price_inr)}<small>{p.price_inr > 0 ? " for 30 days" : " forever"}</small></p>
                    <ul>
                      <li><Icon name="check" size={16} />{fmtNum(p.monthly_token_limit)} tokens each month</li>
                      <li><Icon name="check" size={16} />Up to {p.max_documents} documents</li>
                      {p.features.filter((f) => !/documents?$/i.test(f)).map((f) => <li key={f}><Icon name="check" size={16} />{f}</li>)}
                    </ul>
                    <Link className={`btn ${p.id === "pro" ? "btn-lumen" : "btn-glass"}`} to={cta}>{p.price_inr === 0 ? "Start free" : `Choose ${p.name}`}</Link>
                  </SpotCard>
                </Reveal>
              ))}
            </div>
          </div>
        </section>
      )}

      <section id="faq" className="ob-section">
        <div className="ob-wrap lp-faq">
          <Reveal><p className="ob-kicker">FAQ</p><h2 className="ob-h2">Questions <em>students ask.</em></h2></Reveal>
          <div>{FAQ.map(([q, a]) => <FaqItem key={q} q={q} a={a} />)}</div>
        </div>
      </section>

      <section className="ob-final">
        <div className="ob-beam ob-beam-final" aria-hidden="true"><i /><i /></div>
        <div className="ob-wrap ob-final-in">
          <Reveal><h2>Bring your next exam’s notes.<br /><em>Get answers with receipts.</em></h2></Reveal>
          <Reveal delay={0.1}><Magnetic><Link className="btn btn-lumen btn-lg" to={cta}>{user ? "Open dashboard" : "Create your free account"}</Link></Magnetic></Reveal>
        </div>
      </section>

      <footer className="ob-foot">
        <div className="ob-wrap ob-foot-in">
          <Logo onDark />
          <nav aria-label="Footer"><a href="#tour">Product</a><a href="#how">How it works</a><a href="#faq">FAQ</a>{!user && <Link to="/login">Sign in</Link>}</nav>
          <p>AI answers can be wrong. Check important facts against your sources.</p>
          <p className="ob-by">Designed and built by <strong>Afzal Manihar</strong></p>
        </div>
        <div className="ob-mark" aria-hidden="true">Lumina</div>
      </footer>
    </div>
  );
}
