"use client";

import React from "react";

interface AgentResponseProps {
  goal: string;
  messages: string[];
}

export default function AgentResponse({ goal, messages }: AgentResponseProps) {
  if (!messages || messages.length === 0) return null;

  return (
    <div style={{ marginBottom: 24, display: "flex", flexDirection: "column", gap: 16 }}>
      {/* User Goal */}
      {goal && (
        <div style={{ display: "flex", gap: 12, alignItems: "flex-start" }}>
          <div style={{ fontSize: 20 }}>👤</div>
          <div style={{
            background: "var(--surface)", border: "1px solid var(--border)",
            borderRadius: "var(--radius)", padding: "12px 16px",
            fontSize: 14, color: "var(--text)", flex: 1
          }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: "var(--text-muted)", marginBottom: 4 }}>You</div>
            {goal}
          </div>
        </div>
      )}

      {/* Agent Messages */}
      {messages.map((msg, idx) => (
        <div key={idx} style={{ display: "flex", gap: 12, alignItems: "flex-start" }}>
          <div style={{ fontSize: 20 }}>🤖</div>
          <div style={{
            background: "var(--surface)", border: "1px solid var(--border)",
            borderLeft: "4px solid var(--accent)",
            borderRadius: "var(--radius)", padding: "12px 16px",
            fontSize: 14, color: "var(--text)", flex: 1,
            lineHeight: 1.5,
          }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: "var(--accent)", marginBottom: 4 }}>PayAgent</div>
            {msg}
          </div>
        </div>
      ))}
    </div>
  );
}
