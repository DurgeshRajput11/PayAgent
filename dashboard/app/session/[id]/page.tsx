"use client";
import { use, useState, useEffect, useRef } from "react";
import AuditTimeline from "@/components/AuditTimeline";
import CartSummary from "@/components/CartSummary";
import ApprovalDialog from "@/components/ApprovalDialog";
import PaymentSuccess from "@/components/PaymentSuccess";
import { useSSEStream } from "@/lib/useSSEStream";
import VoiceInput from "@/components/VoiceInput";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Panel, Group as PanelGroup, Separator as PanelResizeHandle } from "react-resizable-panels";
import { openRazorpayCheckout } from "@/lib/razorpay";

function copyToClipboard(text: string) {
  navigator.clipboard.writeText(text).catch(() => {});
}

export default function SessionPage({ params }: { params: { id: string } }) {
  const { id } = params;
  const { events, isConnected } = useSSEStream(id);
  const [cart, setCart] = useState<any>(null);
  const [agentData, setAgentData] = useState<{ goal: string; budget?: number; messages: string[]; status?: string; token_usage?: any }>({ goal: "", messages: [] });
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const [approvalLoading, setApprovalLoading] = useState(false);
  const [paymentLoading, setPaymentLoading] = useState(false);
  const [approvalError, setApprovalError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const terminalRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const saved = localStorage.getItem(`agent_response_${id}`);
    if (saved) {
      try { setAgentData(JSON.parse(saved)); } catch {}
    } else {
      fetch(`/api/proxy/agent/${id}/state`)
        .then(res => res.json())
        .then(data => {
            if (data.messages) {
                const nextData = { goal: data.goal, budget: data.budget, messages: data.messages, status: data.status, token_usage: data.token_usage };
                setAgentData(nextData);
                localStorage.setItem(`agent_response_${id}`, JSON.stringify(nextData));
            }
        })
        .catch(console.error);
    }
  }, [id]);

  // Reactively fetch cart state whenever an SSE event indicates a state mutation
  useEffect(() => {
    const latest = events[events.length - 1];
    if (latest?.event_type === "CART_ADD" || latest?.event_type === "CART_REMOVE" || latest?.event_type?.includes("CART") || latest?.event_type === "PAYMENT_SUCCESS" || latest?.event_type === "ORDER_CONFIRMED") {
      fetchCart();
    }
  }, [events]);

  useEffect(() => {
    if (terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
    }
  }, [agentData.messages, events]);

  const fetchCart = async () => {
  try {
    // Proxied through app/api/proxy/merchant/*
    const res = await fetch(`/api/proxy/merchant/cart/${id}`);
    setCart(await res.json());
  } catch {}
};

