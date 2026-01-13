import React, { useState } from "react";
import ControlBar from "./components/ControlBar";
import { useAudioWS } from "./lib/useAudioWS";

export default function App() {

    const { status, level, emotion, proba, start, stop } = useAudioWS("ws://localhost:8001/ws/audio");
    const [isRecording, setIsRecording] = useState(false);

    return (
        <div>
            <ControlBar
                status={status}
                isRecording={isRecording}
                level={level}
                onStart={async () => { await start(); setIsRecording(true); }}
                onStop={() => { stop(); setIsRecording(false); }}
                onEnd={() => { stop(); setIsRecording(false); }}
            />

            <div style={{
                padding: 12,
                border: "1px solid #e5e7eb",
                borderRadius: 12,
                marginTop: 12,
            }}>
                <h3 style={{ margin: 0 }}>Emotion: {emotion || ""}</h3>
                <div style={{ fontSize: 12, color: "#555" }}>
                    Raw Probabilities: {JSON.stringify(proba || [])}
                </div>
            </div>
        </div>
    );
}
