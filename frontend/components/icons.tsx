export function HomeGlyph() {
  return (
    <svg viewBox="0 0 24 24" style={{ width: 15, height: 15, display: "block" }}>
      <path
        d="M3 9.5 12 3l9 6.5V20a1 1 0 0 1-1 1h-5v-6H10v6H4a1 1 0 0 1-1-1z"
        fill="#fff"
      />
    </svg>
  );
}

export function CheckGlyph() {
  return (
    <svg viewBox="0 0 24 24" style={{ width: 15, height: 15, display: "block" }}>
      <path
        d="M5 12.5l4.5 4.5L19 7.5"
        fill="none"
        stroke="#fff"
        strokeWidth={2.6}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function StarGlyph({ fill = "#8C1822", size = 15 }: { fill?: string; size?: number }) {
  return (
    <svg viewBox="0 0 24 24" style={{ width: size, height: size, display: "block" }}>
      <path
        d="M12 3.5l2.6 5.6 6.1.7-4.5 4.2 1.2 6-5.4-3-5.4 3 1.2-6L3.3 9.8l6.1-.7z"
        fill={fill}
      />
    </svg>
  );
}

export function GearGlyph() {
  const teeth = Array.from({ length: 8 }, (_, i) => i * 45);
  return (
    <svg viewBox="0 0 24 24" style={{ width: 15, height: 15, display: "block" }}>
      <g fill="#fff">
        {teeth.map((deg) => (
          <rect
            key={deg}
            x="10.9"
            y="1.7"
            width="2.2"
            height="4.2"
            rx="1.1"
            transform={`rotate(${deg} 12 12)`}
          />
        ))}
      </g>
      <circle cx="12" cy="12" r="5.4" fill="none" stroke="#fff" strokeWidth={3.4} />
    </svg>
  );
}

export function MicBars({ color = "#F5EFD3" }: { color?: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 3 }}>
      <div style={{ width: 3, height: 8, borderRadius: 2, background: color }} />
      <div style={{ width: 3, height: 14, borderRadius: 2, background: color }} />
      <div style={{ width: 3, height: 20, borderRadius: 2, background: color }} />
    </div>
  );
}

export function VibrationBars() {
  const heights = [7, 13, 19, 13, 7];
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 3, flex: "none" }}>
      {heights.map((height, index) => (
        <div
          key={index}
          style={{
            width: 3,
            height,
            borderRadius: 2,
            background: index === 2 ? "#C9DBF2" : index === 1 || index === 3 ? "rgba(89,55,42,.45)" : "rgba(89,55,42,.25)",
          }}
        />
      ))}
    </div>
  );
}
