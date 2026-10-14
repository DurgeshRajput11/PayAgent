import { NextRequest, NextResponse } from "next/server";
import { AGENT_URL, AGENT_SERVICE_API_KEY } from "@/lib/serverConfig";

export async function POST(req: NextRequest, { params }: { params: { id: string } }) {
  const body = await req.text();

  try {
    const upstream = await fetch(`${AGENT_URL}/agent/${params.id}/resume`, {
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
  } catch (error) {
    console.error("Agent resume proxy failed:", error);
    return NextResponse.json(
      { error: "AGENT_SERVER_UNREACHABLE" },
      { status: 502 }
    );
  }
}