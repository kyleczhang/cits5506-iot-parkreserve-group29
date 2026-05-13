/**
 * Login page.
 *
 * Routes by role on success:
 *   - admin → `/admin/grid` (when implemented)
 *   - everyone else → `/app` or the `?next=` redirect target.
 *
 * Maps backend 401 errors to a single helpful message; 422 errors
 * surface as field-level hints (RHF + Zod handle the local cases).
 */
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { LogIn, Mail, Lock, ArrowLeft } from "lucide-react";
import { useState } from "react";

import { useAuth } from "@/auth/AuthProvider";
import { ApiError } from "@/api/client";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { loginRequest, type LoginRequest } from "@/schemas/auth";
import { AuthShell } from "./shell";

export function LoginPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const { signIn } = useAuth();
  const [formError, setFormError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginRequest>({
    resolver: zodResolver(loginRequest),
  });

  const onSubmit = handleSubmit(async (values) => {
    setFormError(null);
    try {
      const user = await signIn(values);
      const next = params.get("next");
      if (next) {
        navigate(decodeURIComponent(next), { replace: true });
      } else {
        navigate(user.role === "admin" ? "/admin/grid" : "/app", { replace: true });
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setFormError("Email or password is incorrect.");
      } else if (err instanceof ApiError) {
        setFormError(err.message);
      } else {
        setFormError("Sign in failed. Please try again.");
      }
    }
  });

  return (
    <AuthShell
      title="Sign in"
      subtitle="Welcome back. Sign in to manage your reservations."
    >
      <form className="flex flex-col gap-4" onSubmit={onSubmit} noValidate>
        <Field
          label="Email"
          type="email"
          autoComplete="email"
          required
          leadingIcon={<Mail className="h-4 w-4" aria-hidden="true" />}
          error={errors.email?.message}
          {...register("email")}
        />
        <Field
          label="Password"
          type="password"
          autoComplete="current-password"
          required
          leadingIcon={<Lock className="h-4 w-4" aria-hidden="true" />}
          error={errors.password?.message}
          {...register("password")}
        />
        {formError ? (
          <p
            role="alert"
            className="rounded-lg border border-danger/30 bg-danger/10 p-3 text-sm text-danger"
          >
            {formError}
          </p>
        ) : null}
        <Button
          type="submit"
          loading={isSubmitting}
          size="lg"
          leadingIcon={<LogIn className="h-4 w-4" />}
        >
          Sign in
        </Button>
      </form>

      <p className="mt-6 text-sm text-text-muted">
        New here?{" "}
        <Link to="/register" className="font-medium text-brand hover:underline">
          Create a driver account
        </Link>
      </p>
      <Link
        to="/"
        className="mt-4 inline-flex items-center gap-1 text-sm text-text-muted hover:text-text"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden="true" /> Back to landing
      </Link>
    </AuthShell>
  );
}
