export default function ApprovalDialog({
  cart, onDecide, orderId, onPay, loading, paymentLoading, amount,
}: {
  cart: any;
  onDecide?: (d: "approved" | "rejected") => void;
  orderId?: string;
  onPay?: () => void;
  loading?: boolean;
  paymentLoading?: boolean;
  amount?: number;
}) {
  const total = amount && amount > 0 ? amount : cart?.total_inr;

  if (orderId) {
    return (
      <div className="card" style={{ border: "1px solid rgba(37, 99, 235, 0.4)", background: "var(--bg-surface-elevated)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
          <div style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--accent)", boxShadow: "0 0 6px var(--accent)" }} />
          <span style={{ fontSize: 12, fontWeight: 600, color: "var(--accent)", textTransform: "uppercase", letterSpacing: "0.06em" }}>Payment Ready</span>
        </div>
        <p style={{ fontSize: 13, color: "var(--text-secondary)", marginBottom: 4 }}>
          Razorpay order created. Confirm payment of
        </p>
        <p className="font-mono" style={{ fontSize: 20, fontWeight: 700, color: "var(--text-primary)", marginBottom: 16 }}>
          ₹{total?.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
        </p>
        <div style={{ fontSize: 11, color: "var(--text-muted)", marginBottom: 14, fontFamily: "'JetBrains Mono', monospace" }}>
          Order ID: {orderId}
        </div>
        <button 
          className="btn btn-primary" 
          onClick={onPay} 
          disabled={paymentLoading}
          style={{ width: "100%", justifyContent: "center", padding: "10px 0", opacity: paymentLoading ? 0.7 : 1 }}
        >
          {paymentLoading ? "Confirming Payment..." : "Complete Payment with Razorpay"}
        </button>
      </div>
    );
  }

  return (
    <div className="card" style={{ border: "1px solid rgba(245, 158, 11, 0.4)", background: "var(--bg-surface-elevated)" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--warning)" strokeWidth="2.5">
          <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
          <line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
        </svg>
        <span style={{ fontSize: 12, fontWeight: 600, color: "var(--warning)", textTransform: "uppercase", letterSpacing: "0.06em" }}>Action Required</span>
      </div>
      <p style={{ fontSize: 13, color: "var(--text-secondary)", marginBottom: 4 }}>
        Agent is requesting to create a payment order for
      </p>
      <p className="font-mono" style={{ fontSize: 20, fontWeight: 700, color: "var(--text-primary)", marginBottom: 16 }}>
        ₹{total?.toLocaleString("en-IN", { minimumFractionDigits: 2 }) ?? "—"}
      </p>
      {/* 
        Human-in-the-Loop Breakpoint:
        This prevents the autonomous agent from blindly spending money. The LangGraph state machine
        is fully suspended until the user explicitly clicks Approve, after which we POST to /resume.
      */}
      <p style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 16, lineHeight: 1.6 }}>
        This will initiate a Razorpay payment flow. The agent cannot proceed without your explicit approval.
      </p>
      <div style={{ display: "flex", gap: 8 }}>
        <button
          className="btn btn-success"
          onClick={() => onDecide?.("approved")}
          disabled={loading}
          style={{ flex: 1, justifyContent: "center", opacity: loading ? 0.7 : 1 }}
        >
          {loading ? "Processing…" : "Approve"}
        </button>
        <button
          className="btn btn-danger"
          onClick={() => onDecide?.("rejected")}
          disabled={loading}
          style={{ flex: 1, justifyContent: "center", opacity: loading ? 0.7 : 1 }}
        >
          Reject
        </button>
      </div>
    </div>
  );
}
