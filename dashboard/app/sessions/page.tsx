"use client";
import Link from "next/link";
import { useEffect, useState } from "react";

function StatusBadge({ lastEvent }: { lastEvent: string }) {
  if (lastEvent === "ORDER_CONFIRMED" || lastEvent === "PAYMENT_SUCCESS")
    return <span className="badge badge-success">PAID</span>;
  if (lastEvent === "GUARDRAIL_TRIGGERED")
    return <span className="badge badge-danger">BLOCKED</span>;
  if (lastEvent === "APPROVAL_REQUIRED")
    return <span className="badge badge-warning">PENDING</span>;
  return <span className="badge badge-neutral">{lastEvent || "ACTIVE"}</span>;
}

export default function SessionsPage() {
  const [sessions, setSessions] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`/api/proxy/sessions`)
      .then((r) => r.json())
      .then((d) => setSessions(d.sessions || []))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div style={{ padding: "32px 32px", maxWidth: "100%" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 28 }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 600, letterSpacing: "-0.02em", color: "var(--text-primary)", marginBottom: 4 }}>Session History</h1>
          <p style={{ fontSize: 13, color: "var(--text-muted)" }}>All past agent sessions, sorted by most recent activity</p>
        </div>
        <Link href="/" className="btn btn-primary" style={{ fontSize: 13 }}>New Session →</Link>
      </div>

      {loading ? (
        <div style={{ textAlign: "center", padding: "80px 0", color: "var(--text-muted)", fontSize: 13 }}>Loading sessions...</div>
      ) : sessions.length === 0 ? (
        <div style={{ textAlign: "center", padding: "80px 0" }}>
          <div style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 16 }}>No sessions found. Start your first agent session!</div>
          <Link href="/" className="btn btn-primary">Start Agent</Link>
        </div>
      ) : (
        <div className="card" style={{ padding: 0, overflow: "hidden" }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Session ID</th>
                <th>Goal</th>
                <th>Status</th>
                <th>Events</th>
                <th>Started</th>
                <th>Last Activity</th>
              </tr>
            </thead>
            <tbody>
              {sessions.map((s) => (
                <tr key={s.session_id} onClick={() => (window.location.href = `/session/${s.session_id}`)}>
                  <td>
                    <Link href={`/session/${s.session_id}`} style={{ textDecoration: "none" }}>
                      <code className="font-mono" style={{ fontSize: 12, color: "var(--accent)" }}>
                        {s.session_id.substring(0, 8)}...
                      </code>
                    </Link>
                  </td>
                  <td style={{ maxWidth: 280, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", color: "var(--text-secondary)" }}>
                    {s.goal || <span style={{ color: "var(--text-muted)" }}>-</span>}
                  </td>
                  <td><StatusBadge lastEvent={s.last_event} /></td>
                  <td>
                    <span className="font-mono" style={{ fontSize: 12, color: "var(--text-muted)" }}>{s.event_count}</span>
                  </td>
                  <td>
                    <span className="font-mono" style={{ fontSize: 11, color: "var(--text-muted)" }}>
                      {new Date(s.started_at).toLocaleString("en-IN", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
                    </span>
                  </td>
                  <td>
                    <span className="font-mono" style={{ fontSize: 11, color: "var(--text-muted)" }}>
                      {new Date(s.last_activity).toLocaleString("en-IN", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
