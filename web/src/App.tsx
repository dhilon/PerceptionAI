import React, { useEffect, useRef, useState } from "react";

export default function App() {
    const [status, setStatus] = useState<"idle" | "connecting" | "open" | "closed" | "error">("idle");
    const [log, setLog] = useState<string[]>([]);
    const wsRef = useRef<WebSocket | null>(null);

    useEffect(() => {
        setStatus("connecting");
        const ws = new WebSocket(`ws://${location.hostname}:8001/ws/stream`);
        wsRef.current = ws;
        ws.onopen = () => setStatus("open");
        ws.onclose = () => setStatus("closed");
        ws.onerror = () => setStatus("error");
        ws.onmessage = (ev) => setLog((l) => [ev.data, ...l].slice(0, 20));
        return () => ws.close();
    }, []);

    return (
        <div style={{ fontFamily: "system-ui", padding: 20 }}>
            <h1>EmpathAI</h1>
            <p>WS status: <strong>{status}</strong></p>
            <h3>Last messages</h3>
            <pre style={{ whiteSpace: "pre-wrap", background: "#f6f8fa", padding: 12, borderRadius: 8, maxHeight: 240, overflow: "auto" }}>
                {log.join("\n\n")}
            </pre>
        </div>
    );
}
