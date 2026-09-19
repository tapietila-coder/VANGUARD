// Server-side proxy for the mutating start/stop/restart actions. This is the
// one place in the UI that holds the VANGUARD_API_TOKEN bearer token (read
// server-side only, from lib/api.ts) — the browser never sees it, matching
// the pattern the existing resolve-by-name proxy established for CORS.
import { NextResponse } from "next/server";
import { apiPost } from "@/lib/api";
import type { ManagedProcessStatus } from "@/lib/types";

const ALLOWED_ACTIONS = new Set(["start", "stop", "restart"]);

export async function POST(
  _req: Request,
  { params }: { params: Promise<{ id: string; action: string }> }
) {
  const { id, action } = await params;
  if (!ALLOWED_ACTIONS.has(action)) {
    return NextResponse.json({ error: `Unknown action "${action}"` }, { status: 400 });
  }

  const result = await apiPost<ManagedProcessStatus>(
    `/services/${encodeURIComponent(id)}/${action}`
  );

  if (result.ok) {
    return NextResponse.json(result.data);
  }
  if (result.unreachable) {
    return NextResponse.json({ error: result.error }, { status: 503 });
  }
  return NextResponse.json({ error: result.error }, { status: result.status });
}
