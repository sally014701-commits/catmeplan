"use client";

import { useRef, useState } from "react";

export type Star = {
  id: string;
  left: number;
  top: number;
  dx: number;
  dy: number;
  rot: number;
  size: number;
  delay: number;
};

type SpringState = {
  q: number;
  v: number;
  t: number;
  t0: number;
  x0: number;
  y0: number;
  moved: number;
  dirX: number;
  dirY: number;
  px: number;
  py: number;
};

function freshSpring(): SpringState {
  return { q: 0, v: 0, t: 0, t0: 0, x0: 0, y0: 0, moved: 0, dirX: 0, dirY: 0, px: 0, py: 0 };
}

/** Press-to-squish spring physics + release star-burst, shared by every 말랑이 character view. */
export function useSquishStars(interactive: boolean) {
  const squishRef = useRef<HTMLDivElement>(null);
  const spring = useRef<SpringState>(freshSpring());
  const rafId = useRef<number | null>(null);
  const [stars, setStars] = useState<Star[]>([]);

  const tick = () => {
    const s = spring.current;
    const dt = 1 / 60;
    const k = 210;
    const c = 15;
    const acc = -k * (s.q - s.t) - c * s.v;
    s.v += acc * dt;
    s.q += s.v * dt;
    let alive = true;
    if (Math.abs(s.q - s.t) < 0.0008 && Math.abs(s.v) < 0.0008) {
      s.q = s.t;
      s.v = 0;
      alive = s.t !== 0;
    }
    if (squishRef.current) {
      squishRef.current.style.transform = `scaleY(${1 - 0.1 * s.q})`;
    }
    rafId.current = alive ? requestAnimationFrame(tick) : null;
  };

  const startLoop = () => {
    if (!rafId.current) rafId.current = requestAnimationFrame(tick);
  };

  const burst = (px: number, py: number, count: 2 | 3, swipeDeg: number | null) => {
    const now = Date.now();
    const trail = swipeDeg !== null;
    const angles = trail
      ? [swipeDeg, swipeDeg, swipeDeg]
      : count === 3
        ? [-118, -90, -62]
        : [-104, -76];
    const dists = trail ? [44, 66, 88] : count === 3 ? [58, 74, 58] : [62, 72];
    const sizes = trail ? [15, 13, 11] : count === 3 ? [13, 15, 12] : [13, 15];
    const made: Star[] = Array.from({ length: count }, (_, i) => {
      const ang = (angles[i] * Math.PI) / 180;
      const dist = dists[i];
      return {
        id: `${now}-${i}-${Math.random().toString(36).slice(2, 6)}`,
        left: px,
        top: py,
        dx: Math.cos(ang) * dist,
        dy: Math.sin(ang) * dist,
        rot: trail ? i * 40 : (i - (count - 1) / 2) * 24,
        size: sizes[i] ?? 13,
        delay: i * (trail ? 60 : 70),
      };
    });
    setStars((current) => [...current, ...made]);
    setTimeout(() => {
      const ids = new Set(made.map((m) => m.id));
      setStars((current) => current.filter((star) => !ids.has(star.id)));
    }, 900);
  };

  const handlePointerDown = (event: React.PointerEvent<HTMLDivElement>) => {
    if (!interactive) return;
    const rect = event.currentTarget.getBoundingClientRect();
    const s = spring.current;
    s.t = 1;
    s.t0 = Date.now();
    s.x0 = event.clientX;
    s.y0 = event.clientY;
    s.moved = 0;
    s.px = event.clientX - rect.left;
    s.py = event.clientY - rect.top;
    startLoop();
  };

  const handlePointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    if (!interactive) return;
    const s = spring.current;
    if (s.t !== 1 || !s.x0) return;
    s.moved = Math.max(s.moved, Math.hypot(event.clientX - s.x0, event.clientY - s.y0));
    s.dirX = event.clientX - s.x0;
    s.dirY = event.clientY - s.y0;
  };

  const handlePointerRelease = () => {
    if (!interactive) return;
    const s = spring.current;
    if (s.t === 1 && s.t0) {
      const held = Date.now() - s.t0;
      const hard = s.moved > 10 || held > 260;
      const swipeDeg = s.moved > 10 ? (Math.atan2(s.dirY, s.dirX) * 180) / Math.PI : null;
      burst(s.px, s.py, hard ? 3 : 2, swipeDeg);
    }
    s.t = 0;
    s.t0 = 0;
    s.x0 = 0;
    s.moved = 0;
    startLoop();
  };

  return { squishRef, stars, handlePointerDown, handlePointerMove, handlePointerRelease };
}
