import { animate, motion, useInView, useMotionValue, useReducedMotion, useSpring, type HTMLMotionProps } from "motion/react";
import { useCallback, useEffect, useRef, useState, type CSSProperties, type MouseEvent, type ReactNode } from "react";

/** Shared easing so every motion in the product feels related. */
export const EASE = [0.22, 1, 0.36, 1] as const;
export const SPRING = { type: "spring", stiffness: 380, damping: 32, mass: 0.8 } as const;

/** Fade and rise into view once. Used sparingly: for a handful of landing sections only. */
export function Reveal({ children, delay = 0, y = 18, className, as = "div", ...rest }:
  { children: ReactNode; delay?: number; y?: number; className?: string; as?: "div" | "li" | "article" | "section" } & Omit<HTMLMotionProps<"div">, "children">) {
  const reduce = useReducedMotion();
  const Tag = motion[as] as typeof motion.div;
  return (
    <Tag className={className} initial={reduce ? false : { opacity: 0, y }} whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-80px" }} transition={{ duration: 0.7, ease: EASE, delay }} {...rest}>{children}</Tag>
  );
}

/** Counts from 0 to `value` when scrolled into view. The final frame is always the exact value; reduced motion skips straight to it. */
export function CountUp({ value, format = (n: number) => Math.round(n).toLocaleString("en-IN"), duration = 1.1 }:
  { value: number; format?: (n: number) => string; duration?: number }) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true });
  const reduce = useReducedMotion();
  const [shown, setShown] = useState(reduce ? value : 0);
  useEffect(() => {
    if (reduce) { setShown(value); return; }
    if (!inView) return;
    const c = animate(0, value, { duration, ease: EASE, onUpdate: (v) => setShown(v), onComplete: () => setShown(value) });
    return () => c.stop();
  }, [inView, value, reduce, duration]);
  return <span ref={ref}>{format(shown)}</span>;
}

/** Button wrapper that leans a few pixels toward the cursor. Pointer devices only. */
export function Magnetic({ children, strength = 0.25 }: { children: ReactNode; strength?: number }) {
  const reduce = useReducedMotion();
  const x = useSpring(useMotionValue(0), { stiffness: 220, damping: 18 });
  const y = useSpring(useMotionValue(0), { stiffness: 220, damping: 18 });
  const onMove = (e: MouseEvent<HTMLSpanElement>) => {
    if (reduce) return;
    const r = e.currentTarget.getBoundingClientRect();
    x.set((e.clientX - (r.left + r.width / 2)) * strength); y.set((e.clientY - (r.top + r.height / 2)) * strength);
  };
  return <motion.span className="magnetic" style={{ x, y }} onMouseMove={onMove} onMouseLeave={() => { x.set(0); y.set(0); }}>{children}</motion.span>;
}

/** Card with a soft light that follows the cursor (CSS reads --mx / --my). */
export function SpotCard({ children, className = "", as = "article" }: { children: ReactNode; className?: string; as?: "article" | "div" }) {
  const onMove = useCallback((e: MouseEvent<HTMLElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    e.currentTarget.style.setProperty("--mx", `${e.clientX - r.left}px`);
    e.currentTarget.style.setProperty("--my", `${e.clientY - r.top}px`);
  }, []);
  const Tag = as;
  return <Tag className={`spot ${className}`} onMouseMove={onMove}>{children}</Tag>;
}

/** Placeholder block while real data loads (replaces bare spinners on data screens). */
export function Skeleton({ w = "100%", h = 16, r = 8, style }: { w?: number | string; h?: number | string; r?: number; style?: CSSProperties }) {
  return <span className="skeleton" aria-hidden="true" style={{ width: w, height: h, borderRadius: r, ...style }} />;
}

/** Splits text into words that rise in one after another. Runs once on mount (hero headline). */
export function WordRise({ text, delay = 0, step = 0.055 }: { text: string; delay?: number; step?: number }) {
  const reduce = useReducedMotion();
  return (
    <>
      {text.split(" ").map((w, i) => (
        <span key={i}><span className="word-mask"><motion.span className="word" initial={reduce ? false : { y: "110%" }} animate={{ y: 0 }}
          transition={{ duration: 0.8, ease: EASE, delay: delay + i * step }}>{w}</motion.span></span>{" "}</span>
      ))}
    </>
  );
}

/** Reveals text word by word. Presentation only: the full text is already in the DOM for assistive tech. */
export function WordReveal({ text, onDone, perWord = 0.018 }: { text: string; onDone?: () => void; perWord?: number }) {
  const reduce = useReducedMotion();
  const words = text.split(/(\s+)/);
  const [n, setN] = useState(reduce ? words.length : 0);
  useEffect(() => {
    if (reduce || n >= words.length) { if (n >= words.length) onDone?.(); return; }
    const t = setTimeout(() => setN((v) => Math.min(words.length, v + 2)), perWord * 1000);
    return () => clearTimeout(t);
  }, [n, words.length, reduce, perWord, onDone]);
  return (
    <>
      <span className="sr-only">{text}</span>
      <span aria-hidden="true">{words.slice(0, n).join("")}{n < words.length && <span className="caret" />}</span>
    </>
  );
}

/** Light / dark / system theme with persistence. Falls back silently if storage is unavailable. */
export type ThemeChoice = "system" | "light" | "dark";
export function useTheme() {
  const [choice, setChoice] = useState<ThemeChoice>(() => {
    try { const v = localStorage.getItem("lumina-theme"); return v === "light" || v === "dark" || v === "system" ? v : "dark"; } catch { return "dark"; }
  });
  useEffect(() => {
    const el = document.documentElement;
    if (choice === "system") el.removeAttribute("data-theme"); else el.setAttribute("data-theme", choice);
    try { localStorage.setItem("lumina-theme", choice); } catch { /* storage unavailable */ }
  }, [choice]);
  return [choice, setChoice] as const;
}

/** Soft light that follows the pointer, and feeds --mx/--my to the card under it so borders can glow. Pointer devices only. */
export function Spotlight() {
  useEffect(() => {
    if (window.matchMedia("(pointer: coarse)").matches || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let raf = 0;
    const root = document.documentElement;
    const move = (e: PointerEvent) => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        root.style.setProperty("--sx", `${e.clientX}px`); root.style.setProperty("--sy", `${e.clientY}px`);
        const el = (e.target as HTMLElement | null)?.closest?.(".glow, .card, .tile, .ob-card") as HTMLElement | null;
        if (el) { const r = el.getBoundingClientRect(); el.style.setProperty("--mx", `${e.clientX - r.left}px`); el.style.setProperty("--my", `${e.clientY - r.top}px`); }
      });
    };
    window.addEventListener("pointermove", move, { passive: true });
    return () => { window.removeEventListener("pointermove", move); cancelAnimationFrame(raf); };
  }, []);
  return <div className="spotlight" aria-hidden="true" />;
}

/** Deterministic star field (one element, many box-shadows) so server and client always match. */
export function Stars({ count = 110 }: { count?: number }) {
  let seed = 7; const rnd = () => { seed = (seed * 16807) % 2147483647; return seed / 2147483647; };
  const dots = Array.from({ length: count }, () => `${(rnd() * 100).toFixed(2)}vw ${(rnd() * 100).toFixed(2)}vh 0 ${rnd() < 0.15 ? 1 : 0}px rgb(255 255 255 / ${(0.25 + rnd() * 0.6).toFixed(2)})`).join(",");
  return <div className="stars" aria-hidden="true"><i style={{ boxShadow: dots }} /></div>;
}
