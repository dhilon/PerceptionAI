export async function startMicStream(onChunk: (buf: ArrayBuffer) => void) {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const ctx = new AudioContext({ sampleRate: 16000 }); // let browser resample
    const src = ctx.createMediaStreamSource(stream);
    const processor = ctx.createScriptProcessor(4096, 1, 1);
    src.connect(processor);
    processor.connect(ctx.destination);

    processor.onaudioprocess = (e) => {
        const data = e.inputBuffer.getChannelData(0);
        // float32 -> PCM16
        const pcm16 = new Int16Array(data.length);
        for (let i = 0; i < data.length; i++) {
            let s = Math.max(-1, Math.min(1, data[i]));
            pcm16[i] = s < 0 ? s * 0x8001 : s * 0x7fff;
        }
        onChunk(pcm16.buffer);
    };

    return () => {
        processor.disconnect(); src.disconnect();
        stream.getTracks().forEach(t => t.stop());
        ctx.close();
    };
}
