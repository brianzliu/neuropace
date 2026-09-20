import type { ServerMsg } from "./types";
import { backendUrl } from "./backend";

export type SocketStatus = "connecting" | "open" | "closed" | "reconnecting" | "failed";

/** WebSocket client for /ws/session/{id}: JSON text frames in and out, binary PCM frames out. */
export class SessionSocket {
  private ws: WebSocket | null = null;
  private closedByUser = false;
  private attempts = 0;
  private timer: number | null = null;

  constructor(
    private sessionId: string,
    private onMessage: (m: ServerMsg) => void,
    private onStatus: (s: SocketStatus) => void,
  ) {}

  private url(): string {
    const url = new URL(backendUrl(`/ws/session/${this.sessionId}`, true));
    url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
    return url.toString();
  }

  connect(): void {
    this.closedByUser = false;
    this.onStatus(this.attempts === 0 ? "connecting" : "reconnecting");
    const ws = new WebSocket(this.url());
    ws.binaryType = "arraybuffer";
    this.ws = ws;
    ws.onopen = () => {
      this.attempts = 0;
      this.onStatus("open");
    };
    ws.onmessage = (ev) => {
      if (typeof ev.data !== "string") return;
      try {
        this.onMessage(JSON.parse(ev.data) as ServerMsg);
      } catch {
        // ignore malformed frames
      }
    };
    ws.onclose = (ev) => {
      this.ws = null;
      if (this.closedByUser || ev.code === 4404) {
        this.onStatus("closed");
        return;
      }
      if (this.attempts >= 6) {
        this.onStatus("failed");
        return;
      }
      this.attempts += 1;
      const delay = Math.min(4000, 400 * 2 ** this.attempts);
      this.onStatus("reconnecting");
      this.timer = window.setTimeout(() => this.connect(), delay);
    };
    ws.onerror = () => {
      // onclose follows
    };
  }

  send(obj: Record<string, unknown>): boolean {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(obj));
      return true;
    }
    return false;
  }

  sendBinary(buf: ArrayBuffer): boolean {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(buf);
      return true;
    }
    return false;
  }

  get open(): boolean {
    return !!this.ws && this.ws.readyState === WebSocket.OPEN;
  }

  close(): void {
    this.closedByUser = true;
    if (this.timer !== null) window.clearTimeout(this.timer);
    this.ws?.close();
    this.ws = null;
  }
}
