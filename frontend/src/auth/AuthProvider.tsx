/**
 * Auth provider.
 *
 * Owns:
 *   - the in-memory `user` (re-hydrated on boot by calling `/auth/me`),
 *   - the `signIn` / `register` / `signOut` mutations,
 *   - the `parkreserve:auth-expired` listener that fires when any
 *     request 401s, so the user is bounced to /login from any tab state.
 *
 * Why not `useQuery(['auth','me'])`? We need imperative auth state
 * available to React Router loaders (which run outside the component
 * tree); a dedicated provider gives us a single ref that the router
 * can consult synchronously. See plan §4 ("Auth lives in a single
 * AuthProvider keyed off the JWT").
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useQueryClient } from "@tanstack/react-query";

import * as authApi from "@/api/auth";
import { AUTH_EXPIRED_EVENT, ApiError, tokenStore } from "@/api/client";
import type {
  LoginRequest,
  RegisterRequest,
  UserOut,
} from "@/schemas/auth";

type AuthStatus = "idle" | "authenticating" | "authenticated" | "unauthenticated";

interface AuthContextValue {
  status: AuthStatus;
  user: UserOut | null;
  signIn: (req: LoginRequest) => Promise<UserOut>;
  register: (req: RegisterRequest) => Promise<UserOut>;
  signOut: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [user, setUser] = useState<UserOut | null>(null);
  const [status, setStatus] = useState<AuthStatus>(() =>
    tokenStore.get() ? "authenticating" : "unauthenticated",
  );

  // On boot, if we have a token, validate it. A 401 clears state.
  useEffect(() => {
    const token = tokenStore.get();
    if (!token) {
      setStatus("unauthenticated");
      return;
    }
    let cancelled = false;
    authApi
      .me()
      .then((profile) => {
        if (cancelled) return;
        setUser(profile);
        setStatus("authenticated");
      })
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 401) {
          tokenStore.clear();
        }
        setUser(null);
        setStatus("unauthenticated");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Cross-cutting 401 — every API call that 401s dispatches this.
  useEffect(() => {
    function handleExpiry() {
      setUser(null);
      setStatus("unauthenticated");
      queryClient.clear();
    }
    window.addEventListener(AUTH_EXPIRED_EVENT, handleExpiry);
    return () => window.removeEventListener(AUTH_EXPIRED_EVENT, handleExpiry);
  }, [queryClient]);

  const signIn = useCallback(
    async (req: LoginRequest) => {
      setStatus("authenticating");
      try {
        const res = await authApi.login(req);
        tokenStore.set(res.access_token);
        setUser(res.user);
        setStatus("authenticated");
        return res.user;
      } catch (err) {
        setStatus("unauthenticated");
        throw err;
      }
    },
    [],
  );

  const register = useCallback(async (req: RegisterRequest) => {
    // Register does NOT auto-login on the backend — it returns the user
    // and the caller must POST /login next. We chain the two for UX.
    const created = await authApi.register(req);
    const res = await authApi.login({ email: req.email, password: req.password });
    tokenStore.set(res.access_token);
    setUser(res.user);
    setStatus("authenticated");
    return created;
  }, []);

  const signOut = useCallback(() => {
    tokenStore.clear();
    setUser(null);
    setStatus("unauthenticated");
    queryClient.clear();
  }, [queryClient]);

  const value = useMemo<AuthContextValue>(
    () => ({ status, user, signIn, register, signOut }),
    [status, user, signIn, register, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

/** React hook — throws if used outside the provider (intentional). */
export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used inside <AuthProvider>");
  }
  return ctx;
}
