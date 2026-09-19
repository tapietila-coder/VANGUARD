// Server-side proxy for the cross-service log index (read-only,
// unauthenticated on the backend — no Depends(operator) on GET /logs —
// proxied only because the backend has no CORS middleware, same posture as
// the per-service /logs route).
import { NextResponse } from "next/server";
import { apiGet } from "@/lib/api";
import type { LogSource } from "@/lib/types";

export async function GET() {
  const result = await apiGet<LogSource[]>("/logs");
  if (result.ok) {
    return NextResponse.json(result.data);
  }
  if (result.unreachable) {
    return NextResponse.json({ error: result.error }, { status: 503 });
  }
  return NextResponse.json({ error: result.error }, { status: result.status });
}
