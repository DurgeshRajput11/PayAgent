import { NextRequest, NextResponse } from "next/server";
import { AGENT_URL, AGENT_SERVICE_API_KEY } from "@/lib/serverConfig";

export async function POST(req: NextRequest, { params }: { params: { id: string } }) {
  const body = await req.text();
  try {
    const upstream = await fetch(`${AGENT_URL}/agent/${params.id}/message`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Internal-Key": AGENT_SERVICE_API_KEY,
      },
      body,
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
