import React from "react";

export default function Transcript({ lines }: { lines: { text: string, sentiment?: number, arousal?: number, valence?: number }[] }) {
    return (
        <div className="space-y-1">
            {lines.map((l, i) => (
                <div key={i} style={{ borderLeft: "4px solid", borderColor: colorFor(l), paddingLeft: 8 }}>
                    {l.text}
                </div>
            ))}
        </div>
    );
}

function colorFor(l: any) {
    if (l.label === "frustrated") return "#e74c3c";
    if (l.label === "excited") return "#27ae60";
    if (l.label === "calm") return "#2ecc71";
    return "#bdc3c7";
}
