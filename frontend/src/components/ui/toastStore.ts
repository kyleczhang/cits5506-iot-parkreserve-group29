/**
 * Lightweight global toast store.
 *
 * `pushToast` is callable from anywhere (React tree, mutations, the
 * realtime bus); the `<Toaster>` component renders the queue via Radix
 * `<Toast.Root>` so we get free focus management + ARIA live regions.
 */

export type ToastTone = "info" | "success" | "warn" | "danger";

export interface ToastInput {
  title: string;
  description?: string | undefined;
  tone?: ToastTone;
  /** Auto-dismiss delay in ms (default 5000; danger = 8000). */
  durationMs?: number;
  /** Live-region politeness. */
  ariaLive?: "polite" | "assertive";
}

export interface ToastItem extends ToastInput {
  id: string;
  tone: ToastTone;
  durationMs: number;
  ariaLive: "polite" | "assertive";
}

type Listener = (items: ToastItem[]) => void;

let _items: ToastItem[] = [];
const _listeners = new Set<Listener>();

function notify() {
  for (const l of _listeners) l(_items);
}

export function pushToast(input: ToastInput): string {
  const tone: ToastTone = input.tone ?? "info";
  const item: ToastItem = {
    id:
      typeof crypto !== "undefined" && "randomUUID" in crypto
        ? crypto.randomUUID()
        : `t-${Date.now()}-${Math.random().toString(36).slice(2)}`,
    title: input.title,
    description: input.description,
    tone,
    durationMs: input.durationMs ?? (tone === "danger" ? 8000 : 5000),
    ariaLive:
      input.ariaLive ?? (tone === "danger" || tone === "warn" ? "assertive" : "polite"),
  };
  _items = [..._items, item];
  notify();
  return item.id;
}

export function dismissToast(id: string): void {
  _items = _items.filter((t) => t.id !== id);
  notify();
}

export function subscribeToasts(listener: Listener): () => void {
  _listeners.add(listener);
  listener(_items);
  return () => {
    _listeners.delete(listener);
  };
}
