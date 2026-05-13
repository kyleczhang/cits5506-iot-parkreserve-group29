/**
 * Zod mirrors for `/api/v1/auth/*` request and response shapes.
 *
 * The schemas are the single source of truth for both
 * (a) React-Hook-Form validation, and
 * (b) runtime parsing of backend responses (defends against contract
 * drift; the OpenAPI spec is canonical but humans can mis-edit it).
 */
import { z } from "zod";

export const loginRequest = z.object({
  email: z.string().email("must be a valid email"),
  password: z.string().min(1, "password required").max(128),
});
export type LoginRequest = z.infer<typeof loginRequest>;

export const registerRequest = z.object({
  email: z.string().email("must be a valid email"),
  name: z.string().min(1, "name required").max(120),
  password: z
    .string()
    .min(8, "at least 8 characters")
    .max(128, "at most 128 characters"),
});
export type RegisterRequest = z.infer<typeof registerRequest>;

export const userOut = z.object({
  id: z.string().uuid(),
  email: z.string().email(),
  name: z.string(),
  role: z.enum(["user", "admin"]),
});
export type UserOut = z.infer<typeof userOut>;

export const tokenResponse = z.object({
  access_token: z.string().min(1),
  token_type: z.string().default("Bearer"),
  user: userOut,
});
export type TokenResponse = z.infer<typeof tokenResponse>;
