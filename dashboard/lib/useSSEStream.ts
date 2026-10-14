"use client";
import { useEffect, useRef, useState } from "react";

export interface AuditEvent {
  id: number;
  session_id: string;
  event_type: string;
  actor: string;
  reasoning: string;
  outcome: string;
  payload?: any;
  created_at: string;
}

export function useSSEStream(sessionId: string) {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    // Goes through our own server-side streaming proxy (app/api/proxy/stream/[id])
    // rather than the Go backend directly. /stream/:id now requires an API key,
    // and EventSource can't send custom headers at all — the proxy is what
    // attaches the key server-side and relays the SSE body through.
    const url = `/api/proxy/stream/${sessionId}`;
    const es = new EventSource(url);
    esRef.current = es;

    es.onopen = () => {
      console.log("[SSE CONNECTED]", url);
      setIsConnected(true);
    };

    es.addEventListener("audit_log", (e) => {
      const parsed: AuditEvent = JSON.parse(e.data);
      console.log("[SSE EVENT RECEIVED]", parsed);
      setEvents((prev) => {
        // Deduplicate events to handle transient network reconnects gracefully
        const exists = prev.find((ev) => ev.id === parsed.id);
        return exists ? prev : [...prev, parsed];
      });
    });

    es.onerror = () => setIsConnected(false);

    return () => {
      es.close();
      setIsConnected(false);
    };
  }, [sessionId]);

  return { events, isConnected };
}
