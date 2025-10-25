export async function startMicStream(onChunk: (buf: ArrayBuffer) => void) {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const ctx = new (window.AudioContext || (window as any).webkitAudioContext)({ sampleRate: 16000 });

    // Load the worklet module (served by Vite from /src)
    await ctx.audioWorklet.addModule('/src/worklets/pcm16-worklet.js');

    const source = ctx.createMediaStreamSource(stream);
    const node = new (window as any).AudioWorkletNode(ctx, 'pcm16-worklet');

    // Receive PCM16 buffers from the worklet thread
    node.port.onmessage = (e: MessageEvent<ArrayBuffer>) => {
        onChunk(e.data);
    };

    // Don’t route to speakers to avoid feedback; connect to a silent Gain
    const mute = ctx.createGain();
    mute.gain.value = 0;
    source.connect(node).connect(mute).connect(ctx.destination);

    return () => {
        node.port.onmessage = null;
        node.disconnect();
        source.disconnect();
        mute.disconnect();
        stream.getTracks().forEach(t => t.stop());
        ctx.close();
    };
}
