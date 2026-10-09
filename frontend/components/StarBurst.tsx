import type { Star } from "@/lib/useSquishStars";

export default function StarBurst({ stars }: { stars: Star[] }) {
  return (
    <>
      {stars.map((star) => (
        <div
          key={star.id}
          style={{
            position: "absolute",
            left: star.left - star.size / 2,
            top: star.top - star.size / 2,
            width: star.size,
            height: star.size,
            pointerEvents: "none",
            zIndex: 6,
            ["--dx" as never]: `${star.dx}px`,
            ["--dy" as never]: `${star.dy}px`,
            ["--rot" as never]: `${star.rot}deg`,
            animation: `starPop .82s cubic-bezier(.3,1.2,.5,1) ${star.delay}ms both`,
          }}
        >
          <svg viewBox="0 0 24 24" style={{ width: "100%", height: "100%", display: "block" }}>
            <path
              d="M12 3.5l2.6 5.6 6.1.7-4.5 4.2 1.2 6-5.4-3-5.4 3 1.2-6L3.3 9.8l6.1-.7z"
              fill="#8C1822"
            />
          </svg>
        </div>
      ))}
    </>
  );
}
