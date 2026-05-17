/**
 * Evidence-image viewer for strong-conflict rows.
 *
 * The `GET /api/v1/conflicts/{id}/evidence` endpoint is JWT-protected,
 * so we can't use a plain `<img src>` — instead we `fetch` the JPEG,
 * wrap in `URL.createObjectURL`, and revoke on unmount.
 *
 * When the image has been purged (404 — `image_purge_at` passed,
 * default 30 d), fall back to the textual evidence (recognised plate
 * + LPR confidence) per plan §5.10.
 */
import { useEffect, useState } from "react";
import { ImageOff } from "lucide-react";

import { getEvidence } from "@/api/conflicts";
import { ApiError } from "@/api/client";
import { Spinner } from "@/components/ui/Spinner";
import type { ConflictOut } from "@/schemas/conflict";

interface Props {
  conflict: ConflictOut;
}

export function EvidenceViewer({ conflict }: Props) {
  const [url, setUrl] = useState<string | null>(null);
  const [error, setError] = useState<"purged" | "other" | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (conflict.kind !== "strong") {
      setLoading(false);
      return;
    }
    let cancelled = false;
    let createdUrl: string | null = null;
    setLoading(true);
    setError(null);
    getEvidence(conflict.id)
      .then((blob) => {
        if (cancelled) return;
        createdUrl = URL.createObjectURL(blob);
        setUrl(createdUrl);
      })
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 404) {
          setError("purged");
        } else {
          setError("other");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
      if (createdUrl) URL.revokeObjectURL(createdUrl);
    };
  }, [conflict.id, conflict.kind]);

  if (conflict.kind === "weak") {
    return (
      <p className="rounded-lg border border-border bg-surface-2 p-3 text-sm text-text-muted">
        Weak conflicts have no evidence image — LPR didn&apos;t produce a
        confident result before the grace window expired.
      </p>
    );
  }

  if (loading) {
    return (
      <div className="grid h-48 place-items-center rounded-lg bg-surface-2">
        <Spinner label="Loading evidence" />
      </div>
    );
  }

  if (error === "purged") {
    return (
      <div className="space-y-2 rounded-lg border border-border bg-surface-2 p-4 text-sm">
        <p className="flex items-center gap-2 font-medium text-text">
          <ImageOff
            aria-hidden="true"
            className="h-4 w-4 text-text-muted"
          />
          Image retention expired
        </p>
        <p className="text-text-muted">
          The captured JPEG was purged automatically after 30 days. The
          recognised-plate text and confidence below remain in the audit
          record.
        </p>
        <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
          <dt className="text-text-muted">Plate</dt>
          <dd className="font-mono">{conflict.recognised_plate ?? "—"}</dd>
          <dt className="text-text-muted">Confidence</dt>
          <dd className="font-mono">
            {conflict.lpr_confidence !== null &&
            conflict.lpr_confidence !== undefined
              ? conflict.lpr_confidence.toFixed(2)
              : "—"}
          </dd>
        </dl>
      </div>
    );
  }

  if (error === "other" || !url) {
    return (
      <p className="rounded-lg border border-danger/30 bg-danger/10 p-3 text-sm text-danger">
        Couldn&apos;t load the evidence image.
      </p>
    );
  }

  return (
    <figure className="space-y-2">
      <img
        src={url}
        alt={
          conflict.recognised_plate
            ? `Strong-conflict evidence — LPR saw plate ${conflict.recognised_plate}`
            : "Strong-conflict evidence image"
        }
        className="w-full rounded-lg border border-border bg-black"
      />
      <figcaption className="text-xs text-text-muted">
        Plate{" "}
        <span className="font-mono text-text">
          {conflict.recognised_plate ?? "—"}
        </span>{" "}
        · confidence{" "}
        <span className="font-mono text-text">
          {conflict.lpr_confidence?.toFixed(2) ?? "—"}
        </span>
      </figcaption>
    </figure>
  );
}
