import { NextResponse } from "next/server";
import { MERCHANT_URL, MERCHANT_API_KEY } from "@/lib/serverConfig";

export async function GET() {
  try {
    const upstream = await fetch(`${MERCHANT_URL}/sessions`, {
      headers: { "X-API-Key": MERCHANT_API_KEY },
      cache: "no-store",
    });
    const data = await upstream.text();
    return new NextResponse(data, {
      status: upstream.status,
      headers: { "Content-Type": "application/json" },
    });
  } catch {
    return NextResponse.json({ error: "MERCHANT_SERVER_UNREACHABLE" }, { status: 502 });
  }
}
