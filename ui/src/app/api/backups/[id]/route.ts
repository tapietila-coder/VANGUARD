// Server-side proxy for one backup's detail (unauthenticated read) and
// deletion (bearer-token protected, real DELETE against the backend).
import { NextResponse } from "next/server";
import { apiDelete, apiGet } from "@/lib/api";
import type { BackupRecord } from "@/lib/types";

export async function GET(_req: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const result = await apiGet<BackupRecord>(`/backups/${encodeURIComponent(id)}`);
  if (result.ok) {
    return NextResponse.json(result.data);
  }
  if (result.unreachable) {
    return NextResponse.json({ error: result.error }, { status: 503 });
  }
  return NextResponse.json({ error: result.error }, { status: result.status });
}

export async function DELETE(_req: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const result = await apiDelete<{ deleted: boolean; backup_id: string }>(
    `/backups/${encodeURIComponent(id)}`
  );
  if (result.ok) {
    return NextResponse.json(result.data);
  }
  if (result.unreachable) {
    return NextResponse.json({ error: result.error }, { status: 503 });
  }
  return NextResponse.json({ error: result.error }, { status: result.status });
}
