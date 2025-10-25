import React, { useRef, useState } from "react";
import { startMicStream } from "../lib/audio";
import { connectWS } from "../lib/ws";

export default function ControlBar({ onEvent }: { onEvent: (m: any) => void }) {
    const wsRef = useRef<WebSocket | null>(null);
    const stopMicRef = useRef<null | (() => void)>(null);
    const [live, setLive] = useState(false);

    const start = async () => {
        wsRef.current = connectWS(`ws://${location.hostname}:8001/ws/stream`, onEvent);
        stopMicRef.current = await startMicStream((buf) => wsRef.current?.send(buf));
        setLive(true);
    };
    const stop = () => {
        wsRef.current?.send(JSON.stringify({ type: "end" }));
        stopMicRef.current?.(); wsRef.current?.close(); setLive(false);
    };

    return (
        <div className="flex gap-2">
            {!live ? <button onClick={start}>Start</button> : <button onClick={stop}>Stop</button>}
        </div>
    );
}
