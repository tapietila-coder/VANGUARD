// Server-side proxy for the backups list (unauthenticated read, same posture
// as every other read-only route) and backup creation (bearer-token
// protected — submits a real backup_create job to the existing Job Queue and
// returns the job, same pattern as api/jobs/route.ts).
import { NextResponse } from "next/server";
import { apiGet, apiPost } from "@/lib/api";
import type { BackupRecord, Job } from "@/lib/types";

export async function GET() {
  const result = await apiGet<BackupRecord[]>("/backups");
  if (result.ok) {
    return NextResponse.json(result.data);
  }
  if (result.unreachable) {
    return NextResponse.json({ error: result.error }, { status: 503 });
  }
  return NextResponse.json({ error: result.error }, { status: result.status });
}

export async function POST(req: Request) {
  let body: unknown = { reason: "manual" };
  try {
    const parsed = await req.json();
    if (parsed && typeof parsed === "object") body = parsed;
  } catch {
    // No/invalid JSON body — fall back to the default reason above, mirroring
    // the backend's own BackupCreateRequest default.
  }

  const result = await apiPost<Job>("/backups", undefined, body);
  if (result.ok) {
    return NextResponse.json(result.data, { status: 202 });
  }
  if (result.unreachable) {
    return NextResponse.json({ error: result.error }, { status: 503 });
  }
  return NextResponse.json({ error: result.error }, { status: result.status });
}
