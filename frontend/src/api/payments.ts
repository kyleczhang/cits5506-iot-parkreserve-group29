/**
 * `/api/v1/users/me/payments` REST module — read-only mock-payment ledger.
 */
import { http } from "./client";
import {
  transactionListResponse,
  transactionOut,
  type TransactionOut,
} from "@/schemas/payment";

const BASE = "/api/v1/users/me/payments";

export async function listPayments(): Promise<TransactionOut[]> {
  const json = await http.get(BASE).json();
  return transactionListResponse.parse(json).transactions;
}

export async function getPayment(id: string): Promise<TransactionOut> {
  const json = await http.get(`${BASE}/${id}`).json();
  return transactionOut.parse(json);
}
