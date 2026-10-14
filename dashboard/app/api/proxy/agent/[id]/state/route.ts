import { NextResponse } from "next/server";
import { AGENT_URL, AGENT_SERVICE_API_KEY } from "@/lib/serverConfig";

export async function GET(_req: Request, { params }: { params: { id: string } }) {
  try {
    const upstream = await fetch(`${AGENT_URL}/agent/${params.id}/state`, {
      headers: { "X-Internal-Key": AGENT_SERVICE_API_KEY },
      cache: "no-store",
    });
    const data = await upstream.text();
    return new NextResponse(data, {
      status: upstream.status,
      headers: { "Content-Type": "application/json" },
    });
  } catch {
    return NextResponse.json({ error: "AGENT_SERVICE_UNREACHABLE" }, { status: 502 });
  }
}
