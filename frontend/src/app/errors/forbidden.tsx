/**
 * Authenticated-but-wrong-role landing page.
 */
import { Link } from "react-router-dom";
import { ArrowLeft, ShieldOff } from "lucide-react";
import { Button } from "@/components/ui/Button";

export function ForbiddenPage() {
  return (
    <div className="grid min-h-screen place-items-center bg-bg px-6 text-text">
      <div className="max-w-md text-center">
        <ShieldOff className="mx-auto h-10 w-10 text-danger" aria-hidden="true" />
        <h1 className="mt-4 text-2xl font-semibold">Not allowed</h1>
        <p className="mt-2 text-text-muted">
          Your account doesn&apos;t have permission to view that area.
        </p>
        <Link to="/app" className="mt-6 inline-block">
          <Button leadingIcon={<ArrowLeft className="h-4 w-4" />}>
            Back to dashboard
          </Button>
        </Link>
      </div>
    </div>
  );
}
