// Server-side proxy for the real current metrics sample (read-only,
// unauthenticated on the backend — no Depends(operator) on
// GET /metrics/current — proxied only because the backend has no CORS
// middleware, same posture as /api/system-health).
import { NextResponse } from "next/server";
import { apiGet } from "@/lib/api";
import type { MetricsCurrentResponse } from "@/lib/types";

export async function GET() {
  const result = await apiGet<MetricsCurrentResponse>("/metrics/current");
  if (result.ok) {
    return NextResponse.json(result.data);
  }
  if (result.unreachable) {
    return NextResponse.json({ error: result.error }, { status: 503 });
  }
  return NextResponse.json({ error: result.error }, { status: result.status });
}
