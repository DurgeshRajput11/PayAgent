"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";

export default function AnalyticsPage() {
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`/api/proxy/analytics`)
      .then((r) => r.json())
      .then(setStats)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const METRICS = stats
    ? [
        { label: "Total Sessions", value: stats.total_sessions ?? 0, color: "var(--accent)" },
        { label: "Orders Confirmed", value: stats.total_orders ?? 0, color: "var(--success)" },
        { label: "Guardrails Triggered", value: stats.guardrails_triggered ?? 0, color: "var(--danger)" },
      ]
    : [];

  return (
    <div style={{ padding: "32px 32px", maxWidth: "100%" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 28 }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 600, letterSpacing: "-0.02em", color: "var(--text-primary)", marginBottom: 4 }}>Analytics</h1>
          <p style={{ fontSize: 13, color: "var(--text-muted)" }}>Aggregated session and transaction metrics</p>
        </div>
        <Link href="/" className="btn btn-primary" style={{ fontSize: 13 }}>New Session →</Link>
      </div>

      {loading ? (
        <div style={{ textAlign: "center", padding: "80px 0", color: "var(--text-muted)", fontSize: 13 }}>Loading analytics...</div>
      ) : !stats ? (
        <div style={{ textAlign: "center", padding: "80px 0", color: "var(--text-muted)", fontSize: 13 }}>No data available. Run some agent sessions first.</div>
      ) : (
        <>
          {/* Metric Cards */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16, marginBottom: 24 }}>
            {METRICS.map((m) => (
              <div key={m.label} className="card">
                <div className="card-header">{m.label}</div>
                <div className="font-mono" style={{ fontSize: 32, fontWeight: 700, color: m.color, letterSpacing: "-0.02em" }}>
                  {m.value}
                </div>
              </div>
            ))}
          </div>

          {/* Chart */}
          <div className="card">
            <div className="card-header">Activity - Last 7 Days</div>
            <div style={{ height: 280 }}>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={stats.timeline || []} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" vertical={false} />
                  <XAxis dataKey="date" stroke="var(--text-muted)" fontSize={11} tickLine={false} axisLine={false} fontFamily="'JetBrains Mono', monospace" />
                  <YAxis stroke="var(--text-muted)" fontSize={11} tickLine={false} axisLine={false} />
                  <Tooltip
                    contentStyle={{ background: "var(--bg-surface-elevated)", border: "1px solid var(--border-subtle)", borderRadius: 6, color: "var(--text-primary)", fontSize: 12 }}
                    itemStyle={{ color: "var(--accent)" }}
                    cursor={{ stroke: "var(--border-subtle)", strokeDasharray: "4" }}
                  />
                  <Line type="monotone" dataKey="events" name="Events" stroke="var(--accent)" strokeWidth={2} dot={{ r: 3, fill: "var(--accent)", strokeWidth: 0 }} activeDot={{ r: 5 }} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
