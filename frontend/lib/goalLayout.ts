import type { Goal } from "./types";

export type GoalNode = {
  goal: Goal;
  left: number;
  top: number;
  size: number;
  bg: string;
  fg: string;
  border?: string;
};

const CONTAINER = { width: 340, height: 308 };
const VISION_SIZE = 118;
const SATELLITE_SIZES = [72, 66, 68, 62, 54, 70, 64];
const SATELLITE_SKINS = [
  { bg: "#E4E1C2", fg: "#59372A" },
  { bg: "#C9DBF2", fg: "#3B5570" },
];

function center() {
  return { x: CONTAINER.width / 2, y: CONTAINER.height / 2 };
}

export function layoutGoalMap(goals: Goal[], focusId: string | null): GoalNode[] {
  const vision = goals.find((goal) => goal.isVision);
  const satellites = goals.filter((goal) => !goal.isVision);
  const c = center();

  const base = new Map<string, { x: number; y: number; size: number }>();
  if (vision) base.set(vision.id, { x: c.x, y: c.y, size: VISION_SIZE });

  const radius = 92;
  satellites.forEach((goal, index) => {
    const angle = (-90 + index * (360 / satellites.length)) * (Math.PI / 180);
    const size = SATELLITE_SIZES[index % SATELLITE_SIZES.length];
    base.set(goal.id, {
      x: c.x + Math.cos(angle) * radius,
      y: c.y + Math.sin(angle) * radius,
      size,
    });
  });

  const positions = new Map(base);
  if (focusId && base.has(focusId)) {
    const focusBase = base.get(focusId)!;
    const focusSize = 132;
    positions.set(focusId, { x: focusBase.x, y: focusBase.y, size: focusSize });

    for (const [id, point] of base) {
      if (id === focusId) continue;
      const dx = point.x - focusBase.x;
      const dy = point.y - focusBase.y;
      const dist = Math.hypot(dx, dy) || 1;
      const push = Math.max(0, 46 - dist * 0.22);
      positions.set(id, {
        x: point.x + (dx / dist) * push,
        y: point.y + (dy / dist) * push,
        size: point.size,
      });
    }
  }

  const nodes: GoalNode[] = [];
  if (vision) {
    const point = positions.get(vision.id)!;
    nodes.push({
      goal: vision,
      left: point.x - point.size / 2,
      top: point.y - point.size / 2,
      size: point.size,
      bg: "#8C1822",
      fg: "#F5EFD3",
    });
  }
  satellites.forEach((goal, index) => {
    const point = positions.get(goal.id)!;
    const skin = goal.stalled
      ? { bg: "#FFFFFF", fg: "#8C1822", border: "2px dashed #8C1822" }
      : SATELLITE_SKINS[index % SATELLITE_SKINS.length];
    nodes.push({
      goal,
      left: point.x - point.size / 2,
      top: point.y - point.size / 2,
      size: point.size,
      bg: skin.bg,
      fg: skin.fg,
      border: "border" in skin ? skin.border : undefined,
    });
  });

  return nodes;
}

export const GOAL_MAP_SIZE = CONTAINER;
