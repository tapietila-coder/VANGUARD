// Server-side proxy for the read-only process-status endpoint. This route
// itself needs no bearer token (the backend leaves GET .../process
// unauthenticated, same posture as every other read-only route), but it
// still runs server-side because the backend has no CORS middleware.
import { NextResponse } from "next/server";
import { apiGet } from "@/lib/api";
import type { ManagedProcessStatus } from "@/lib/types";

export async function GET(_req: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const result = await apiGet<ManagedProcessStatus>(`/services/${encodeURIComponent(id)}/process`);

  if (result.ok) {
    return NextResponse.json(result.data);
  }
  if (result.unreachable) {
    return NextResponse.json({ error: result.error }, { status: 503 });
  }
  return NextResponse.json({ error: result.error }, { status: result.status });
}
