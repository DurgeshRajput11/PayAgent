export default function CartSummary({ cart, budgetCap = 5000, onRemove }: { cart: any; budgetCap?: number; onRemove?: (id: string) => void }) {
  const total = cart?.total_inr || 0;
  console.log("CartSummary cart:", cart);
  const pct = Math.min((total / budgetCap) * 100, 100);
  const isOver = total > budgetCap;
  const isWarn = !isOver && pct > 70;

  return (
    <div className="card" style={{ padding: 0, overflow: "hidden" }}>
      <div style={{ padding: "10px 14px", borderBottom: "1px solid var(--border-subtle)" }}>
        <div className="card-header" style={{ marginBottom: 0 }}>Shopping Cart</div>
      </div>

      {/* Items */}
      <div style={{ display: "flex", flexDirection: "column" }}>
        {(!cart || !cart.items || cart.items.length === 0) ? (
          <div style={{ textAlign: "center", padding: "24px 0", color: "var(--text-muted)", fontSize: 13 }}>
            Cart is empty
          </div>
        ) : (
          cart.items.map((item: any) => (
            <div key={item.product_id} style={{
              display: "flex", alignItems: "center", gap: 10, padding: "10px 14px",
              borderBottom: "1px solid var(--border-subtle)",
            }}>
              {item.image_url ? (
                <img src={item.image_url} alt={item.name} style={{ width: 36, height: 36, borderRadius: 4, objectFit: "cover", flexShrink: 0, border: "1px solid var(--border-subtle)" }} />
              ) : (
                <div style={{ width: 36, height: 36, borderRadius: 4, background: "var(--bg-subtle)", flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 16 }}>📦</div>
              )}
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 13, fontWeight: 500, color: "var(--text-primary)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{item.name}</div>
                <div style={{ fontSize: 11, color: "var(--text-muted)" }}>qty {item.quantity}</div>
              </div>
              <div className="font-mono" style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)", flexShrink: 0 }}>
                ₹{(item.price_inr * item.quantity).toLocaleString("en-IN")}
              </div>
              {/* 
                Out-of-band state mutation:
                Clicking this manually alters the cart state. Since our agent dynamically 
                injects the live Redis state on every turn, it never hallucinates this change.
              */}
              {onRemove && (
                <button 
                  onClick={() => onRemove(item.product_id)}
                  style={{ background: "transparent", border: "none", color: "var(--danger)", cursor: "pointer", fontSize: 20, marginLeft: 4, fontWeight: "bold" }}
                  title="Decrease quantity by 1"
                >
                  -
                </button>
              )}
            </div>
          ))
        )}
      </div>

      {/* 
        Spending Guardrail Visual Feedback:
        Reactively displays the budget consumption, warning the user if the agent 
        is approaching or exceeding the strict spending limit.
      */}
      <div style={{ padding: "10px 14px", borderBottom: "1px solid var(--border-subtle)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
          <span style={{ fontSize: 11, color: "var(--text-muted)" }}>Budget used</span>
          <span className="font-mono" style={{ fontSize: 11, color: isOver ? "var(--danger)" : isWarn ? "var(--warning)" : "var(--text-muted)" }}>
            {pct.toFixed(0)}%
          </span>
        </div>
        <div className="budget-bar">
          <div className={`budget-bar-fill ${isOver ? "over" : isWarn ? "warn" : ""}`} style={{ width: `${pct}%` }} />
        </div>
      </div>

      {/* Total */}
      <div style={{ padding: "10px 14px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span style={{ fontSize: 13, fontWeight: 600, color: "var(--text-secondary)" }}>Total</span>
        <span className="font-mono" style={{ fontSize: 16, fontWeight: 700, color: isOver ? "var(--danger)" : "var(--text-primary)" }}>
          ₹{total.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
        </span>
      </div>
    </div>
  );
}
