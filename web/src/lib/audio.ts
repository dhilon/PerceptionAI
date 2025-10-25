// web/src/lib/audio.ts
export type StopFn = () => Promise<void>;

/**
 * Starts mic capture, streams PCM16 via onChunk, and reports live level via onLevel.
 * - 16 kHz mono
 * - echo cancellation, noise suppression, AGC on
 * - graph kept alive by muted gain → destination (no feedback)
 */
export async function startMicPCM16(
    onChunk: (buf: ArrayBuffer) => void,
    onLevel?: (rms01: number) => void,
    targetSampleRate = 16000,
    deviceId?: string
): Promise<StopFn> {
    const constraints: MediaStreamConstraints = {
        audio: deviceId
            ? { deviceId: { exact: deviceId }, channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true }
            : { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true }
    };

    const stream = await navigator.mediaDevices.getUserMedia(constraints);

    const AudioCtx = (window.AudioContext || (window as any).webkitAudioContext) as typeof AudioContext;
    const ctx = new AudioCtx({ sampleRate: targetSampleRate });

    // ✅ Vite-safe module URL
    await ctx.audioWorklet.addModule(new URL("../worklets/pcm16-worklet.js", import.meta.url));

    const source = ctx.createMediaStreamSource(stream);

    // Worklet for PCM16 streaming
    const node = new (window as any).AudioWorkletNode(ctx, "pcm16-worklet");
    node.port.onmessage = (e: MessageEvent<ArrayBuffer>) => onChunk(e.data);

    // Keep graph alive without feedback
    const mute = ctx.createGain();
    mute.gain.value = 0;
    source.connect(node).connect(mute).connect(ctx.destination);

    // ✅ Level meter via AnalyserNode (independent of chunk flow)
    let raf: number | null = null;
    let analyser: AnalyserNode | null = null;

    if (onLevel) {
        analyser = ctx.createAnalyser();
        analyser.fftSize = 1024;
        const buf = new Uint8Array(analyser.fftSize);
        source.connect(analyser);

        const tick = () => {
            if (!analyser) return;
            analyser.getByteTimeDomainData(buf);
            // RMS of 8-bit time-domain signal (centered at 128)
            let sum = 0;
            for (let i = 0; i < buf.length; i++) {
                const v = (buf[i] - 128) / 128; // -1..1
                sum += v * v;
            }
            const rms = Math.sqrt(sum / buf.length); // 0..~1
            onLevel(rms);
            raf = requestAnimationFrame(tick);
        };
        raf = requestAnimationFrame(tick);
    }

    // iOS/Safari occasionally needs an explicit resume after gesture
    try { await ctx.resume(); } catch { }

    return async () => {
        if (raf) cancelAnimationFrame(raf);
        node.port.onmessage = null;
        analyser && source.disconnect(analyser);
        node.disconnect();
        mute.disconnect();
        source.disconnect();
        stream.getTracks().forEach(t => t.stop());
        await ctx.close();
    };
}
