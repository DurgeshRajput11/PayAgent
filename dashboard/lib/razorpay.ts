"use client";

// Previously "Complete Payment with Razorpay" did a bare setTimeout(1000)
// and then called the confirm endpoint directly — no card entry, no
// Razorpay involvement at all, so an order could be marked "paid" with no
// evidence any payment ever happened. This loads the real Razorpay
// Checkout.js widget and only resolves once Razorpay itself reports a
// successful payment with a verifiable signature.

declare global {
  interface Window {
    Razorpay?: new (options: Record<string, unknown>) => { open: () => void };
  }
}

let scriptPromise: Promise<boolean> | null = null;

function loadRazorpayScript(): Promise<boolean> {
  if (typeof window === "undefined") return Promise.resolve(false);
  if (window.Razorpay) return Promise.resolve(true);
  if (scriptPromise) return scriptPromise;

  scriptPromise = new Promise((resolve) => {
    const script = document.createElement("script");
    script.src = "https://checkout.razorpay.com/v1/checkout.js";
    script.onload = () => resolve(true);
    script.onerror = () => resolve(false);
    document.body.appendChild(script);
  });
  return scriptPromise;
}

export interface RazorpayPaymentResult {
  razorpay_payment_id: string;
  razorpay_order_id: string;
  razorpay_signature: string;
}

export async function openRazorpayCheckout(params: {
  razorpayOrderId: string;
  amountPaise: number;
  name?: string;
  description?: string;
}): Promise<RazorpayPaymentResult> {
  const ok = await loadRazorpayScript();
  if (!ok || !window.Razorpay) {
    throw new Error("Could not load Razorpay Checkout. Check your connection and try again.");
  }

  const keyId = process.env.NEXT_PUBLIC_RAZORPAY_KEY_ID;
  if (!keyId) {
    throw new Error("NEXT_PUBLIC_RAZORPAY_KEY_ID is not configured.");
  }

  return new Promise((resolve, reject) => {
    const rzp = new window.Razorpay!({
      key: keyId,
      amount: params.amountPaise,
      currency: "INR",
      name: params.name || "PayAgent",
      description: params.description || "Order payment",
      order_id: params.razorpayOrderId,
      handler: (response: RazorpayPaymentResult) => resolve(response),
      modal: {
        ondismiss: () => reject(new Error("Payment cancelled")),
      },
      theme: { color: "#2563eb" },
    });
    rzp.open();
  });
}
