import React, { useEffect, useMemo, useRef, useState } from "react";
import { useAudioWS } from "../lib/useAudioWS";

type Props = {
    status: ReturnType<typeof useAudioWS>["status"];
    isRecording: boolean;
    level?: number; // 0..1
    onStart: () => void;
    onStop: () => void;
    onReset?: () => void;
    onEnd?: () => void;
};

const pill: Record<ReturnType<typeof useAudioWS>["status"], string> = {
    idle: "#9CA3AF", connecting: "#F59E0B", open: "#10B981", closed: "#6B7280", error: "#EF4444",
};

export default function ControlBar({ status, isRecording, level = 0, onStart, onStop, onReset, onEnd }: Props) {
    const [elapsed, setElapsed] = useState(0);
    const rafRef = useRef<number | null>(null);
    const startRef = useRef<number | null>(null);
    const baseElapsedRef = useRef(0); // accumulate elapsed across pauses

    useEffect(() => {
        if (rafRef.current) { cancelAnimationFrame(rafRef.current); rafRef.current = null; }

        if (isRecording) {
            // resume from previous elapsed instead of resetting timer
            startRef.current = performance.now() - baseElapsedRef.current;
            const tick = () => {
                if (startRef.current != null) {
                    setElapsed(performance.now() - startRef.current);
                    rafRef.current = requestAnimationFrame(tick);
                }
            };
            rafRef.current = requestAnimationFrame(tick);
        } else {
            // store elapsed so next start resumes
            baseElapsedRef.current = elapsed;
            startRef.current = null;
        }

        return () => {
            if (rafRef.current) { cancelAnimationFrame(rafRef.current); rafRef.current = null; }
        };
    }, [isRecording]);

    const timeStr = useMemo(() => {
        const s = Math.max(0, Math.floor(elapsed / 1000));
        const mm = String(Math.floor(s / 60)).padStart(2, "0");
        const ss = String(s % 60).padStart(2, "0");
        return `${mm}:${ss}`;
    }, [elapsed]);

    const lvl = Math.max(0, Math.min(1, level));

    return (
        <div style={S.wrap}>
            <div style={S.left}>
                <span style={{ ...S.pill, background: pill[status] }}>{status.toUpperCase()}</span>
                <div style={S.levelWrap}><div style={{ ...S.levelFill, transform: `scaleX(${lvl})` }} /></div>
                <span style={S.timer}>{timeStr}</span>
            </div>

            <div style={S.right}>
                <button onClick={onStart} disabled={isRecording || status === "connecting"} style={{ ...S.btn, ...S.primary }}>
                    🎙️ Record
                </button>
                <button onClick={onEnd} disabled={!onEnd} style={{ ...S.btn, ...S.warning }}>
                    ⏸️ Pause Conversation
                </button>
                <button onClick={onStop} disabled={!isRecording} style={{ ...S.btn, ...S.danger }}>
                    🔪 Clip Script
                </button>

                {onReset && <button onClick={onReset} style={S.btn}>↺ Reset</button>}
            </div>
        </div>
    );
}

const S: Record<string, React.CSSProperties> = {
    wrap: { display: "grid", gridTemplateColumns: "1fr auto", alignItems: "center", gap: 12, padding: 12, border: "1px solid #e5e7eb", borderRadius: 12, background: "#fff" },
    left: { display: "flex", alignItems: "center", gap: 10 },
    right: { display: "flex", justifyContent: "flex-end", gap: 8 },
    pill: { color: "#fff", fontWeight: 700, fontSize: 12, padding: "4px 10px", borderRadius: 999, letterSpacing: 0.5 },
    levelWrap: { position: "relative", width: 200, height: 10, borderRadius: 6, background: "#f3f4f6", overflow: "hidden", transform: "translateZ(0)" },
    levelFill: { position: "absolute", inset: 0, transformOrigin: "0% 50%", background: "linear-gradient(90deg, #34d399, #22c55e 40%, #f59e0b 75%, #ef4444)" },
    timer: { fontVariantNumeric: "tabular-nums", color: "#374151" },
    btn: { fontFamily: "inherit", fontSize: 14, borderRadius: 10, padding: "8px 12px", border: "1px solid #e5e7eb", background: "#fff", cursor: "pointer" },
    primary: { background: "#111827", color: "#fff", borderColor: "#111827" },
    danger: { background: "#ef4444", color: "#fff", borderColor: "#ef4444" },
    warning: { background: "#f59e0b", color: "#fff", borderColor: "#f59e0b" },
};
