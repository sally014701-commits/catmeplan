"use client";

import { useEffect, useRef, useState } from "react";

import StarBurst from "./StarBurst";
import { useSquishStars } from "@/lib/useSquishStars";

type CatElement = HTMLElement & {
  replay(): void;
  pause(): void;
  play(): void;
  finish(): void;
  loop: boolean;
};

export default function GhostCatScene({
  maxWidth = 360,
  interactive = false,
  loop = false,
  onSit,
  className,
  style,
}: {
  maxWidth?: number;
  interactive?: boolean;
  loop?: boolean;
  onSit?: () => void;
  className?: string;
  style?: React.CSSProperties;
}) {
  const hostRef = useRef<HTMLDivElement>(null);
  const petRef = useRef<CatElement | null>(null);
  const onSitRef = useRef(onSit);
  onSitRef.current = onSit;
  const [ready, setReady] = useState(false);
  const { squishRef, stars, handlePointerDown, handlePointerMove, handlePointerRelease } =
    useSquishStars(interactive);

  useEffect(() => {
    let cancelled = false;
    // @ts-expect-error -- ghost-cat.js is a plain side-effect script (no types, no exports)
    import("./ghost-cat.js").then(() => {
      if (cancelled) return;
      const element = document.createElement("ghost-cat-animation") as CatElement;
      element.toggleAttribute("loop", loop);
      const listener = () => onSitRef.current?.();
      element.addEventListener("sitcomplete", listener);
      hostRef.current?.appendChild(element);
      petRef.current = element;
      setReady(true);
    });
    return () => {
      cancelled = true;
      petRef.current?.remove();
      petRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div
      className={className}
      style={{
        position: "relative",
        width: "100%",
        maxWidth,
        cursor: interactive ? "pointer" : "default",
        touchAction: "none",
        ...style,
      }}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerRelease}
      onPointerLeave={handlePointerRelease}
    >
      <div ref={squishRef} style={{ width: "100%", transformOrigin: "50% 88%", opacity: ready ? 1 : 0 }}>
        <div ref={hostRef} style={{ width: "100%" }} />
      </div>
      <StarBurst stars={stars} />
    </div>
  );
}
