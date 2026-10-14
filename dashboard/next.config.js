/** @type {import('next').NextConfig} */
const nextConfig = {
  // NEXT_PUBLIC_MERCHANT_URL / NEXT_PUBLIC_AGENT_URL used to live here so
  // the browser could call those services directly, with the shared API
  // key hardcoded in client components. The dashboard now proxies every
  // privileged call server-side (see app/api/proxy/*, lib/serverConfig.ts),
  // so those two are gone — MERCHANT_URL / AGENT_URL (no NEXT_PUBLIC_
  // prefix) are read straight from process.env on the server instead,
  // never exposed to the client bundle.
  //
  // NEXT_PUBLIC_RAZORPAY_KEY_ID is still here because Razorpay's key id
  // (not the secret) is meant to be public — it's what Checkout.js needs
  // client-side to open the payment widget.
  env: {
    NEXT_PUBLIC_RAZORPAY_KEY_ID: process.env.NEXT_PUBLIC_RAZORPAY_KEY_ID || "",
  },
};

module.exports = nextConfig;
