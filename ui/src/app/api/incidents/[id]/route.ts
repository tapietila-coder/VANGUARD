// Server-side proxy for one incident's detail (unauthenticated read), same
// pattern as api/jobs/[id]/route.ts and api/backups/[id]/route.ts.
import { NextResponse } from "next/server";
import { apiGet } from "@/lib/api";
import type { Incident } from "@/lib/types";

export async function GET(_req: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const result = await apiGet<Incident>(`/incidents/${encodeURIComponent(id)}`);

  if (result.ok) {
    return NextResponse.json(result.data);
  }
  if (result.unreachable) {
    return NextResponse.json({ error: result.error }, { status: 503 });
  }
  return NextResponse.json({ error: result.error }, { status: result.status });
}
