import React from "react";
import { BrowserRouter, Routes, Route, Navigate, Link, useLocation } from "react-router-dom";
import Query from "./pages/Query";
import History from "./pages/History";

function NavLink({ to, label }: { to: string; label: string }) {
  const loc = useLocation();
  const active = loc.pathname === to;
  return (
    <Link
      to={to}
      style={{
        padding: "6px 10px",
        borderRadius: 10,
        textDecoration: "none",
        color: active ? "#000" : "#333",
        background: active ? "#eee" : "transparent",
        border: "1px solid #ddd",
      }}
    >
      {label}
    </Link>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <div style={{ display: "flex", minHeight: "100vh" }}>
        <aside style={{ width: 240, borderRight: "1px solid #ddd", padding: 14, display: "flex", flexDirection: "column", gap: 10 }}>
          <h3 style={{ margin: 0 }}>Agent UI</h3>
          <NavLink to="/query" label="Query" />
          <NavLink to="/history" label="History" />
          <div style={{ marginTop: 12, fontSize: 12, color: "#666" }}>
            SQLite history + Chroma vector memory.
          </div>
        </aside>

        <main style={{ flex: 1, padding: 18 }}>
          <Routes>
            <Route path="/query" element={<Query />} />
            <Route path="/history" element={<History />} />
            <Route path="*" element={<Navigate to="/query" replace />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
