import React, { useMemo, useState } from "react";
import { apiPost, apiGet } from "../api";

type Session = { id: number; created_at: number; message_count: number };

export default function Query() {
  const examples = useMemo(
    () => [
      "Remember that my preferred language is Russian.",
      "Summarize what you know about me from memory.",
      "Store a short summary of this project in memory.",
      "I have Ollama locally. Build me a plan for an agent with vector memory.",
    ],
    []
  );

  const [q, setQ] = useState(examples[0]);
  const [out, setOut] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const [showDebug, setShowDebug] = useState(true);

  const [sessions, setSessions] = useState<Session[]>([]);
  const [sessionId, setSessionId] = useState<number | "new">("new");
  const [remember, setRemember] = useState(true);

  async function refreshSessions() {
    const r = await apiGet("/api/sessions");
    setSessions(r.sessions || []);
  }

  async function run() {
    setErr("");
    setOut(null);
    setLoading(true);
    try {
      const sid = sessionId === "new" ? null : sessionId;
      const res = await apiPost("/api/query", { query: q, session_id: sid, remember, max_steps: 6 });
      setOut(res);
      await refreshSessions();
      if (sessionId === "new" && res?.session_id) setSessionId(res.session_id);
    } catch (e: any) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  }

  async function newSession() {
    const r = await apiPost("/api/sessions/new", {});
    await refreshSessions();
    setSessionId(r.session_id);
    setOut(null);
  }

  async function copy(text: string) {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      // ignore
    }
  }

  return (
    <div>
      <h3>Query</h3>

      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
        <button onClick={refreshSessions} style={{ padding: "6px 10px" }}>
          Refresh sessions
        </button>
        <button onClick={newSession} style={{ padding: "6px 10px" }}>
          New session
        </button>

        <label style={{ display: "flex", gap: 6, alignItems: "center", fontSize: 13 }}>
          session
          <select
            value={sessionId}
            onChange={(e) => setSessionId(e.target.value === "new" ? "new" : Number(e.target.value))}
          >
            <option value="new">new</option>
            {sessions.map((s) => (
              <option key={s.id} value={s.id}>
                {s.id} ({s.message_count})
              </option>
            ))}
          </select>
        </label>

        <label style={{ display: "flex", gap: 6, alignItems: "center", fontSize: 13 }}>
          <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} />
          allow remember
        </label>

        <label style={{ display: "flex", gap: 6, alignItems: "center", fontSize: 13 }}>
          <input
            type="checkbox"
            checked={showDebug}
            onChange={(e) => setShowDebug(e.target.checked)}
          />
          debug
        </label>
      </div>

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 10, marginBottom: 8 }}>
        {examples.map((x) => (
          <button key={x} onClick={() => setQ(x)} style={{ padding: "6px 10px" }}>
            example
          </button>
        ))}
      </div>

      <textarea value={q} onChange={(e) => setQ(e.target.value)} rows={6} style={{ width: "100%", padding: 10 }} />

      <div style={{ marginTop: 8, display: "flex", gap: 8 }}>
        <button onClick={run} disabled={loading} style={{ padding: "8px 12px" }}>
          {loading ? "Running…" : "Run"}
        </button>
      </div>

      {err && <pre style={{ color: "crimson", whiteSpace: "pre-wrap" }}>{err}</pre>}

      {out && (
        <div style={{ marginTop: 12 }}>
          <div
            style={{
              marginTop: 10,
              display: "grid",
              gridTemplateColumns: showDebug ? "1fr 1fr" : "1fr",
              gap: 12,
              alignItems: "start",
            }}
          >
            <div>
              <h4 style={{ margin: 0 }}>Answer</h4>
              <pre style={{ whiteSpace: "pre-wrap", background: "#f6f6f6", padding: 12, borderRadius: 10 }}>
                {out.answer}
              </pre>

              <div style={{ display: "flex", gap: 10, alignItems: "center", justifyContent: "space-between" }}>
                <h4>Meta / timings</h4>
                <button onClick={() => copy(JSON.stringify(out.meta ?? {}, null, 2))} style={{ padding: "6px 10px" }}>
                  Copy
                </button>
              </div>

              <pre style={{ background: "#f6f6f6", padding: 12, overflow: "auto", borderRadius: 10 }}>
                {JSON.stringify(out.meta ?? {}, null, 2)}
              </pre>

              <h4>Memories used (top hits)</h4>
              <pre style={{ background: "#f6f6f6", padding: 12, overflow: "auto", borderRadius: 10 }}>
                {JSON.stringify(out.memories ?? [], null, 2)}
              </pre>
            </div>

            {showDebug && (
              <div>
                <div style={{ display: "flex", gap: 10, alignItems: "center", justifyContent: "space-between", flexWrap: "wrap" }}>
                  <h4 style={{ margin: 0 }}>Debug log</h4>
                  <div style={{ display: "flex", gap: 8 }}>
                    <button onClick={() => copy(String(out?.debug_log ?? ""))} style={{ padding: "6px 10px" }} disabled={!out?.debug_log}>
                      Copy
                    </button>
                  </div>
                </div>

                <pre
                  style={{
                    marginTop: 10,
                    height: 520,
                    overflowY: "auto",
                    border: "1px solid #2a2a2a",
                    borderRadius: 10,
                    padding: 12,
                    background: "#0b0b0b",
                    color: "#e8e8e8",
                    fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
                    fontSize: 12,
                    lineHeight: 1.35,
                    whiteSpace: "pre-wrap",
                  }}
                >
                  {out?.debug_log || "(no debug log returned)"}
                </pre>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
