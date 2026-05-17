/**
 * Conflict detail drawer — opened from the conflicts queue and from
 * the per-bay drill-down's "Open conflicts" tab.
 *
 * Resolve action limited to `vehicle_left` / `admin_resolved`
 * (the third value, `user_arrived_and_checked_in`, is server-set on
 * the weak-conflict fallback check-in path — plan §5.10).
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Check, FileWarning, Footprints } from "lucide-react";

import { listOpenConflicts, resolveConflict } from "@/api/conflicts";
import { qk } from "@/api/queryKeys";
import { ApiError } from "@/api/client";
import { Button } from "@/components/ui/Button";
import { Drawer } from "@/components/ui/Drawer";
import { Spinner } from "@/components/ui/Spinner";
import { EvidenceViewer } from "@/components/conflict/EvidenceViewer";
import { pushToast } from "@/components/ui/toastStore";
import { formatAbsolute } from "@/lib/time";
import { cn } from "@/lib/cn";
import type { ConflictResolveRequest } from "@/schemas/conflict";

interface Props {
  id: string;
  onClose: () => void;
}

export function ConflictDrawer({ id, onClose }: Props) {
  const queryClient = useQueryClient();
  // We re-use the open-conflicts cache rather than refetching detail,
  // since the API doesn't currently expose a per-conflict detail route.
  const list = useQuery({
    queryKey: qk.conflicts.open(),
    queryFn: listOpenConflicts,
  });
  const conflict = list.data?.find((c) => c.id === id);

  const [resolution, setResolution] = useState<
    ConflictResolveRequest["resolution"] | null
  >(null);

  const mutate = useMutation({
    mutationFn: (req: ConflictResolveRequest) => resolveConflict(id, req),
    onSuccess: () => {
      pushToast({ tone: "success", title: "Conflict resolved" });
      void queryClient.invalidateQueries({ queryKey: qk.conflicts.open() });
      onClose();
    },
    onError: (err) => {
      pushToast({
        tone: "danger",
        title: "Couldn't resolve",
        description: err instanceof ApiError ? err.message : undefined,
      });
    },
  });

  return (
    <Drawer
      open={Boolean(id)}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      title={
        conflict
          ? `Conflict at Bay ${conflict.bay_code}`
          : "Conflict detail"
      }
      description={
        conflict
          ? `${conflict.kind === "strong" ? "Strong" : "Weak"} conflict · raised ${formatAbsolute(conflict.detected_at)}`
          : undefined
      }
    >
      {!conflict ? (
        <Spinner label="Loading" />
      ) : (
        <div className="space-y-5">
          <EvidenceViewer conflict={conflict} />

          <section aria-labelledby="resolve-heading">
            <h3
              id="resolve-heading"
              className="text-sm font-semibold text-text"
            >
              Mark resolved
            </h3>
            <p className="mt-1 text-xs text-text-muted">
              Pick the resolution reason. The Pi clears the alarm + LED
              automatically once the row is closed.
            </p>
            <div className="mt-3 grid grid-cols-1 gap-2">
              <ResolutionChoice
                value="vehicle_left"
                label="Vehicle has left the bay"
                hint="Sensor cleared without further action."
                Icon={Footprints}
                selected={resolution === "vehicle_left"}
                onSelect={() => setResolution("vehicle_left")}
              />
              <ResolutionChoice
                value="admin_resolved"
                label="Admin resolved out-of-band"
                hint="Manually settled (e.g. spoke with the vehicle owner)."
                Icon={FileWarning}
                selected={resolution === "admin_resolved"}
                onSelect={() => setResolution("admin_resolved")}
              />
            </div>
            <div className="mt-4 flex justify-end">
              <Button
                loading={mutate.isPending}
                disabled={!resolution}
                onClick={() =>
                  resolution && mutate.mutate({ resolution })
                }
                leadingIcon={<Check className="h-4 w-4" />}
              >
                Resolve
              </Button>
            </div>
          </section>
        </div>
      )}
    </Drawer>
  );
}

interface ChoiceProps {
  value: ConflictResolveRequest["resolution"];
  label: string;
  hint: string;
  Icon: React.ComponentType<{ className?: string }>;
  selected: boolean;
  onSelect: () => void;
}

function ResolutionChoice({ label, hint, Icon, selected, onSelect }: ChoiceProps) {
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      className={cn(
        "flex w-full items-start gap-3 rounded-lg border p-3 text-left",
        "transition-colors duration-150 cursor-pointer",
        selected
          ? "border-brand bg-brand/10 ring-1 ring-brand"
          : "border-border hover:bg-surface-2",
      )}
    >
      <Icon
        aria-hidden="true"
        className={cn("mt-0.5 h-4 w-4 shrink-0", selected ? "text-brand" : "text-text-muted")}
      />
      <div>
        <p className="text-sm font-medium">{label}</p>
        <p className="text-xs text-text-muted">{hint}</p>
      </div>
    </button>
  );
}
