/**
 * Socket.IO client singleton.
 *
 * The backend exposes namespace `/ws` (see backend/app/sockets/events.py).
 * No auth handshake at the transport level today — we still gate the
 * connect to authenticated routes (plan §8) so the connection lifecycle
 * matches the user session.
 */
import { io, type Socket } from "socket.io-client";
import { BACKEND_ORIGIN } from "@/lib/env";

let _socket: Socket | null = null;

/**
 * Lazy-construct (and return) the shared socket. Safe to call from
 * multiple consumers; only one TCP connection is opened.
 */
export function getSocket(): Socket {
  if (_socket) return _socket;
  const target = BACKEND_ORIGIN || window.location.origin;
  _socket = io(`${target}/ws`, {
    autoConnect: false,
    transports: ["websocket"],
    reconnection: true,
    reconnectionAttempts: Infinity,
    reconnectionDelay: 1_000,
    reconnectionDelayMax: 5_000,
  });
  return _socket;
}

/** Open the socket (idempotent). */
export function connectSocket(): void {
  const s = getSocket();
  if (!s.connected && !s.active) s.connect();
}

/** Close the socket cleanly — used on sign-out. */
export function disconnectSocket(): void {
  if (_socket?.connected || _socket?.active) {
    _socket.disconnect();
  }
}
