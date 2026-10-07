"use client";

import { useState } from "react";

import { StarGlyph } from "./icons";
import { formatDuration, formatTimeLabel } from "@/lib/format";
import type { Project, Task } from "@/lib/types";

export default function TaskRow({
  task,
  project,
  size = 21,
  onToggleDone,
  onReschedule,
  divider = false,
}: {
  task: Task;
  project?: Project | null;
  size?: number;
  onToggleDone: (task: Task) => void;
  onReschedule?: (task: Task, dueAt: string) => void;
  divider?: boolean;
}) {
  const [editingTime, setEditingTime] = useState(false);
  const textColor = task.done ? "rgba(89,55,42,.45)" : "#59372A";
  const labelColor = task.done ? "rgba(140,24,34,.5)" : "#8C1822";

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 12,
        padding: "14px 15px",
        background: task.source === "external" ? "#C9DBF2" : "transparent",
        borderTop: divider ? "1px solid rgba(89,55,42,.09)" : "none",
        marginLeft: divider ? 0 : undefined,
      }}
    >
      <button
        type="button"
        aria-label={task.done ? "완료 취소" : "완료로 표시"}
        onClick={() => onToggleDone(task)}
        style={{
          width: size,
          height: size,
          borderRadius: Math.round(size / 3),
          border: task.done ? "none" : "1.6px solid rgba(89,55,42,.25)",
          background: task.done ? "#8C1822" : "transparent",
          flex: "none",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          cursor: "pointer",
          padding: 0,
        }}
      >
        {task.done && (
          <svg viewBox="0 0 24 24" style={{ width: size * 0.62, height: size * 0.62 }}>
            <path
              d="M5 12.5l4.5 4.5L19 7.5"
              fill="none"
              stroke="#F5EFD3"
              strokeWidth={3}
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        )}
      </button>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          style={{
            font: "400 15.5px 'Pretendard'",
            color: textColor,
            whiteSpace: "nowrap",
            overflow: "hidden",
            textOverflow: "ellipsis",
            textDecoration: task.done ? "line-through" : "none",
          }}
        >
          {task.title}
        </div>
        {project && (
          <div style={{ display: "flex", alignItems: "center", gap: 4, marginTop: 3 }}>
            <StarGlyph size={9} fill={labelColor} />
            <div style={{ font: "500 10.5px 'Pretendard'", color: labelColor, whiteSpace: "nowrap" }}>
              {project.name}
              {task.durationMin ? ` · ${formatDuration(task.durationMin)}` : ""}
            </div>
          </div>
        )}
      </div>
      {onReschedule && editingTime ? (
        <input
          type="datetime-local"
          autoFocus
          defaultValue={task.dueAt ? task.dueAt.slice(0, 16) : ""}
          onBlur={(event) => {
            setEditingTime(false);
            if (event.target.value) {
              onReschedule(task, new Date(event.target.value).toISOString());
            }
          }}
          style={{ font: "400 12px 'Pretendard'", border: "1px solid rgba(89,55,42,.2)", borderRadius: 6 }}
        />
      ) : (
        <button
          type="button"
          onClick={() => onReschedule && setEditingTime(true)}
          style={{
            font: "400 13px 'Pretendard'",
            color: "rgba(89,55,42,.45)",
            flex: "none",
            background: "none",
            border: "none",
            cursor: onReschedule ? "pointer" : "default",
          }}
        >
          {formatTimeLabel(task.dueAt)}
        </button>
      )}
    </div>
  );
}
