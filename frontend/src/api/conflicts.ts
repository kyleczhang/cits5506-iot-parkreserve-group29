/**
 * `/api/v1/conflicts/*` REST module — admin-only.
 *
 * `getEvidence` returns the JPEG body as a `Blob` so the caller can
 * wrap it in `URL.createObjectURL` (the endpoint is JWT-protected, so
 * a plain `<img src>` to the URL wouldn't carry the auth header).
 */
import { http } from "./client";
import { z } from "zod";
import {
  conflictOut,
  type ConflictOut,
  type ConflictResolveRequest,
} from "@/schemas/conflict";

const BASE = "/api/v1/conflicts";

export async function listOpenConflicts(): Promise<ConflictOut[]> {
  const json = await http.get(BASE).json();
  return z.array(conflictOut).parse(json);
}

export async function getEvidence(id: string): Promise<Blob> {
  return http.get(`${BASE}/${id}/evidence`).blob();
}

export async function resolveConflict(
  id: string,
  req: ConflictResolveRequest,
): Promise<ConflictOut> {
  const json = await http.post(`${BASE}/${id}/resolve`, { json: req }).json();
  return conflictOut.parse(json);
}
