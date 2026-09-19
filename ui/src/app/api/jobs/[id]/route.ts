// Server-side proxy for a single job's detail (unauthenticated read).
import { NextResponse } from "next/server";
import { apiGet } from "@/lib/api";
import type { Job } from "@/lib/types";

export async function GET(_req: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const result = await apiGet<Job>(`/jobs/${encodeURIComponent(id)}`);

  if (result.ok) {
    return NextResponse.json(result.data);
  }
  if (result.unreachable) {
    return NextResponse.json({ error: result.error }, { status: 503 });
  }
  return NextResponse.json({ error: result.error }, { status: result.status });
}
