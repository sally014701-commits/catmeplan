"use client";

import { useMemo, useState } from "react";

import MallangAvatar from "@/components/MallangAvatar";
import Screen from "@/components/Screen";
import TabBar from "@/components/TabBar";
import TaskRow from "@/components/TaskRow";
import { StarGlyph } from "@/components/icons";
import { rescheduleTask, toggleTaskDone } from "@/lib/api";
import { buildMonthGrid } from "@/lib/calendar";
import { dateLabel, formatDuration, formatTimeLabel, isSameDay, monthLabel } from "@/lib/format";
import { useProjects, useTasks } from "@/lib/hooks";

const WEEKDAY_HEADERS = ["일", "월", "화", "수", "목", "금", "토"];
type ViewMode = "TO DO" | "TIMELINE" | "PROJECT";

export default function TasksPage() {
  const { tasks, setTasks, refresh: refreshTasks } = useTasks();
  const { projects } = useProjects();
  const today = useMemo(() => new Date(), []);
  const [monthCursor, setMonthCursor] = useState(new Date(today.getFullYear(), today.getMonth(), 1));
  const [selectedDate, setSelectedDate] = useState(today);
  const [view, setView] = useState<ViewMode>("TO DO");
  const [menuOpen, setMenuOpen] = useState(false);

  const projectById = useMemo(() => new Map(projects.map((project) => [project.id, project])), [projects]);
  const datesWithTasks = useMemo(() => {
    const set = new Set<string>();
    for (const task of tasks) {
      if (task.dueAt) set.add(new Date(task.dueAt).toDateString());
    }
    return set;
  }, [tasks]);

  const grid = buildMonthGrid(monthCursor.getFullYear(), monthCursor.getMonth());

  const dayTasks = useMemo(
    () =>
      tasks
        .filter((task) => task.dueAt && isSameDay(new Date(task.dueAt), selectedDate))
        .sort((a, b) => (a.dueAt && b.dueAt ? a.dueAt.localeCompare(b.dueAt) : 0)),
    [tasks, selectedDate],
  );
  const morningTasks = dayTasks.filter((task) => !task.dueAt!.includes("T") || new Date(task.dueAt!).getHours() < 12);
  const afternoonTasks = dayTasks.filter((task) => task.dueAt!.includes("T") && new Date(task.dueAt!).getHours() >= 12);

  const doneCount = dayTasks.filter((task) => task.done).length;
  const comment =
    dayTasks.length === 0
      ? "이 날은 등록된 할 일이 없어."
      : `${isSameDay(selectedDate, today) ? "오늘" : "이 날"} ${dayTasks.length}개 중 ${doneCount}개 끝냈어.`;

  async function handleToggleDone(task: { id: string; done: boolean }) {
    setTasks((current) => current.map((t) => (t.id === task.id ? { ...t, done: !t.done } : t)));
    try {
      await toggleTaskDone(task.id, !task.done);
    } catch {
      refreshTasks();
    }
  }

  return (
    <Screen>
      <div style={{ padding: "28px 20px 10px", flex: "none" }}>
        <div style={{ font: "400 12.5px 'Pretendard'", color: "rgba(89,55,42,.45)" }}>{dateLabel(today)}</div>
        <div style={{ font: "600 28px/1.2 'Pretendard'", color: "#59372A", marginTop: 3 }}>할 일</div>
      </div>

      <div style={{ padding: "0 16px 10px", flex: "none" }}>
        <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", padding: "0 4px 8px" }}>
          <div style={{ font: "600 15px 'Pretendard'", color: "#59372A" }}>{monthLabel(monthCursor)}</div>
          <div style={{ display: "flex", gap: 14, font: "400 14px 'Pretendard'", color: "rgba(89,55,42,.4)" }}>
            <button
              type="button"
              onClick={() => setMonthCursor(new Date(monthCursor.getFullYear(), monthCursor.getMonth() - 1, 1))}
              style={{ background: "none", border: "none", cursor: "pointer", font: "inherit", color: "inherit" }}
            >
              ‹
            </button>
            <button
              type="button"
              onClick={() => setMonthCursor(new Date(monthCursor.getFullYear(), monthCursor.getMonth() + 1, 1))}
              style={{ background: "none", border: "none", cursor: "pointer", font: "inherit", color: "inherit" }}
            >
              ›
            </button>
          </div>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(7,1fr)" }}>
          {WEEKDAY_HEADERS.map((label) => (
            <div key={label} style={{ textAlign: "center", font: "500 10.5px 'Pretendard'", color: "rgba(89,55,42,.4)", paddingBottom: 4 }}>
              {label}
            </div>
          ))}
          {grid.map((cell, index) => {
            if (!cell) return <div key={index} style={{ height: 27 }} />;
            const isToday = isSameDay(cell.date, today);
            const isSelected = isSameDay(cell.date, selectedDate);
            const hasDot = datesWithTasks.has(cell.date.toDateString());
            return (
              <button
                key={index}
                type="button"
                onClick={() => setSelectedDate(cell.date)}
                style={{
                  height: 27,
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: 1,
                  background: "none",
                  border: "none",
                  cursor: "pointer",
                }}
              >
                {isToday ? (
                  <div
                    style={{
                      width: 26,
                      height: 28,
                      borderRadius: "50%",
                      background: "#8C1822",
                      color: "#F5EFD3",
                      font: "600 12.5px/26px 'Pretendard'",
                      textAlign: "center",
                    }}
                  >
                    {cell.day}
                  </div>
                ) : (
                  <div
                    style={{
                      font: "400 12.5px 'Pretendard'",
                      color: isSelected ? "#8C1822" : "#59372A",
                    }}
                  >
                    {cell.day}
                  </div>
                )}
                {hasDot && !isToday && <div style={{ width: 4, height: 4, borderRadius: "50%", background: "#C9DBF2" }} />}
              </button>
            );
          })}
        </div>
      </div>
      <div style={{ height: 1, background: "rgba(89,55,42,.1)", margin: "0 16px 10px", flex: "none" }} />

      <div style={{ padding: "0 20px 12px", position: "relative", flex: "none" }}>
        <button
          type="button"
          onClick={() => setMenuOpen((open) => !open)}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 8,
            cursor: "pointer",
            background: menuOpen ? "rgba(89,55,42,.12)" : "rgba(89,55,42,.06)",
            borderRadius: 12,
            padding: "9px 13px",
            border: "none",
          }}
        >
          <div style={{ font: "600 11px 'Pretendard'", color: "rgba(89,55,42,.5)", letterSpacing: ".06em", flex: "none" }}>보기</div>
          <div style={{ font: "600 13px 'Pretendard'", color: "#59372A", whiteSpace: "nowrap", flex: "none" }}>{view}</div>
          <div style={{ font: "400 9px 'Pretendard'", color: "rgba(89,55,42,.5)", flex: "none" }}>{menuOpen ? "▲" : "▼"}</div>
        </button>
        {menuOpen && (
          <div style={{ position: "absolute", top: 44, left: 20, width: 168, background: "#FFFFFF", border: "1px solid rgba(89,55,42,.12)", borderRadius: 14, overflow: "hidden", boxShadow: "0 8px 22px rgba(89,55,42,.14)", zIndex: 5 }}>
            {(["TO DO", "TIMELINE", "PROJECT"] as ViewMode[]).map((option, index) => {
              const on = view === option;
              return (
                <button
                  key={option}
                  type="button"
                  onClick={() => {
                    setView(option);
                    setMenuOpen(false);
                  }}
                  style={{
                    width: "100%",
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    padding: "11px 13px",
                    cursor: "pointer",
                    background: on ? "rgba(89,55,42,.1)" : "transparent",
                    borderTop: index === 0 ? "none" : "1px solid rgba(89,55,42,.08)",
                    border: "none",
                    textAlign: "left",
                  }}
                >
                  <div style={{ width: 14, flex: "none", font: "600 12px 'Pretendard'", color: "#59372A" }}>{on ? "✓" : ""}</div>
                  <div style={{ flex: 1, minWidth: 0, whiteSpace: "nowrap", font: `${on ? 600 : 400} 13.5px 'Pretendard'`, color: on ? "#59372A" : "rgba(89,55,42,.7)" }}>
                    {option}
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </div>

      {view === "TO DO" && (
        <div className="no-scrollbar" style={{ flex: 1, minHeight: 0, padding: "4px 16px 14px", display: "flex", flexDirection: "column", gap: 10, overflowY: "auto" }}>
          <div style={{ display: "flex", gap: 11, alignItems: "center", background: "#FFFFFF", border: "1px solid rgba(89,55,42,.1)", borderRadius: 16, padding: "12px 14px", flex: "none" }}>
            <MallangAvatar size={30} />
            <div style={{ font: "400 13.5px/1.45 'Gowun Dodum'", color: "#59372A" }}>{comment}</div>
          </div>
          {morningTasks.length > 0 && (
            <div>
              <div style={{ font: "600 12px 'Pretendard'", color: "rgba(89,55,42,.45)", letterSpacing: ".06em", margin: "0 4px 8px" }}>오전</div>
              <div style={{ background: "#FAF4E4", borderRadius: 18, overflow: "hidden" }}>
                {morningTasks.map((task, index) => (
                  <TaskRow
                    key={task.id}
                    task={task}
                    project={task.projectId ? projectById.get(task.projectId) : undefined}
                    divider={index > 0}
                    onToggleDone={handleToggleDone}
                    onReschedule={(t, dueAt) => rescheduleTask(t.id, { due_date: dueAt }).then(refreshTasks)}
                  />
                ))}
              </div>
            </div>
          )}
          {afternoonTasks.length > 0 && (
            <div>
              <div style={{ font: "600 12px 'Pretendard'", color: "rgba(89,55,42,.45)", letterSpacing: ".06em", margin: "0 4px 8px" }}>오후</div>
              <div style={{ borderRadius: 18, overflow: "hidden" }}>
                {afternoonTasks.map((task, index) => (
                  <TaskRow
                    key={task.id}
                    task={task}
                    project={task.projectId ? projectById.get(task.projectId) : undefined}
                    divider={index > 0}
                    onToggleDone={handleToggleDone}
                    onReschedule={(t, dueAt) => rescheduleTask(t.id, { due_date: dueAt }).then(refreshTasks)}
                  />
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {view === "TIMELINE" && (
        <div className="no-scrollbar" style={{ flex: 1, minHeight: 0, padding: "4px 20px 14px", overflowY: "auto", position: "relative" }}>
          <div style={{ position: "absolute", left: 56, top: 0, bottom: 0, width: 1, background: "rgba(89,55,42,.14)" }} />
          {dayTasks.length === 0 && (
            <div style={{ paddingLeft: 44, font: "400 13.5px 'Gowun Dodum'", color: "rgba(89,55,42,.5)" }}>비어 있음 — 오늘은 여유로운 날이야.</div>
          )}
          {dayTasks.map((task) => (
            <div key={task.id} style={{ display: "flex", gap: 14, paddingBottom: 14 }}>
              <div style={{ width: 30, flex: "none", font: "400 11px 'Pretendard'", color: "rgba(89,55,42,.45)", paddingTop: 12 }}>
                {formatTimeLabel(task.dueAt)}
              </div>
              <div
                style={{
                  flex: 1,
                  minWidth: 0,
                  background: task.source === "external" ? "#C9DBF2" : "#FAF4E4",
                  borderRadius: 14,
                  padding: "13px 15px",
                }}
              >
                <div
                  style={{
                    font: "500 14.5px 'Pretendard'",
                    color: "#59372A",
                    textDecoration: task.done ? "line-through" : "none",
                  }}
                >
                  {task.title}
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 4, marginTop: 3 }}>
                  <StarGlyph size={9} />
                  <div style={{ font: "500 11px 'Pretendard'", color: "#8C1822", whiteSpace: "nowrap" }}>
                    {task.source === "external" ? "외부 일정" : task.projectId ? projectById.get(task.projectId)?.name : "개인"}
                    {task.durationMin ? ` · ${formatDuration(task.durationMin)}` : ""}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {view === "PROJECT" && (
        <div className="no-scrollbar" style={{ flex: 1, minHeight: 0, padding: "2px 16px 14px", display: "flex", flexDirection: "column", gap: 10, overflowY: "auto" }}>
          {projects.map((project) => {
            const projectTasks = tasks.filter((task) => task.projectId === project.id);
            const progress = project.totalCount ? Math.round((project.doneCount / project.totalCount) * 100) : 0;
            return (
              <div key={project.id} style={{ background: "#FAF4E4", borderRadius: 18, padding: "14px 15px", flex: "none" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
                  <StarGlyph size={11} />
                  <div style={{ flex: 1, minWidth: 0, font: "600 14.5px 'Pretendard'", color: "#59372A", whiteSpace: "nowrap" }}>{project.name}</div>
                  <div style={{ font: "400 11.5px 'Pretendard'", color: "rgba(89,55,42,.45)", flex: "none" }}>
                    {project.doneCount}/{project.totalCount}
                  </div>
                </div>
                <div style={{ height: 4, borderRadius: 2, background: "rgba(89,55,42,.1)", margin: "9px 0 11px" }}>
                  <div style={{ width: `${progress}%`, height: "100%", borderRadius: 2, background: "#8C1822" }} />
                </div>
                {projectTasks.map((task) => (
                  <div key={task.id} style={{ display: "flex", alignItems: "center", gap: 10, padding: "9px 0 0" }}>
                    <button
                      type="button"
                      onClick={() => handleToggleDone(task)}
                      style={{
                        width: 18,
                        height: 18,
                        borderRadius: 6,
                        border: task.done ? "none" : "1.6px solid rgba(89,55,42,.25)",
                        background: task.done ? "#8C1822" : "transparent",
                        flex: "none",
                        cursor: "pointer",
                        padding: 0,
                      }}
                    />
                    <div
                      style={{
                        flex: 1,
                        minWidth: 0,
                        font: "400 14px 'Pretendard'",
                        color: task.done ? "rgba(89,55,42,.45)" : "#59372A",
                        whiteSpace: "nowrap",
                        textDecoration: task.done ? "line-through" : "none",
                      }}
                    >
                      {task.title}
                    </div>
                  </div>
                ))}
              </div>
            );
          })}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 6,
              border: "1.5px dashed rgba(89,55,42,.22)",
              borderRadius: 16,
              padding: "12px 0",
              flex: "none",
              font: "500 13px 'Pretendard'",
              color: "rgba(89,55,42,.45)",
            }}
          >
            ＋ 프로젝트 추가
          </div>
        </div>
      )}

      <TabBar />
    </Screen>
  );
}
