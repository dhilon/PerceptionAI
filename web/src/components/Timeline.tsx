import React from "react";

export default function Timeline({ frames }: { frames: { arousal: number, valence: number }[] }) {
    return (
        <div className="h-16 flex">
            {frames.map((f, i) => (
                <div key={i} style={{ width: 4, height: "100%", background: bandColor(f) }} />
            ))}
        </div>
    );
}
function bandColor(f: { arousal: number, valence: number }) {
    const r = Math.floor(255 * (f.arousal));
    const g = Math.floor(255 * (f.valence));
    const b = 120;
    return `rgb(${r},${g},${b})`;
}
