import { AuditEvent } from "@/lib/useSSEStream";

const EVENT_CONFIG: Record<string, { cls: string; badge: string }> = {
  CART_ADD:             { cls: "event-accent",   badge: "badge-accent"   },
  CART_REMOVE:          { cls: "event-danger",   badge: "badge-danger"   },
  APPROVAL_REQUIRED:    { cls: "event-warning",  badge: "badge-warning"  },
  ORDER_CREATED:        { cls: "event-success",  badge: "badge-success"  },
  ORDER_CONFIRMED:      { cls: "event-success",  badge: "badge-success"  },
  PAYMENT_SUCCESS:      { cls: "event-success",  badge: "badge-success"  },
  GUARDRAIL_TRIGGERED:  { cls: "event-danger",   badge: "badge-danger"   },
  AGENT_RESPONSE:       { cls: "event-accent",   badge: "badge-neutral"  },
};

function getConfig(type: string) {
  if (EVENT_CONFIG[type]) return EVENT_CONFIG[type];
  if (type?.startsWith("TOOL_CALL_")) return { cls: "event-accent", badge: "badge-accent" };
  return { cls: "", badge: "badge-neutral" };
}

export default function AuditTimeline({ events }: { events: AuditEvent[] }) {
  if (events.length === 0) {
    return (
      <div style={{ textAlign: "center", padding: "48px 16px", color: "var(--text-muted)" }}>
        <div style={{ width: 32, height: 32, borderRadius: "50%", border: "2px solid var(--border-subtle)", margin: "0 auto 12px", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 14 }}>
          ⋯
        </div>
        <div style={{ fontSize: 13 }}>Waiting for agent activity...</div>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      {events.map((ev) => {
        const cfg = getConfig(ev.event_type);
        const ts = new Date(ev.created_at).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
        return (
          <div key={ev.id} className={`timeline-item ${cfg.cls}`}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
              <span className={`badge ${cfg.badge}`}>{ev.event_type}</span>
              <span className="font-mono" style={{ fontSize: 10, color: "var(--text-muted)", flexShrink: 0 }}>{ts}</span>
            </div>
            {ev.reasoning && (
              <p style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.5, marginTop: 4 }}>
                {ev.reasoning.length > 200 ? ev.reasoning.substring(0, 200) + "..." : ev.reasoning}
              </p>
            )}
            <div style={{ display: "flex", gap: 12, marginTop: 2 }}>
              <span style={{ fontSize: 10, color: "var(--text-muted)", fontFamily: "'JetBrains Mono', monospace" }}>
                actor:{ev.actor}
              </span>
              {ev.outcome && (
                <span style={{ fontSize: 10, color: "var(--text-muted)", fontFamily: "'JetBrains Mono', monospace" }}>
                  outcome:{ev.outcome}
                </span>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
