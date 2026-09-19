// Server-side proxy for the System Health aggregate (read-only, unauthenticated
// on the backend — no Depends(operator) on GET /system-health — proxied only
// because the backend has no CORS middleware, same posture as /api/logs).
import { NextResponse } from "next/server";
import { apiGet } from "@/lib/api";
import type { SystemHealthReport } from "@/lib/types";

export async function GET() {
  const result = await apiGet<SystemHealthReport>("/system-health");
  if (result.ok) {
    return NextResponse.json(result.data);
  }
  if (result.unreachable) {
    return NextResponse.json({ error: result.error }, { status: 503 });
  }
  return NextResponse.json({ error: result.error }, { status: result.status });
}
