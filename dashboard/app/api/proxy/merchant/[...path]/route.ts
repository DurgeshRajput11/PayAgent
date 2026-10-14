import { NextRequest, NextResponse } from "next/server";
import { MERCHANT_URL, MERCHANT_API_KEY } from "@/lib/serverConfig";

// Proxies /api/proxy/merchant/<anything> -> ${MERCHANT_URL}/api/v1/<anything>,
// attaching X-API-Key server-side. The browser never sees MERCHANT_API_KEY.
// Covers cart get/add/remove and order create/confirm.

async function forward(req: NextRequest, path: string[]) {
  const search = req.nextUrl.search || "";
  const target = `${MERCHANT_URL}/api/v1/${path.join("/")}${search}`;

  const init: RequestInit = {
    method: req.method,
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": MERCHANT_API_KEY,
    },
  };

  if (req.method === "POST" || req.method === "PATCH") {
    const body = await req.text();
    if (body) init.body = body;
  }

  let upstream: Response;
  try {
    upstream = await fetch(target, init);
  } catch (err) {
    return NextResponse.json({ error: "MERCHANT_SERVER_UNREACHABLE" }, { status: 502 });
  }

  const data = await upstream.text();
  return new NextResponse(data, {
    status: upstream.status,
    headers: { "Content-Type": upstream.headers.get("Content-Type") || "application/json" },
  });
}

export async function GET(req: NextRequest, { params }: { params: { path: string[] } }) {
  return forward(req, params.path);
}

export async function POST(req: NextRequest, { params }: { params: { path: string[] } }) {
  return forward(req, params.path);
}

export async function DELETE(req: NextRequest, { params }: { params: { path: string[] } }) {
  return forward(req, params.path);
}
