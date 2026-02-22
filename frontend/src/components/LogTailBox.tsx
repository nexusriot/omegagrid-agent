import React, { useEffect, useMemo, useRef, useState } from "react";
import { apiGet } from "../api";

type Props = {
  runId: string;
  pollMs?: number;
  maxBytes?: number;
  heightPx?: number;
};

export default function LogTailBox({
  runId,
  pollMs = 2000,
  maxBytes = 200_000,
  heightPx = 420,
}: Props) {
  const [text, setText] = useState<string>("");
  const [err, setErr] = useState<string>("");
  const [paused, setPaused] = useState<boolean>(false);
  const [autoScroll, setAutoScroll] = useState<boolean>(true);
  const [loading, setLoading] = useState<boolean>(false);
  const boxRef = useRef<HTMLDivElement | null>(null);

  const url = useMemo(() => {
    const qs = new URLSearchParams({ max_bytes: String(maxBytes) });
    return `/api/bootstrap/logs/${encodeURIComponent(runId)}?${qs.toString()}`;
  }, [runId, maxBytes]);

  async function fetchLogs() {
    if (!runId) return;
    setLoading(true);
    setErr("");
    try {
      const res = await apiGet(url);
      setText(String(res?.text ?? ""));
    } catch (e: any) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!runId) return;
    fetchLogs();
    const t = setInterval(() => {
      if (!paused) fetchLogs();
    }, pollMs);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId, pollMs, paused, url]);

  useEffect(() => {
    if (!autoScroll) return;
    const el = boxRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [text, autoScroll]);

  return (
    <div>
      <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
        <div style={{ fontSize: 12, opacity: 0.75 }}>
          run_id: <b>{runId}</b>
        </div>

        <button onClick={fetchLogs} style={{ padding: "6px 10px" }}>
          {loading ? "Refreshing…" : "Refresh"}
        </button>

        <label style={{ display: "flex", gap: 6, alignItems: "center", fontSize: 13 }}>
          <input
            type="checkbox"
            checked={!paused}
            onChange={(e) => setPaused(!e.target.checked)}
          />
          live
        </label>

        <label style={{ display: "flex", gap: 6, alignItems: "center", fontSize: 13 }}>
          <input
            type="checkbox"
            checked={autoScroll}
            onChange={(e) => setAutoScroll(e.target.checked)}
          />
          auto-scroll
        </label>

        <div style={{ fontSize: 12, opacity: 0.75 }}>
          poll: {pollMs}ms · max_bytes: {maxBytes}
        </div>
      </div>

      {err && (
        <pre style={{ color: "crimson", marginTop: 8, whiteSpace: "pre-wrap" }}>
          {err}
        </pre>
      )}

      <div
        ref={boxRef}
        style={{
          marginTop: 10,
          height: heightPx,
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
        {text || "(no logs yet)"}
      </div>
    </div>
  );
}