useEffect(() => {
  fetchCart();
}, [id]);

  const handleRemoveCartItem = async (productId: string) => {
    try {
      await fetch(`/api/proxy/merchant/cart/${id}/remove/${productId}?qty=1`, {
        method: "DELETE",
      });
      fetchCart();
    } catch {}
  };

  const handleDecision = async (decision: "approved" | "rejected") => {
  setApprovalLoading(true);
  setApprovalError(null);

  try {
    const res = await fetch(`/api/proxy/resume/${id}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ decision }),
    });

    const data = await res.json().catch(() => ({}));

    if (!res.ok) {
      throw new Error(data?.detail || data?.error || `Server error ${res.status}`);
    }

    const stateRes = await fetch(`/api/proxy/agent/${id}/state`, {
      cache: "no-store",
    });

    if (stateRes.ok) {
      const state = await stateRes.json();

      const next = {
        goal: state.goal ?? agentData.goal,
        budget: state.budget ?? agentData.budget,
        messages: state.messages ?? data.messages ?? agentData.messages,
        status: state.status ?? data.status ?? "completed",
        token_usage: state.token_usage ?? data.token_usage ?? agentData.token_usage,
      };

      setAgentData(next);
      localStorage.setItem(`agent_response_${id}`, JSON.stringify(next));
    }

    await fetchCart();
  } catch (err: any) {
    setApprovalError(err?.message ?? "Failed to send decision. Please try again.");
  } finally {
    setApprovalLoading(false);
  }
};

  // Opens the real Razorpay Checkout widget and, only once Razorpay itself
  // reports success, submits the payment id/order id/signature to the Go
  // server, which verifies the signature before marking anything paid (see
  // merchant-server/internal/services/payment.go). Previously this just
  // waited one second and called confirm directly with no proof of payment.
  const handlePayment = async (internalOrderId: string, razorpayOrderId: string, amountInr: number) => {
    setPaymentLoading(true);
    setApprovalError(null);
    try {
      const result = await openRazorpayCheckout({
        razorpayOrderId,
        amountPaise: Math.round(amountInr * 100),
        description: `PayAgent order ${internalOrderId}`,
      });

      const res = await fetch(`/api/proxy/merchant/orders/${internalOrderId}/confirm`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          razorpay_payment_id: result.razorpay_payment_id,
          razorpay_order_id: result.razorpay_order_id,
          razorpay_signature: result.razorpay_signature,
        }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body?.error || `Payment confirmation failed (${res.status})`);
      }
      fetchCart();
    } catch (err: any) {
      setApprovalError(err?.message ?? "Payment failed or was cancelled.");
    } finally {
      setPaymentLoading(false);
    }
  };

  const handleChat = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!chatInput.trim() || chatLoading) return;
    const message = chatInput.trim();
    setChatInput("");
    setChatLoading(true);
    setAgentData((prev) => ({ ...prev, messages: [...prev.messages, `USER: ${message}`] }));
    try {
      const res = await fetch(`/api/proxy/agent/${id}/message`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message }),
      });
      
      // Graceful degradation: catch fatal rate limits and bubble them into the chat UI
      if (!res.ok) {
        const errObj = await res.json().catch(() => ({}));
        throw new Error(errObj.detail || "Failed to send message to AI Agent.");
      }
      const data = await res.json();
      const next = { goal: agentData.goal, budget: agentData.budget, messages: data.messages, status: data.status, token_usage: data.token_usage };
      setAgentData(next);
      localStorage.setItem(`agent_response_${id}`, JSON.stringify(next));
    } catch (error: any) {
      console.error(error);
      setAgentData((prev) => ({ ...prev, messages: [...prev.messages, `ERROR: ${error.message}`] }));
    } finally {
      setChatLoading(false);
    }
  };

  const isOrderConfirmed = events.some((e) => e.event_type === "ORDER_CONFIRMED" || e.event_type === "PAYMENT_SUCCESS");
  const createdOrder = [...events]
    .reverse()
    .find((e) => e.event_type === "ORDER_CREATED");
  
  const showApproval =
    (agentData?.status === "awaiting_approval" ||
     events.some((e) => e.event_type === "APPROVAL_REQUIRED")) &&
    !isOrderConfirmed &&
    agentData?.status !== "resumed" &&
    (cart?.total_inr ?? 0) > 0;

  console.log("[APPROVAL DEBUG]", {
    cartTotal: cart?.total_inr,
    status: agentData?.status,
    createdOrder: createdOrder?.payload,
    showApproval,
  });


  const cartTotal = cart?.total_inr || 0;
  const budgetCap = agentData?.budget || 5000;
  const budgetPct = Math.min((cartTotal / budgetCap) * 100, 100);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "calc(100vh - 56px)" }}>
      {/* Top Bar */}
      <div style={{
        display: "flex", alignItems: "center", gap: 16, padding: "10px 24px",
        background: "var(--bg-surface)", borderBottom: "1px solid var(--border-subtle)",
        flexShrink: 0,
      }}>
        {/* Session ID */}
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontSize: 11, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.06em" }}>Session</span>
          <code
            className="font-mono"
            onClick={() => { copyToClipboard(id); setCopied(true); setTimeout(() => setCopied(false), 1500); }}
            style={{
              fontSize: 12, color: "var(--text-secondary)", background: "var(--bg-subtle)",
              padding: "2px 8px", borderRadius: 4, cursor: "pointer", border: "1px solid var(--border-subtle)",
              transition: "color 0.15s",
            }}
            title="Click to copy"
          >
            {copied ? "Copied!" : `${id.substring(0, 8)}...${id.slice(-4)}`}
          </code>
        </div>

        <div style={{ width: 1, height: 16, background: "var(--border-subtle)" }} />

        {/* Goal */}
        {agentData.goal && (
          <div style={{ fontSize: 13, color: "var(--text-secondary)", flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            Goal: <span style={{ color: "var(--text-primary)", fontWeight: 500 }}>{agentData.goal}</span>
          </div>
        )}

        {/* Budget Tracker */}
        {cartTotal > 0 && (
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
            <span style={{ fontSize: 11, color: "var(--text-muted)" }}>Budget</span>
            <div style={{ width: 100 }}>
              <div className="budget-bar">
                <div className={`budget-bar-fill ${budgetPct > 90 ? "over" : budgetPct > 70 ? "warn" : ""}`} style={{ width: `${budgetPct}%` }} />
              </div>
            </div>
            <span className="font-mono" style={{ fontSize: 12, color: budgetPct > 90 ? "var(--danger)" : "var(--text-secondary)" }}>
              ₹{cartTotal.toFixed(0)}<span style={{ color: "var(--text-muted)" }}>/₹{budgetCap}</span>
            </span>
          </div>
        )}

        {/* Token Usage */}
        {agentData.token_usage && (
          <>
            <div style={{ width: 1, height: 16, background: "var(--border-subtle)" }} />
            <div className="font-mono" style={{ fontSize: 11, color: "var(--text-muted)", flexShrink: 0 }}>
              {agentData.token_usage.total_tokens} tokens · ${agentData.token_usage.estimated_cost_usd}
            </div>
          </>
        )}

        {/* SSE Status */}
        <div style={{ display: "flex", alignItems: "center", gap: 6, flexShrink: 0 }}>
          <div className={`status-dot ${isConnected ? "connected" : "disconnected"}`} />
          <span style={{ fontSize: 11, color: "var(--text-muted)" }}>{isConnected ? "Live" : "Offline"}</span>
        </div>
      </div>

      {/* 3-Column Cockpit */}
      <PanelGroup orientation="horizontal" style={{ flex: 1, overflow: "hidden" }}>

        {/* Left: Agent Thought Terminal */}
        <Panel defaultSize={28} minSize={20}>
          <div style={{
            display: "flex", flexDirection: "column", height: "100%", overflow: "hidden",
            background: "var(--bg-canvas)",
          }}>
          <div style={{
            padding: "10px 14px", borderBottom: "1px solid var(--border-subtle)",
            background: "var(--bg-surface)", flexShrink: 0,
          }}>
            <span className="card-header" style={{ marginBottom: 0 }}>Agent Terminal</span>
          </div>

          <div className="terminal-panel" style={{ flex: 1, overflowY: "auto" }} ref={terminalRef}>
            {agentData.goal && (
              <div className="terminal-line user">&gt; {agentData.goal}</div>
            )}
            {agentData.messages.map((msg, i) => {
              const isUser = msg.startsWith("USER:");
              const isTool = msg.includes("[TOOL") || msg.includes("tool_call") || events.some(e => e.event_type?.startsWith("TOOL_CALL") && e.reasoning === msg);
              
              if (isUser) {
                return (
                  <div key={i} style={{ padding: "8px 0", borderBottom: "1px solid var(--border-subtle)" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                      <div style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--text-secondary)" }} />
                      <span style={{ fontSize: 11, fontWeight: 600, color: "var(--text-muted)", textTransform: "uppercase" }}>You</span>
                    </div>
                    <div style={{ paddingLeft: 14, color: "var(--text-primary)" }}>
                      {msg.replace("USER:", "").trim()}
                    </div>
                  </div>
                );
              }

              if (isTool) {
                return (
                  <div key={i} className="terminal-line tool" style={{ paddingLeft: 14, opacity: 0.8 }}>
                    {msg}
                  </div>
                );
              }

              return (
                <div key={i} style={{ padding: "12px 0", borderBottom: "1px solid var(--border-subtle)" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                    <div style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--accent)" }} />
                    <span style={{ fontSize: 11, fontWeight: 600, color: "var(--accent)", textTransform: "uppercase" }}>PayAgent</span>
                  </div>
                  <div style={{ paddingLeft: 14 }}>
                    <div className="markdown-body">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {msg}
                      </ReactMarkdown>
                    </div>
                  </div>
                </div>
              );
            })}
            {/* SSE Tool Events in Terminal */}
            {events.filter(e => e.event_type?.startsWith("TOOL_CALL_")).map(e => (
              <div key={e.id} className="terminal-line tool">
                [{e.event_type?.replace("TOOL_CALL_", "")}] {e.reasoning?.substring(0, 120)}
              </div>
            ))}
            {chatLoading && <div className="terminal-line" style={{ color: "var(--text-muted)" }}>Processing<span className="cursor-blink">_</span></div>}
          </div>

          {/* Chat Input */}
          {agentData.status !== "awaiting_approval" && (
            <form onSubmit={handleChat} style={{
              padding: "10px 12px", borderTop: "1px solid var(--border-subtle)",
              background: "var(--bg-surface)", display: "flex", gap: 8, flexShrink: 0,
            }}>
              <input
                className="input font-mono"
                style={{ fontSize: 12, padding: "7px 10px", flex: 1 }}
                placeholder="Send follow-up message..."
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                disabled={chatLoading}
              />
              <VoiceInput onTranscript={(text) => setChatInput(text)} />
              <button type="submit" className="btn btn-primary" disabled={chatLoading || !chatInput.trim()} style={{ padding: "7px 12px", fontSize: 12 }}>
                ↵
              </button>
            </form>
          )}
          </div>
        </Panel>

        <PanelResizeHandle className="ResizeHandle" />

        {/* Center: Audit Timeline */}
        <Panel defaultSize={44} minSize={30}>
          <div style={{
            display: "flex", flexDirection: "column", height: "100%", overflow: "hidden",
          }}>
          <div style={{
            padding: "10px 14px", borderBottom: "1px solid var(--border-subtle)",
            background: "var(--bg-surface)", display: "flex", alignItems: "center", gap: 8, flexShrink: 0,
          }}>
            <span className="card-header" style={{ marginBottom: 0 }}>Audit Timeline</span>
            <span className="badge badge-neutral">{events.length} events</span>
          </div>
          <div style={{ flex: 1, overflowY: "auto", padding: "12px" }}>
            <AuditTimeline events={events} />
          </div>
          </div>
        </Panel>

        <PanelResizeHandle className="ResizeHandle" />

        {/* Right: Cart & Checkout */}
        <Panel defaultSize={28} minSize={20}>
          <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
          <div style={{
            padding: "10px 14px", borderBottom: "1px solid var(--border-subtle)",
            background: "var(--bg-surface)", flexShrink: 0,
          }}>
            <span className="card-header" style={{ marginBottom: 0 }}>Cart & Checkout</span>
          </div>
          <div style={{ flex: 1, overflowY: "auto", padding: "12px", display: "flex", flexDirection: "column", gap: 12 }}>
            <CartSummary cart={cart} budgetCap={budgetCap} onRemove={handleRemoveCartItem} />
            {isOrderConfirmed && createdOrder?.payload?.razorpay_order_id && (
              <PaymentSuccess 
                orderId={createdOrder.payload.razorpay_order_id} 
                amount={createdOrder.payload.amount_paise ? createdOrder.payload.amount_paise / 100 : (cart?.total_inr || 0)} 
              />
            )}
            {!isOrderConfirmed &&
            createdOrder &&
            Number(createdOrder.payload?.amount_paise ?? 0) > 0 && (
              <ApprovalDialog
                cart={cart}
                amount={createdOrder.payload?.amount_paise ? createdOrder.payload.amount_paise / 100 : cart?.total_inr}
                orderId={createdOrder.payload?.razorpay_order_id}
                onPay={() => handlePayment(
                  createdOrder.payload?.id,
                  createdOrder.payload?.razorpay_order_id,
                  createdOrder.payload?.amount_paise ? createdOrder.payload.amount_paise / 100 : (cart?.total_inr || 0)
                )}
                paymentLoading={paymentLoading}
              />
            )}
            {!isOrderConfirmed && createdOrder && approvalError && (
              <div style={{ marginTop: 8, padding: "8px 12px", background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.3)", borderRadius: 6, fontSize: 12, color: "#f87171" }}>
                {approvalError}
              </div>
            )}
            {showApproval &&
            !createdOrder &&
            !isOrderConfirmed &&
            (cart?.total_inr ?? 0) > 0 && (
              <>
                <ApprovalDialog 
                  cart={cart} 
                  amount={cart?.total_inr}
                  onDecide={handleDecision} 
                  loading={approvalLoading} 
                />
                {approvalError && (
                  <div style={{ marginTop: 8, padding: "8px 12px", background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.3)", borderRadius: 6, fontSize: 12, color: "#f87171" }}>
                    {approvalError}
                  </div>
                )}
              </>
            )}
          </div>
          </div>
        </Panel>
      </PanelGroup>
    </div>
  );
}
