/**
 * `/api/v1/bays/*` REST module.
 *
 * Bay listing + detail is public (no JWT required) — the landing strip
 * uses this. The per-bay events endpoint is admin-only and is consumed
 * by the admin drill-down + telemetry pages.
 */
import { http } from "./client";
import { bayOut, bayEventOut, type BayOut, type BayEventOut } from "@/schemas/bay";
import { z } from "zod";

const BASE = "/api/v1/bays";

export async function listBays(): Promise<BayOut[]> {
  const json = await http.get(BASE).json();
  return z.array(bayOut).parse(json);
}

export async function getBay(code: string): Promise<BayOut> {
  const json = await http.get(`${BASE}/${encodeURIComponent(code)}`).json();
  return bayOut.parse(json);
}

export interface ListBayEventsOptions {
  limit?: number;
  /** ISO-8601 cursor — return events strictly older than this. */
  before?: string;
}

export async function listBayEvents(
  code: string,
  options: ListBayEventsOptions = {},
): Promise<BayEventOut[]> {
  const searchParams: Record<string, string | number> = {};
  if (options.limit !== undefined) searchParams["limit"] = options.limit;
  if (options.before !== undefined) searchParams["before"] = options.before;
  const json = await http
    .get(`${BASE}/${encodeURIComponent(code)}/events`, { searchParams })
    .json();
  return z.array(bayEventOut).parse(json);
}
