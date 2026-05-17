/**
 * Right-side drawer built on Radix Dialog.
 *
 * Used by the payments page (transaction detail) and the conflicts
 * queue (per-row detail with evidence image).
 */
import * as Dialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  children: ReactNode;
  /** Drawer width on `md+`. */
  width?: string;
}

export function Drawer({
  open,
  onOpenChange,
  title,
  description,
  children,
  width = "min(520px, 100vw)",
}: Props) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/40 data-[state=open]:animate-fade-in" />
        <Dialog.Content
          className={cn(
            "fixed right-0 top-0 z-50 flex h-screen flex-col bg-surface text-text",
            "border-l border-border shadow-card-hover",
            "data-[state=open]:animate-slide-in-right",
            "focus:outline-none",
          )}
          style={{ width }}
        >
          <header className="flex items-start justify-between gap-3 border-b border-border p-5">
            <div>
              <Dialog.Title className="text-base font-semibold">
                {title}
              </Dialog.Title>
              {description ? (
                <Dialog.Description className="mt-0.5 text-sm text-text-muted">
                  {description}
                </Dialog.Description>
              ) : null}
            </div>
            <Dialog.Close
              aria-label="Close"
              className="rounded p-1 text-text-muted hover:bg-surface-2 hover:text-text focus-visible:bg-surface-2"
            >
              <X className="h-4 w-4" />
            </Dialog.Close>
          </header>
          <div className="flex-1 overflow-y-auto p-5">{children}</div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
