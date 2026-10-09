"use client";

import StarBurst from "./StarBurst";
import { useSquishStars } from "@/lib/useSquishStars";

export default function MallangAvatar({
  size = 64,
  interactive = false,
  className,
  style,
}: {
  size?: number;
  interactive?: boolean;
  className?: string;
  style?: React.CSSProperties;
}) {
  const { squishRef, stars, handlePointerDown, handlePointerMove, handlePointerRelease } =
    useSquishStars(interactive);

  return (
    <div
      className={className}
      style={{
        position: "relative",
        width: size,
        height: size,
        cursor: interactive ? "pointer" : "default",
        touchAction: "none",
        ...style,
      }}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerRelease}
      onPointerLeave={handlePointerRelease}
    >
      <div ref={squishRef} style={{ width: "100%", height: "100%", transformOrigin: "50% 88%" }}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src="/mallang/cat.webp"
          alt="말랑이"
          draggable={false}
          style={{ width: "100%", height: "100%", objectFit: "contain", display: "block", userSelect: "none" }}
        />
      </div>
      <StarBurst stars={stars} />
    </div>
  );
}
