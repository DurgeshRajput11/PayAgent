"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import VoiceInput from "@/components/VoiceInput";

const EXAMPLES = [
  "Buy Puma RS-X shoes under ₹2500",
  "Find boAt wireless earbuds under ₹1500",
  "I need a Wildcraft laptop bag",
  "Get me the Designing Data-Intensive Applications book",
  "Buy a Fire-Boltt smartwatch under ₹2000",
];

const STEPS = [
  { num: "01", title: "Search Catalog", desc: "Agent autonomously queries product catalog based on your goal." },
  { num: "02", title: "Build Cart", desc: "AI selects the best matching items within your budget and reasoning is logged." },
  { num: "03", title: "Human Approval", desc: "You review the cart and approve or reject the Razorpay checkout." },
];

export default function Home() {
  const router = useRouter();
  const [goal, setGoal] = useState("");
  const [budget, setBudget] = useState("5000");
  const [loading, setLoading] = useState(false);

  const handleStart = async () => {
    if (!goal.trim() || loading) return;
    setLoading(true);
    try {
      const parsedBudget = Number(budget) || 5000;
      // Proxied through our own server (app/api/proxy/agent/run) so the
      // shared internal key never has to live in client-side code.
      const res = await fetch(`/api/proxy/agent/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ goal, budget: parsedBudget }),
      });
      const data = await res.json();
      localStorage.setItem(`agent_response_${data.session_id}`, JSON.stringify({
        messages: data.messages,
        status: data.status,
        goal,
        budget: parsedBudget,
        token_usage: data.token_usage,
      }));
      router.push(`/session/${data.session_id}`);
    } catch {
      setLoading(false);
    }
  };

  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", minHeight: "calc(100vh - 56px)", maxWidth: "100%" }}>
      {/* Left: Command Input */}
      <div style={{
        padding: "48px 48px 48px 48px",
        display: "flex", flexDirection: "column", justifyContent: "center",
        borderRight: "1px solid var(--border-subtle)",
      }}>
        <div style={{ maxWidth: 520 }}>
          <div style={{ marginBottom: 8 }}>
            <span className="badge badge-accent">Powered by Razorpay MCP + LangGraph</span>
          </div>
          <h1 style={{ fontSize: 32, fontWeight: 700, letterSpacing: "-0.03em", lineHeight: 1.2, marginBottom: 8, color: "var(--text-primary)" }}>
            Autonomous AI<br />Shopping Agent
          </h1>
          <p style={{ fontSize: 14, color: "var(--text-secondary)", marginBottom: 32, lineHeight: 1.6 }}>
            Describe your shopping goal. The AI agent will search, pick items, and request your approval before charging.
          </p>

          <div className="card" style={{ marginBottom: 16 }}>
            <label style={{ fontSize: 11, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--text-muted)", display: "block", marginBottom: 8 }}>
              Shopping Goal
            </label>
            <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
              <textarea
                className="input"
                value={goal}
                onChange={(e) => setGoal(e.target.value)}
                placeholder="e.g. Buy running shoes under ₹2500"
                rows={3}
                onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleStart(); } }}
              />
              <div style={{ display: "flex", flexDirection: "column", gap: 8, width: 140 }}>
                <div style={{ position: "relative" }}>
                  <span style={{ position: "absolute", left: 12, top: 12, color: "var(--text-muted)", fontSize: 14 }}>₹</span>
                  <input
                    type="number"
                    className="input"
                    value={budget}
                    onChange={(e) => setBudget(e.target.value)}
                    placeholder="Budget"
                    style={{ paddingLeft: 28, height: "40px" }}
                    onKeyDown={(e) => { if (e.key === "Enter") handleStart(); }}
                  />
                </div>
                <VoiceInput onTranscript={(text) => setGoal(text)} />
              </div>
            </div>

            <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 16 }}>
              {EXAMPLES.map((ex) => (
                <button
                  key={ex}
                  onClick={() => setGoal(ex)}
                  style={{
                    fontSize: 11, padding: "4px 10px",
                    borderRadius: 4, border: "1px solid var(--border-subtle)",
                    background: "transparent", color: "var(--text-muted)",
                    cursor: "pointer", transition: "all 0.15s", fontFamily: "inherit",
                  }}
                  onMouseOver={(e) => { e.currentTarget.style.borderColor = "var(--accent)"; e.currentTarget.style.color = "var(--accent)"; }}
                  onMouseOut={(e) => { e.currentTarget.style.borderColor = "var(--border-subtle)"; e.currentTarget.style.color = "var(--text-muted)"; }}
                >
                  {ex}
                </button>
              ))}
            </div>

            <button
              className="btn btn-primary"
              onClick={handleStart}
              disabled={loading || !goal.trim()}
              style={{ width: "100%", padding: "10px 0", fontSize: 14, justifyContent: "center" }}
            >
              {loading ? (
                <>
                  <span style={{ display: "inline-block", width: 14, height: 14, border: "2px solid rgba(255,255,255,0.3)", borderTopColor: "#fff", borderRadius: "50%", animation: "spin 0.7s linear infinite" }} />
                  Dispatching Agent...
                </>
              ) : "Run Agent →"}
            </button>
          </div>

          <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        </div>
      </div>

      {/* Right: How It Works */}
      <div style={{
        padding: "48px",
        display: "flex", flexDirection: "column", justifyContent: "center",
        background: "var(--bg-surface)",
      }}>
        <div style={{ maxWidth: 480, margin: "0 auto" }}>
          <div style={{ fontSize: 11, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--text-muted)", marginBottom: 24 }}>
            How It Works
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
            {STEPS.map((step, i) => (
              <div key={step.num} style={{ display: "flex", gap: 16, paddingBottom: i < STEPS.length - 1 ? 28 : 0, position: "relative" }}>
                {i < STEPS.length - 1 && (
                  <div style={{ position: "absolute", left: 15, top: 32, width: 1, height: "calc(100% - 8px)", background: "var(--border-subtle)" }} />
                )}
                <div style={{
                  width: 32, height: 32, borderRadius: 6, flexShrink: 0,
                  background: "var(--accent-bg)", border: "1px solid rgba(37, 99, 235, 0.3)",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontSize: 11, fontWeight: 700, color: "var(--accent)",
                  fontFamily: "'JetBrains Mono', monospace", zIndex: 1,
                }}>
                  {step.num}
                </div>
                <div>
                  <div style={{ fontWeight: 600, fontSize: 14, color: "var(--text-primary)", marginBottom: 4 }}>{step.title}</div>
                  <div style={{ fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.6 }}>{step.desc}</div>
                </div>
              </div>
            ))}
          </div>

          <div style={{ marginTop: 40, padding: 16, background: "var(--bg-surface-elevated)", borderRadius: 6, border: "1px solid var(--border-subtle)" }}>
            <div style={{ fontSize: 11, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--text-muted)", marginBottom: 12 }}>
              Safety Guarantees
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {[
                { label: "Spending Guardrail", desc: "Auto-rejects orders exceeding your specified budget" },
                { label: "Human Approval Gate", desc: "No charge without explicit user approval" },
                { label: "Full Audit Trail", desc: "Every agent action logged in real-time" },
              ].map((item) => (
                <div key={item.label} style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
                  <div style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--success)", marginTop: 5, flexShrink: 0 }} />
                  <div>
                    <span style={{ fontWeight: 600, fontSize: 13, color: "var(--text-primary)" }}>{item.label}</span>
                    <span style={{ fontSize: 13, color: "var(--text-muted)", marginLeft: 8 }}>{item.desc}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
