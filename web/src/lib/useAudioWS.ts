import { useEffect, useRef, useState } from "react";

export function useAudioWS(url: string) {
    const wsRef = useRef<WebSocket | null>(null);
    const [status, setStatus] = useState<"idle" | "connecting" | "open" | "closed" | "error">("idle");
    const [level, setLevel] = useState(0);
    const [emotion, setEmotion] = useState<string | null>(null);
    const [proba, setProba] = useState<number[]>([]);

    const audioCtx = useRef<AudioContext | null>(null);
    const processor = useRef<ScriptProcessorNode | null>(null);
    const source = useRef<MediaStreamAudioSourceNode | null>(null);

    // ---- connect websocket ----
    useEffect(() => {
        wsRef.current = new WebSocket(url);
        wsRef.current.binaryType = "arraybuffer";
        setStatus("connecting");

        wsRef.current.onopen = () => setStatus("open");
        wsRef.current.onerror = () => setStatus("error");
        wsRef.current.onclose = () => setStatus("closed");

        wsRef.current.onmessage = (msg) => {
            const data = JSON.parse(msg.data);
            if (data.type === "level") setLevel(data.value);
            if (data.type === "emotion") {
                if (typeof data.emotion === "string") setEmotion(data.emotion);
                if (Array.isArray(data.proba)) setProba(data.proba as number[]);
            }
        };

        return () => wsRef.current?.close();
    }, [url]);

    // ---- start recording ----
    const start = async () => {
        audioCtx.current = new AudioContext({ sampleRate: 16000 });
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

        source.current = audioCtx.current.createMediaStreamSource(stream);
        processor.current = audioCtx.current.createScriptProcessor(4096, 1, 1);

        processor.current.onaudioprocess = (e) => {
            const input = e.inputBuffer.getChannelData(0);
            // compute simple RMS level 0..1 for the UI
            let sumSq = 0;
            for (let i = 0; i < input.length; i++) {
                const s = input[i];
                sumSq += s * s;
            }
            const rms = Math.sqrt(sumSq / input.length);
            const levelVal = Math.max(0, Math.min(1, rms));
            setLevel(levelVal);

            const pcm16 = floatToPCM16(input);

            wsRef.current?.send(pcm16);
        };

        source.current.connect(processor.current);
        processor.current.connect(audioCtx.current.destination);
    };

    // ---- stop recording ----
    const stop = () => {
        processor.current?.disconnect();
        source.current?.disconnect();
        audioCtx.current?.close();
    };

    return { status, level, emotion, proba, start, stop };
}

function floatToPCM16(float32: Float32Array) {
    const buf = new Int16Array(float32.length);
    for (let i = 0; i < float32.length; i++) {
        let s = Math.max(-1, Math.min(1, float32[i]));
        buf[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
    }
    return buf;
}
