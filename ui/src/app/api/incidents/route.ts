// Server-side proxy for the incidents list (unauthenticated read, same
// posture as every other list route). Passes through optional status/severity
// filters exactly as the backend's GET /incidents accepts them.
import { NextResponse } from "next/server";
import { apiGet } from "@/lib/api";
import type { Incident } from "@/lib/types";

export async function GET(req: Request) {
  const url = new URL(req.url);
  const params: Record<string, string> = {};
  const status = url.searchParams.get("status");
  const severity = url.searchParams.get("severity");
  if (status) params.status = status;
  if (severity) params.severity = severity;

  const result = await apiGet<Incident[]>("/incidents", params);
  if (result.ok) {
    return NextResponse.json(result.data);
  }
  if (result.unreachable) {
    return NextResponse.json({ error: result.error }, { status: 503 });
  }
  return NextResponse.json({ error: result.error }, { status: result.status });
}
