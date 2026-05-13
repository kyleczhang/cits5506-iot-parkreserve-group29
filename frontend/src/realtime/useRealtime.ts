/**
 * Component-level hook that opens the socket, attaches the bus, and
 * tears both down on unmount. Mount this once at the top of any
 * authenticated layout (driver shell, admin shell).
 *
 * Re-attaches when the user id changes so owner-targeted events go
 * to the right cache.
 */
import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { attachBus } from "./bus";
import { connectSocket, disconnectSocket, getSocket } from "./socket";

export type ConnectionState = "connecting" | "connected" | "disconnected";

export function useRealtime(userId: string | null): ConnectionState {
  const queryClient = useQueryClient();
  const [conn, setConn] = useState<ConnectionState>(() =>
    getSocket().connected ? "connected" : "connecting",
  );

  useEffect(() => {
    connectSocket();
    const detach = attachBus(queryClient, { userId });
    const socket = getSocket();
    const onConnect = () => setConn("connected");
    const onDisconnect = () => setConn("disconnected");
    const onReconnectAttempt = () => setConn("connecting");
    socket.on("connect", onConnect);
    socket.on("disconnect", onDisconnect);
    socket.io.on("reconnect_attempt", onReconnectAttempt);
    return () => {
      socket.off("connect", onConnect);
      socket.off("disconnect", onDisconnect);
      socket.io.off("reconnect_attempt", onReconnectAttempt);
      detach();
    };
  }, [queryClient, userId]);

  // On sign-out (user becomes null AFTER the socket connected once),
  // close cleanly so we don't keep an idle WS in the background.
  useEffect(() => {
    return () => {
      if (userId === null) disconnectSocket();
    };
  }, [userId]);

  return conn;
}
