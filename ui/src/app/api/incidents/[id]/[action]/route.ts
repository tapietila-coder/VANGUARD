// Server-side proxy for the mutating acknowledge/resolve actions — the one
// place in this route holding the VANGUARD_API_TOKEN bearer token, matching
// the exact pattern established by jobs/[id]/[action]/route.ts.
import { NextResponse } from "next/server";
import { apiPost } from "@/lib/api";
import type { Incident } from "@/lib/types";

const ALLOWED_ACTIONS = new Set(["acknowledge", "resolve"]);

export async function POST(
  req: Request,
  { params }: { params: Promise<{ id: string; action: string }> }
) {
  const { id, action } = await params;
  if (!ALLOWED_ACTIONS.has(action)) {
    return NextResponse.json({ error: `Unknown action "${action}"` }, { status: 400 });
  }

  let reason = "";
  try {
    const body = await req.json();
    if (body && typeof body.reason === "string") reason = body.reason;
  } catch {
    // No JSON body sent — proceed with no reason, same as the backend default.
  }

  const result = await apiPost<Incident>(
    `/incidents/${encodeURIComponent(id)}/${action}`,
    undefined,
    { reason }
  );

  if (result.ok) {
    return NextResponse.json(result.data);
  }
  if (result.unreachable) {
    return NextResponse.json({ error: result.error }, { status: 503 });
  }
  return NextResponse.json({ error: result.error }, { status: result.status });
}
