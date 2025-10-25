export function connectWS(url: string, onMsg: (m: any) => void) {
    const ws = new WebSocket(url);
    ws.binaryType = "arraybuffer";
    ws.onmessage = (ev) => {
        try { onMsg(JSON.parse(ev.data)); } catch { /* ignore */ }
    };
    return ws;
}
