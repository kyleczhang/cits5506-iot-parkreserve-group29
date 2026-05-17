/**
 * Role gate used inside route elements.
 *
 *   <RequireRole role="admin"><AdminGrid /></RequireRole>
 *
 * If the user is unauthenticated, redirects to `/login?next=…`.
 * If authenticated with the wrong role, redirects to `/forbidden`.
 * While the auth state is still resolving, renders a quiet spinner so
 * we don't briefly flash the login page during a token-validation
 * round-trip on cold boot.
 */
import { Navigate, useLocation } from "react-router-dom";
import type { ReactNode } from "react";

import { useAuth } from "./AuthProvider";
import { Spinner } from "@/components/ui/Spinner";

interface Props {
  /** Optional role gate. If omitted, only authentication is required. */
  role?: "user" | "admin";
  children: ReactNode;
}

export function RequireRole({ role, children }: Props) {
  const { status, user } = useAuth();
  const location = useLocation();

  if (status === "authenticating") {
    return (
      <div className="grid min-h-[50vh] place-items-center">
        <Spinner label="Loading your session" />
      </div>
    );
  }

  if (status !== "authenticated" || !user) {
    const next = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/login?next=${next}`} replace />;
  }

  if (role && user.role !== role) {
    return <Navigate to="/forbidden" replace />;
  }

  return <>{children}</>;
}
