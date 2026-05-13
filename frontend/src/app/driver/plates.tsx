/**
 * Plates page — bind / unbind licence plates against the current user.
 *
 * Backend cap is 5 plates/user; the UI surfaces an at-cap badge and
 * disables the add button accordingly. Plate strings are normalised
 * to upper-case-no-spaces in the Zod transform, with a live preview
 * below the input so the user sees the canonical form before submit.
 */
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { Car, Trash2, Plus, ShieldAlert } from "lucide-react";
import * as AlertDialog from "@radix-ui/react-alert-dialog";

import * as platesApi from "@/api/plates";
import { qk } from "@/api/queryKeys";
import { ApiError } from "@/api/client";
import { Card } from "@/components/ui/Card";
import { Field } from "@/components/ui/Field";
import { Button } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Spinner";
import { pushToast } from "@/components/ui/toastStore";
import {
  normalisePlate,
  plateAddRequest,
  type PlateAddRequest,
} from "@/schemas/plate";

const PLATES_PER_USER_MAX = 5;

export function PlatesPage() {
  const queryClient = useQueryClient();
  const plates = useQuery({ queryKey: qk.plates.list(), queryFn: platesApi.listPlates });

  const {
    register,
    handleSubmit,
    watch,
    reset,
    formState: { errors, isSubmitting },
    setError,
  } = useForm<PlateAddRequest>({
    resolver: zodResolver(plateAddRequest),
  });
  const rawPlate = watch("plate") ?? "";
  const preview = rawPlate ? normalisePlate(rawPlate) : "";

  const addMutation = useMutation({
    mutationFn: (req: PlateAddRequest) => platesApi.addPlate(req),
    onSuccess: () => {
      reset();
      void queryClient.invalidateQueries({ queryKey: qk.plates.list() });
      pushToast({ tone: "success", title: "Plate bound" });
    },
    onError: (err) => {
      if (err instanceof ApiError) {
        setError("plate", { message: err.message });
      } else {
        setError("plate", { message: "Couldn't bind the plate." });
      }
    },
  });

  const onSubmit = handleSubmit((values) => addMutation.mutate(values));

  const count = plates.data?.length ?? 0;
  const atCap = count >= PLATES_PER_USER_MAX;

  return (
    <div className="grid gap-8 lg:grid-cols-[1fr_1fr]">
      <section aria-labelledby="add-plate-heading">
        <header className="mb-4 flex items-baseline justify-between">
          <h2
            id="add-plate-heading"
            className="text-xl font-semibold tracking-tight"
          >
            Add a licence plate
          </h2>
          <span className="text-sm text-text-muted">
            {count} / {PLATES_PER_USER_MAX}
          </span>
        </header>

        <Card className="p-5">
          <form className="flex flex-col gap-4" onSubmit={onSubmit} noValidate>
            <Field
              label="Plate"
              required
              placeholder="ABC123"
              autoComplete="off"
              leadingIcon={<Car className="h-4 w-4" aria-hidden="true" />}
              helper={
                preview && preview !== rawPlate
                  ? `Will be saved as "${preview}"`
                  : "Letters and digits, no spaces. Saved in upper case."
              }
              error={errors.plate?.message}
              disabled={atCap}
              {...register("plate")}
            />
            <Field
              label="Label (optional)"
              placeholder="e.g. Family car"
              autoComplete="off"
              error={errors.label?.message}
              disabled={atCap}
              {...register("label")}
            />
            {atCap ? (
              <p
                role="alert"
                className="inline-flex items-center gap-2 rounded-lg border border-warn/40 bg-warn/10 p-3 text-sm text-text"
              >
                <ShieldAlert className="h-4 w-4 text-warn" aria-hidden="true" />
                You&apos;ve reached the {PLATES_PER_USER_MAX}-plate cap. Remove
                one to add another.
              </p>
            ) : null}
            <Button
              type="submit"
              loading={isSubmitting || addMutation.isPending}
              disabled={atCap}
              leadingIcon={<Plus className="h-4 w-4" />}
            >
              Bind plate
            </Button>
          </form>
        </Card>
      </section>

      <section aria-labelledby="bound-plates-heading">
        <header className="mb-4 flex items-baseline justify-between">
          <h2
            id="bound-plates-heading"
            className="text-xl font-semibold tracking-tight"
          >
            Bound plates
          </h2>
        </header>

        {plates.isLoading ? (
          <Card className="grid h-32 place-items-center">
            <Spinner label="Loading plates" />
          </Card>
        ) : count === 0 ? (
          <Card className="p-5 text-sm text-text-muted">
            No plates bound yet. Add one on the left to start booking.
          </Card>
        ) : (
          <ul className="flex flex-col gap-2">
            {plates.data?.map((p) => (
              <PlateRow key={p.id} plate={p.plate} label={p.label ?? null} />
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

interface RowProps {
  plate: string;
  label: string | null;
}

function PlateRow({ plate, label }: RowProps) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const mutation = useMutation({
    mutationFn: () => platesApi.removePlate(plate),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: qk.plates.list() });
      pushToast({ tone: "success", title: `Plate ${plate} removed` });
      setOpen(false);
    },
    onError: () => {
      pushToast({ tone: "danger", title: "Couldn't remove plate" });
    },
  });

  return (
    <li>
      <Card className="flex items-center justify-between gap-3 p-4">
        <div>
          <p className="font-mono text-lg font-semibold leading-none">{plate}</p>
          {label ? (
            <p className="mt-1 text-sm text-text-muted">{label}</p>
          ) : null}
        </div>
        <AlertDialog.Root open={open} onOpenChange={setOpen}>
          <AlertDialog.Trigger asChild>
            <Button
              variant="ghost"
              size="sm"
              aria-label={`Remove plate ${plate}`}
              leadingIcon={<Trash2 className="h-4 w-4 text-danger" />}
            >
              Remove
            </Button>
          </AlertDialog.Trigger>
          <AlertDialog.Portal>
            <AlertDialog.Overlay className="fixed inset-0 z-40 bg-black/40 data-[state=open]:animate-fade-in" />
            <AlertDialog.Content
              className={
                "fixed left-1/2 top-1/2 z-50 w-[min(420px,calc(100vw-2rem))] -translate-x-1/2 -translate-y-1/2 " +
                "rounded-xl border border-border bg-surface p-5 shadow-card-hover data-[state=open]:animate-fade-in"
              }
            >
              <AlertDialog.Title className="text-base font-semibold">
                Remove plate {plate}?
              </AlertDialog.Title>
              <AlertDialog.Description className="mt-2 text-sm text-text-muted">
                Any active reservation will be updated and re-published over
                MQTT. You can re-bind the plate at any time.
              </AlertDialog.Description>
              <div className="mt-5 flex justify-end gap-2">
                <AlertDialog.Cancel asChild>
                  <Button variant="ghost">Cancel</Button>
                </AlertDialog.Cancel>
                <Button
                  variant="danger"
                  loading={mutation.isPending}
                  onClick={() => mutation.mutate()}
                >
                  Remove
                </Button>
              </div>
            </AlertDialog.Content>
          </AlertDialog.Portal>
        </AlertDialog.Root>
      </Card>
    </li>
  );
}
