/**
 * `/api/v1/auth/*` REST module.
 */
import { http } from "./client";
import {
  loginRequest,
  registerRequest,
  tokenResponse,
  userOut,
  type LoginRequest,
  type RegisterRequest,
  type TokenResponse,
  type UserOut,
} from "@/schemas/auth";

const BASE = "/api/v1/auth";

/** Exchange credentials for a JWT. */
export async function login(req: LoginRequest): Promise<TokenResponse> {
  const json = await http
    .post(`${BASE}/login`, { json: loginRequest.parse(req) })
    .json();
  return tokenResponse.parse(json);
}

/** Register a new driver account; backend returns the `UserOut`. */
export async function register(req: RegisterRequest): Promise<UserOut> {
  const json = await http
    .post(`${BASE}/register`, { json: registerRequest.parse(req) })
    .json();
  return userOut.parse(json);
}

/** Current-user profile — used on app boot to validate any stored JWT. */
export async function me(): Promise<UserOut> {
  const json = await http.get(`${BASE}/me`).json();
  return userOut.parse(json);
}
