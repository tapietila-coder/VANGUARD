// Server-side proxy for the client-side service resolver form. The FastAPI
// backend has no CORS middleware, so the browser can't call it directly from
// a different origin/port; this route runs on the Next.js server (same origin
// as the browser sees it) and forwards to the real VANGUARD API.
import { NextResponse } from "next/server";
import { apiGet } from "@/lib/api";
import type { VanguardService } from "@/lib/types";

export async function GET(_req: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const result = await apiGet<VanguardService>(`/services/${encodeURIComponent(id)}`);

  if (result.ok) {
    return NextResponse.json(result.data);
  }
  if (result.unreachable) {
    return NextResponse.json({ error: result.error }, { status: 503 });
  }
  return NextResponse.json({ error: result.error }, { status: result.status });
}
