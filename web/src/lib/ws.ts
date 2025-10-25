import { wsDirectUrl } from "./wsUrl";

export type WSStatus = "idle" | "connecting" | "open" | "closed" | "error";

export function createWS(
    onJSON: (msg: any) => void,
    onStatus: (s: WSStatus) => void
) {
    let ws: WebSocket | null = new WebSocket(wsDirectUrl("/ws/stream", 8001));

    const queue: (ArrayBuffer | string)[] = [];

    const flush = () => {
        if (!ws || ws.readyState !== WebSocket.OPEN) return;
        while (queue.length) ws.send(queue.shift()!);
    };

    const connect = () => {
        onStatus("connecting");
        ws = new WebSocket(wsDirectUrl("/ws/stream", 8001));
        ws.binaryType = "arraybuffer";

        ws.onopen = () => { onStatus("open"); flush(); };
        ws.onmessage = (ev) => {
            if (typeof ev.data === "string") {
                console.log("onmessage", ev.data);
                try { onJSON(JSON.parse(ev.data)); } catch { }
            }
        };
        ws.onerror = () => onStatus("error");
        ws.onclose = () => onStatus("closed");
    };

    connect();

    return {
        sendBytes: (buf: ArrayBuffer) => {
            if (ws && ws.readyState === WebSocket.OPEN) ws.send(buf);
            else queue.push(buf);
        },
        sendJSON: (obj: any) => {
            const s = JSON.stringify(obj);
            if (ws && ws.readyState === WebSocket.OPEN) ws.send(s);
            else queue.push(s);
        },
        close: () => ws?.close(),
    };
}
