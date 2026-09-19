// Server-side proxy for the jobs list (unauthenticated read, same posture as
// every other read-only route) and job submission (bearer-token protected,
// same CORS-workaround + token pattern as the process-control proxy).
import { NextResponse } from "next/server";
import { apiGet, apiPost } from "@/lib/api";
import type { Job } from "@/lib/types";

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url);
  const params: Record<string, string> = {};
  const state = searchParams.get("state");
  const jobType = searchParams.get("job_type");
  if (state) params.state = state;
  if (jobType) params.job_type = jobType;

  const result = await apiGet<Job[]>("/jobs", params);
  if (result.ok) {
    return NextResponse.json(result.data);
  }
  if (result.unreachable) {
    return NextResponse.json({ error: result.error }, { status: 503 });
  }
  return NextResponse.json({ error: result.error }, { status: result.status });
}

export async function POST(req: Request) {
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Request body must be JSON" }, { status: 400 });
  }

  const result = await apiPost<Job>("/jobs", undefined, body);
  if (result.ok) {
    return NextResponse.json(result.data, { status: 201 });
  }
  if (result.unreachable) {
    return NextResponse.json({ error: result.error }, { status: 503 });
  }
  return NextResponse.json({ error: result.error }, { status: result.status });
}
