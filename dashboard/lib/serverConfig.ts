// Server-only config. Nothing in this file is prefixed NEXT_PUBLIC_, so none
// of it is ever bundled into client-side JavaScript. Every route under
// app/api/proxy/* imports from here instead of reading these vars directly,
// so there's exactly one place that holds the shared service keys.
//
// This replaces the previous setup, where the dashboard called the Go
// merchant server directly from the browser with the API key hardcoded in
// client-side source (dashboard/app/session/[id]/page.tsx used to ship
// "internal-agent-api-key-change-in-prod" straight into the JS bundle).

export const MERCHANT_URL = process.env.MERCHANT_URL || "http://localhost:8080";
export const MERCHANT_API_KEY = process.env.MERCHANT_API_KEY || "internal-agent-api-key-change-in-prod";

export const AGENT_URL = process.env.AGENT_URL || "http://localhost:8001";
export const AGENT_SERVICE_API_KEY = process.env.AGENT_SERVICE_API_KEY || "internal-agent-service-key-change-in-prod";
