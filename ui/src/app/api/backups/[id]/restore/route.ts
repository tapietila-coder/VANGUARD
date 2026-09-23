// Server-side proxy for the one genuinely destructive backup action:
// restore. Bearer-token protected, holds the token server-side only, same
// pattern as jobs/[id]/[action]/route.ts.
import { NextResponse } from "next/server";
import { apiPost } from "@/lib/api";
import type { RestoreResult } from "@/lib/types";

export async function POST(req: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  let reason = "";
  try {
    const body = await req.json();
    if (body && typeof body.reason === "string") reason = body.reason;
  } catch {
    // No JSON body sent — restore with no reason, same as the backend default.
  }

  const result = await apiPost<RestoreResult>(
    `/backups/${encodeURIComponent(id)}/restore`,
    reason ? { reason } : undefined
  );
  if (result.ok) {
    return NextResponse.json(result.data);
  }
  if (result.unreachable) {
    return NextResponse.json({ error: result.error }, { status: 503 });
  }
  return NextResponse.json({ error: result.error }, { status: result.status });
}
