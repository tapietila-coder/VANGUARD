// Server-side proxy for the log-tail endpoint (read-only, unauthenticated on
// the backend, proxied only because the backend has no CORS middleware).
import { NextResponse } from "next/server";
import { apiGet } from "@/lib/api";
import type { ProcessLogsResponse } from "@/lib/types";

export async function GET(req: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const url = new URL(req.url);
  const lines = url.searchParams.get("lines") ?? "100";
  const result = await apiGet<ProcessLogsResponse>(`/services/${encodeURIComponent(id)}/logs`, { lines });

  if (result.ok) {
    return NextResponse.json(result.data);
  }
  if (result.unreachable) {
    return NextResponse.json({ error: result.error }, { status: 503 });
  }
  return NextResponse.json({ error: result.error }, { status: result.status });
}
