// Converts Float32 audio frames to Int16 PCM and sends to main thread.
class PCM16Worklet extends AudioWorkletProcessor {
    process(inputs) {
        const input = inputs[0];
        if (!input || !input[0]) return true;

        const f32 = input[0];
        const pcm16 = new Int16Array(f32.length);
        for (let i = 0; i < f32.length; i++) {
            let s = Math.max(-1, Math.min(1, f32[i]));
            pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
        }
        // post zero-copy to the page
        this.port.postMessage(pcm16.buffer, [pcm16.buffer]);
        return true; // keep alive
    }
}

registerProcessor('pcm16-worklet', PCM16Worklet);
