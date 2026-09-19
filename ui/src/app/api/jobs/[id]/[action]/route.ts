// Server-side proxy for the mutating cancel/retry actions — the one place in
// this route holding the VANGUARD_API_TOKEN bearer token, matching the exact
// pattern established by services/[id]/process/[action]/route.ts.
import { NextResponse } from "next/server";
import { apiPost } from "@/lib/api";
import type { Job } from "@/lib/types";

const ALLOWED_ACTIONS = new Set(["cancel", "retry"]);

export async function POST(
  _req: Request,
  { params }: { params: Promise<{ id: string; action: string }> }
) {
  const { id, action } = await params;
  if (!ALLOWED_ACTIONS.has(action)) {
    return NextResponse.json({ error: `Unknown action "${action}"` }, { status: 400 });
  }

  const result = await apiPost<Job>(`/jobs/${encodeURIComponent(id)}/${action}`);

  if (result.ok) {
    return NextResponse.json(result.data);
  }
  if (result.unreachable) {
    return NextResponse.json({ error: result.error }, { status: 503 });
  }
  return NextResponse.json({ error: result.error }, { status: result.status });
}
