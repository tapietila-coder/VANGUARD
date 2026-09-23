// Server-side proxy for real historical metrics samples (read-only,
// unauthenticated on the backend — same posture as /api/metrics/current).
import { NextRequest, NextResponse } from "next/server";
import { apiGet } from "@/lib/api";
import type { MetricsHistoryResponse } from "@/lib/types";

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const params: Record<string, string> = {};
  for (const key of ["since", "until", "interval"]) {
    const value = searchParams.get(key);
    if (value) params[key] = value;
  }

  const result = await apiGet<MetricsHistoryResponse>("/metrics/history", params);
  if (result.ok) {
    return NextResponse.json(result.data);
  }
  if (result.unreachable) {
    return NextResponse.json({ error: result.error }, { status: 503 });
  }
  return NextResponse.json({ error: result.error }, { status: result.status });
}
