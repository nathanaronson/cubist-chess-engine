// STUB — Person D owns. REST + WS client. See plans/person-d-frontend.md.

import type { Envelope } from "./events";

export async function fetchEngines(): Promise<unknown> {
  const r = await fetch("/api/engines");
  return r.json();
}

export function connectEvents(onEvent: (e: Envelope["event"]) => void): WebSocket {
  const ws = new WebSocket(`ws://${location.host}/ws`);
  ws.onmessage = (msg) => {
    const env = JSON.parse(msg.data) as Envelope;
    onEvent(env.event);
  };
  return ws;
}
