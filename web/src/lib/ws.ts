export function connectWS(url: string, onMsg: (m: any) => void, onStatus: (s: string) => void) {
    let ws: WebSocket;
    let timer: any;

    const open = () => {
        onStatus("connecting");
        ws = new WebSocket(url);
        ws.binaryType = "arraybuffer";

        ws.onopen = () => onStatus("open");
        ws.onmessage = (ev) => {
            try { onMsg(JSON.parse(ev.data)); } catch { /* might be binary */ }
        };
        ws.onerror = (e) => { console.error("WS error", e); onStatus("error"); };
        ws.onclose = (ev) => {
            console.warn("WS closed", ev.code, ev.reason);
            onStatus("closed");
            timer = setTimeout(open, 1500);   // simple reconnect
        };
    };

    open();
    return { send: (d: any) => ws?.send(d), close: () => { clearTimeout(timer); ws?.close(); } };
}
