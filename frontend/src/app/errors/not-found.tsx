/**
 * Catch-all 404. Plain layout — no header/footer dependency on auth state.
 */
import { Link } from "react-router-dom";
import { ArrowLeft, Compass } from "lucide-react";
import { Button } from "@/components/ui/Button";

export function NotFoundPage() {
  return (
    <div className="grid min-h-screen place-items-center bg-bg px-6 text-text">
      <div className="max-w-md text-center">
        <Compass className="mx-auto h-10 w-10 text-text-muted" aria-hidden="true" />
        <h1 className="mt-4 text-2xl font-semibold">Page not found</h1>
        <p className="mt-2 text-text-muted">
          That URL doesn&apos;t match any route we know about.
        </p>
        <Link to="/" className="mt-6 inline-block">
          <Button leadingIcon={<ArrowLeft className="h-4 w-4" />}>
            Back to landing
          </Button>
        </Link>
      </div>
    </div>
  );
}
