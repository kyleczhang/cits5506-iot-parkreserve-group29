/**
 * Register page.
 *
 * Backend `POST /auth/register` does not return a JWT; `AuthProvider.register`
 * chains a login immediately so the user is fully signed in by the time
 * we navigate to `/app`.
 */
import { Link, useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { ArrowLeft, Mail, Lock, User as UserIcon, UserPlus } from "lucide-react";

import { useAuth } from "@/auth/AuthProvider";
import { ApiError } from "@/api/client";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { registerRequest, type RegisterRequest } from "@/schemas/auth";
import { AuthShell } from "./shell";

export function RegisterPage() {
  const navigate = useNavigate();
  const { register: registerUser } = useAuth();
  const [formError, setFormError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
    setError,
  } = useForm<RegisterRequest>({
    resolver: zodResolver(registerRequest),
  });

  const onSubmit = handleSubmit(async (values) => {
    setFormError(null);
    try {
      await registerUser(values);
      navigate("/app", { replace: true });
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setError("email", { message: "Email is already registered." });
      } else if (err instanceof ApiError && err.status === 422) {
        setFormError(err.message);
      } else if (err instanceof ApiError) {
        setFormError(err.message);
      } else {
        setFormError("Registration failed. Please try again.");
      }
    }
  });

  return (
    <AuthShell
      title="Create account"
      subtitle="Add a driver account to start booking bays."
    >
      <form className="flex flex-col gap-4" onSubmit={onSubmit} noValidate>
        <Field
          label="Full name"
          autoComplete="name"
          required
          leadingIcon={<UserIcon className="h-4 w-4" aria-hidden="true" />}
          error={errors.name?.message}
          {...register("name")}
        />
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
          autoComplete="new-password"
          required
          helper="At least 8 characters."
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
          leadingIcon={<UserPlus className="h-4 w-4" />}
        >
          Create account
        </Button>
      </form>

      <p className="mt-6 text-sm text-text-muted">
        Already have an account?{" "}
        <Link to="/login" className="font-medium text-brand hover:underline">
          Sign in instead
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
