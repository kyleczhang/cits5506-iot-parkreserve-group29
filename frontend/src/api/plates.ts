/**
 * `/api/v1/users/me/plates` REST module.
 */
import { http } from "./client";
import { z } from "zod";
import { plateOut, type PlateAddRequest, type PlateOut } from "@/schemas/plate";

const BASE = "/api/v1/users/me/plates";

export async function listPlates(): Promise<PlateOut[]> {
  const json = await http.get(BASE).json();
  return z.array(plateOut).parse(json);
}

export async function addPlate(req: PlateAddRequest): Promise<PlateOut> {
  const json = await http.post(BASE, { json: req }).json();
  return plateOut.parse(json);
}

export async function removePlate(plate: string): Promise<void> {
  await http.delete(`${BASE}/${encodeURIComponent(plate)}`);
}
