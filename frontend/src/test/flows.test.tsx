import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "../auth/AuthContext";
import { Citations } from "../components/Citations";
import { StepList } from "../components/StepList";
import { Login } from "../pages/AuthPages";
import { MemoryPage } from "../pages/Memory";
import { stepLabel } from "../lib";

type Handler = (url: string, init?: RequestInit) => { status?: number; body?: unknown };
let handler: Handler;
const calls: { url: string; method: string; body?: string }[] = [];

beforeEach(() => {
  calls.length = 0;
  handler = () => ({ status: 401, body: { error: { code: "unauthorized", message: "no session" } } });
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    calls.push({ url, method: init?.method ?? "GET", body: init?.body as string | undefined });
    const r = handler(url, init);
    const status = r.status ?? 200;
    return { ok: status < 400, status, json: async () => r.body } as Response;
  }));
});

const wrap = (ui: React.ReactNode, path = "/") => render(<MemoryRouter initialEntries={[path]}><AuthProvider>{ui}</AuthProvider></MemoryRouter>);

describe("login", () => {
  it("shows a safe server error and keeps the user on the form", async () => {
    handler = (url) => url.endsWith("/auth/login")
      ? { status: 401, body: { error: { code: "invalid_credentials", message: "Invalid email or password" } } }
      : { status: 401, body: {} };
    wrap(<Login />);
    await userEvent.type(await screen.findByLabelText("Email"), "a@b.co");
    await userEvent.type(screen.getByLabelText("Password"), "wrong-pass1");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Invalid email or password");
    expect(calls.some((c) => c.url.endsWith("/auth/login") && c.method === "POST")).toBe(true);
  });
});

describe("citations", () => {
  const cite = { cite_id: "S1", chunk_id: "c1", document_id: "d1", filename: "notes.pdf", page: 2, section: null, passage: "The Calvin cycle occurs in the stroma.", score: 0.83 };
  it("expands to the stored passage with file and page", async () => {
    render(<Citations citations={[cite]} />);
    const btn = screen.getByRole("button", { name: /notes\.pdf, page 2/ });
    expect(btn).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText(/Calvin cycle/)).toBeNull();
    await userEvent.click(btn);
    expect(btn).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText(/Calvin cycle occurs in the stroma/)).toBeInTheDocument();
  });
});

describe("workflow status", () => {
  it("lists only steps the backend recorded and hides internals", () => {
    render(<StepList steps={[{ name: "understand", status: "ok" }, { name: "retrieve", status: "ok" }, { name: "secret_internal", status: "ok" }]} />);
    expect(screen.getByText(/2 steps/)).toBeInTheDocument();
    expect(screen.queryByText(/secret_internal/)).toBeNull();
  });
  it("renders nothing when there are no recorded steps", () => {
    const { container } = render(<StepList steps={[]} />);
    expect(container).toBeEmptyDOMElement();
  });
  it("labels tool steps from the real tool name", () => { expect(stepLabel("tool:calculate")).toBe("Used tool: calculate"); });
});

describe("memory page", () => {
  const mem = { id: "m1", text: "Prefers short explanations", type: "preference", source: "user_manual", created_at: "2026-10-01T00:00:00Z", updated_at: "2026-10-01T00:00:00Z" };
  it("lists, deletes after confirmation, and explains when memory is off", async () => {
    let items = [mem]; let enabled = true;
    handler = (url, init) => {
      if (url.includes("/auth/refresh")) return { status: 401, body: {} };
      if (url.includes("/memory/m1") && init?.method === "DELETE") { items = []; return { status: 204 }; }
      if (url.includes("/memory")) return { body: { items, total: items.length, enabled } };
      return { status: 404, body: {} };
    };
    const { unmount } = wrap(<MemoryPage />);
    expect(await screen.findByText("Prefers short explanations")).toBeInTheDocument();
    await userEvent.click(screen.getAllByRole("button", { name: "Delete" })[0]);
    await userEvent.click(await screen.findByRole("button", { name: "Delete" }));  // inline confirm
    await waitFor(() => expect(screen.getByText(/Nothing saved yet/)).toBeInTheDocument());
    expect(calls.some((c) => c.method === "DELETE" && c.url.endsWith("/memory/m1"))).toBe(true);
    unmount();
    enabled = false;
    wrap(<MemoryPage />);
    expect(await screen.findByText(/Memory is turned off/)).toBeInTheDocument();
  });
});
