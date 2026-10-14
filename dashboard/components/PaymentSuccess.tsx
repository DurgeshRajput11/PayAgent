export default function PaymentSuccess({ orderId, amount }: { orderId: string; amount: number }) {
  return (
    <div className="card" style={{ border: "1px solid rgba(16, 185, 129, 0.4)", background: "var(--bg-surface-elevated)", animation: "fadeIn 0.5s ease" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
        <div style={{ width: 20, height: 20, borderRadius: "50%", background: "var(--success-bg)", border: "1px solid var(--success)", display: "flex", alignItems: "center", justifyContent: "center" }}>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="var(--success)" strokeWidth="3">
            <polyline points="20 6 9 17 4 12"/>
          </svg>
        </div>
        <span style={{ fontSize: 12, fontWeight: 600, color: "var(--success)", textTransform: "uppercase", letterSpacing: "0.06em" }}>Payment Successful</span>
      </div>
      <div style={{ marginBottom: 12 }}>
        <div style={{ fontSize: 11, color: "var(--text-muted)", marginBottom: 4 }}>Amount Paid</div>
        <div className="font-mono" style={{ fontSize: 22, fontWeight: 700, color: "var(--success)" }}>
          ₹{amount.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
        </div>
      </div>
      <div>
        <div style={{ fontSize: 11, color: "var(--text-muted)", marginBottom: 2 }}>Razorpay Order ID</div>
        <code className="font-mono" style={{ fontSize: 11, color: "var(--text-secondary)", background: "var(--bg-subtle)", padding: "3px 8px", borderRadius: 4, border: "1px solid var(--border-subtle)", display: "block", wordBreak: "break-all" }}>
          {orderId}
        </code>
      </div>
      <div style={{ marginTop: 10, fontSize: 11, color: "var(--text-muted)" }}>
        {new Date().toLocaleString("en-IN")}
      </div>
    </div>
  );
}
