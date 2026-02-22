import React, { useEffect, useState } from "react";
import { apiGet } from "../api";

type Session = { id: number; created_at: number; message_count: number };
type Msg = { id: number; session_id: number; ts: number; role: string; content: string };

function fmtTs(ts: number) {
  try {
    return new Date(ts * 1000).toLocaleString();
  } catch {
    return String(ts);
  }
}

export default function History() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [sid, setSid] = useState<number | null>(null);
  const [messages, setMessages] = useState<Msg[]>([]);
  const [err, setErr] = useState("");

  async function loadSessions() {
    const r = await apiGet("/api/sessions");
    setSessions(r.sessions || []);
    if (!sid && r.sessions?.[0]?.id) setSid(r.sessions[0].id);
  }

  async function loadMessages(sessionId: number) {
    const r = await apiGet(`/api/sessions/${sessionId}/messages?limit=500`);
    setMessages(r.messages || []);
  }

  useEffect(() => {
    (async () => {
      try {
        setErr("");
        await loadSessions();
      } catch (e: any) {
        setErr(String(e));
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    (async () => {
      if (!sid) return;
      try {
        setErr("");
        await loadMessages(sid);
      } catch (e: any) {
        setErr(String(e));
      }
    })();
  }, [sid]);

  return (
    <div>
      <h3>History</h3>

      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
        <button onClick={loadSessions} style={{ padding: "6px 10px" }}>
          Refresh sessions
        </button>

        <label style={{ display: "flex", gap: 6, alignItems: "center", fontSize: 13 }}>
          session
          <select value={sid ?? ""} onChange={(e) => setSid(Number(e.target.value))}>
            {(sessions || []).map((s) => (
              <option key={s.id} value={s.id}>
                {s.id} ({s.message_count}) — {fmtTs(s.created_at)}
              </option>
            ))}
          </select>
        </label>

        {sid && (
          <button onClick={() => loadMessages(sid)} style={{ padding: "6px 10px" }}>
            Reload messages
          </button>
        )}
      </div>

      {err && <pre style={{ color: "crimson", whiteSpace: "pre-wrap" }}>{err}</pre>}

      <div style={{ marginTop: 12 }}>
        <h4 style={{ marginBottom: 8 }}>Messages</h4>
        <pre
          style={{
            height: 620,
            overflowY: "auto",
            border: "1px solid #ddd",
            borderRadius: 10,
            padding: 12,
            background: "#fafafa",
            whiteSpace: "pre-wrap",
            fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
            fontSize: 12,
            lineHeight: 1.35,
          }}
        >
          {(messages || [])
            .map((m) => `[${fmtTs(m.ts)}] ${m.role}\n${m.content}\n`)
            .join("\n")}
        </pre>
      </div>
    </div>
  );
}
