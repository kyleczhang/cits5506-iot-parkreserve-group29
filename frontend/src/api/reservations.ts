/**
 * `/api/v1/reservations/*` REST module.
 *
 * The check-in endpoint deliberately throws an `ApiError` with code
 * `vehicle_not_detected_yet` on 409 — the call site (`reservation
 * cockpit`) is expected to treat that as a "wait for WS" signal,
 * NOT a user-facing error. See plan §5.5.
 */
import { http } from "./client";
import { z } from "zod";
import {
  reservationOut,
  type ReservationCheckInRequest,
  type ReservationCreateRequest,
  type ReservationOut,
} from "@/schemas/reservation";

const BASE = "/api/v1/reservations";

export async function createReservation(
  req: ReservationCreateRequest,
): Promise<ReservationOut> {
  const json = await http.post(BASE, { json: req }).json();
  return reservationOut.parse(json);
}

export async function listReservations(): Promise<ReservationOut[]> {
  const json = await http.get(BASE).json();
  return z.array(reservationOut).parse(json);
}

export async function getReservation(id: string): Promise<ReservationOut> {
  const json = await http.get(`${BASE}/${id}`).json();
  return reservationOut.parse(json);
}

export async function cancelReservation(id: string): Promise<ReservationOut> {
  const json = await http.post(`${BASE}/${id}/cancel`).json();
  return reservationOut.parse(json);
}

export async function checkInReservation(
  id: string,
  req: ReservationCheckInRequest,
): Promise<ReservationOut> {
  const json = await http.post(`${BASE}/${id}/check-in`, { json: req }).json();
  return reservationOut.parse(json);
}
