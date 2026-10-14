import { NextRequest, NextResponse } from "next/server";
import { MERCHANT_URL, MERCHANT_API_KEY } from "@/lib/serverConfig";

export const dynamic = "force-dynamic";

// The browser's EventSource API cannot set custom headers, so there was no
// way for the old client-side `new EventSource(...)` call to carry an
// X-API-Key — which is exactly why /stream/:id used to be left
// unauthenticated on the Go server. This route does a server-side fetch
// (which CAN set the header) and pipes the upstream SSE body straight
// through to the browser, same-origin, so the client needs no key at all.
export async function GET(req: NextRequest, { params }: { params: { id: string } }) {
  let upstream: Response;
  try {
    upstream = await fetch(`${MERCHANT_URL}/stream/${params.id}`, {
     method: "GET",
     headers: {
      "X-API-Key": MERCHANT_API_KEY,
       Accept: "text/event-stream",
     },
     cache: "no-store",
    });
  } catch {
    return NextResponse.json({ error: "MERCHANT_SERVER_UNREACHABLE" }, { status: 502 });
  }

  if (!upstream.body) {
    return NextResponse.json({ error: "NO_STREAM_BODY" }, { status: 502 });
  }

  return new NextResponse(upstream.body, {
    status: upstream.status,
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
    },
  });
}
