// web/src/App.tsx
import React, { useRef, useState, useEffect } from "react";
import ControlBar from "./components/ControlBar";
import { createWS, WSStatus } from "./lib/ws";
import { startMicPCM16, StopFn } from "./lib/audio";

type Transcript = { text: string; emotion?: { label: string; sentiment: number }; duration?: number };

export default function App() {
    const [status, setStatus] = useState<WSStatus>("idle");
    const [isRecording, setIsRecording] = useState(false);
    const [level, setLevel] = useState(0);
    const [partial, setPartial] = useState("");
    const [finals, setFinals] = useState<Transcript[]>([]);

    const wsRef = useRef<ReturnType<typeof createWS> | null>(null);
    const stopRef = useRef<StopFn | null>(null);
    // Tracks the cumulative finalized text so we can extract only the new delta on each final
    const finalizedPrefixRef = useRef("");

    useEffect(() => {
        const ws = createWS(
            (msg) => {
                if (msg?.type === "transcript.partial") {
                    setPartial(msg.data?.text ?? "");
                } else if (msg?.type === "transcript.final") {
                    setPartial("");
                    console.log("transcript.final", msg.data);
                    const segments: Array<{ text: string }> | undefined = msg.data?.segments;
                    const full: string = msg.data?.text ?? "";
                    const prev = finalizedPrefixRef.current;

                    // Prefer segments only when multiple segments are present and they contribute beyond the previous prefix.
                    if (Array.isArray(segments) && segments.length > 1) {
                        // Build concat to update prefix and compute deltas per segment
                        const concat = segments.map(s => s?.text ?? "").join("");

                        // Emit only the portion of each segment that extends beyond prev
                        let consumed = 0; // characters covered so far
                        for (const seg of segments) {
                            const segText = seg?.text ?? "";
                            const nextConsumed = consumed + segText.length;
                            if (nextConsumed > prev.length) {
                                const sliceStart = Math.max(0, prev.length - consumed);
                                const piece = segText.slice(sliceStart).trim();
                                if (piece) {
                                    setFinals(f => [{ text: piece, emotion: msg.data?.emotion, duration: msg.data?.duration }, ...f]);
                                }
                            }
                            consumed = nextConsumed;
                        }
                        finalizedPrefixRef.current = concat;
                    } else {
                        // Single (or missing) segment → compute delta from full text
                        let delta = full;
                        if (prev && full.startsWith(prev)) {
                            delta = full.slice(prev.length).trim();
                        }
                        finalizedPrefixRef.current = full;
                        if (delta) {
                            setFinals(f => [{ text: delta, emotion: msg.data?.emotion, duration: msg.data?.duration }, ...f]);
                        }
                    }
                } else if (msg?.type === "error") {
                    console.error("Server error:", msg.stage, msg.message);
                } else if (msg?.type === "debug") {
                    console.log("[DEBUG]", msg);
                }
            },
            setStatus
        );
        wsRef.current = ws;
        return () => ws.close();
    }, []);

    const onStart = async () => {
        const ws = wsRef.current!;
        setIsRecording(true);
        finalizedPrefixRef.current = "";
        setPartial("");
        setFinals([]);
        stopRef.current = await startMicPCM16(
            (buf) => ws.sendBytes(buf),   // PCM16 → backend
            (rms) => setLevel(rms),       // live level 0..1
            16000
        );
    };


    const onEnd = async () => {
        await stopRef.current?.();
        stopRef.current = null;
        setIsRecording(false);
        setLevel(0);
        wsRef.current?.sendJSON({ type: "end" }); // finalize on server (and Fish realtime)
    };

    const onClip = async () => {
        await wsRef.current?.sendJSON({ type: "end" });
    }

    return (
        <div style={{ fontFamily: "system-ui", padding: 20, maxWidth: 900, margin: "0 auto" }}>
            <h1 style={{ marginTop: 0 }}>PerceptionAI</h1>

            <ControlBar
                status={status}
                isRecording={isRecording}
                level={level}
                onStart={onStart}
                onStop={onClip}
                onEnd={onEnd}
            />

            <section style={{ marginTop: 16 }}>
                <h3 style={{ margin: "12px 0 6px" }}>Partial</h3>
                <div style={{ padding: 12, minHeight: 40, border: "1px dashed #d1d5db", borderRadius: 8, background: "#fff" }}>
                    {partial || <span style={{ opacity: 0.6 }}>…</span>}
                </div>

                <h3 style={{ margin: "16px 0 6px" }}>Final transcripts</h3>
                <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: 8 }}>
                    {finals.map((t, i) => (
                        <li key={i} style={{ padding: 12, border: "1px solid #e5e7eb", borderRadius: 8, background: "#fff" }}>
                            <div><strong>{t.text}</strong></div>
                            {t.emotion && (
                                <div style={{ marginTop: 4, fontSize: 13, opacity: 0.8 }}>
                                    emotion: <b>{t.emotion.label}</b> ({t.emotion.sentiment.toFixed(2)})
                                </div>
                            )}
                            <div style={{ marginTop: 4, fontSize: 13, opacity: 0.8 }}>duration: {t.duration?.toFixed(2)} seconds</div>
                        </li>
                    ))}
                    {finals.length === 0 && <li style={{ opacity: 0.6 }}>No transcripts yet.</li>}
                </ul>
            </section>
        </div>
    );
}
