"use client";

import { useMemo, useState } from "react";

import MallangAvatar from "@/components/MallangAvatar";
import Screen from "@/components/Screen";
import TabBar from "@/components/TabBar";
import { GOAL_MAP_SIZE, layoutGoalMap } from "@/lib/goalLayout";
import { useGoals, useWeeklyStats } from "@/lib/hooks";

export default function RecordsPage() {
  const { goals } = useGoals();
  const { stats } = useWeeklyStats();
  const [focusId, setFocusId] = useState<string | null>(null);

  const nodes = useMemo(() => layoutGoalMap(goals, focusId), [goals, focusId]);

  const retro = useMemo(() => {
    if (!stats || stats.days.every((day) => day.totalCount === 0)) return null;
    const past = stats.days.filter((day) => new Date(day.date) <= new Date());
    if (past.length === 0) return null;
    const best = past.reduce((a, b) => (b.doneCount > a.doneCount ? b : a));
    const worst = past.reduce((a, b) =>
      b.totalCount > 0 && b.doneCount / b.totalCount < (a.totalCount ? a.doneCount / a.totalCount : 1) ? b : a,
    );
    if (best.label === worst.label || best.doneCount === 0) {
      return "이번 주는 아직 기록이 적어. 하나씩 차근차근 해보자.";
    }
    return `${best.label}요일에 제일 많이 했어. 대신 ${worst.label}요일은 거의 못 했지. 다음 주엔 ${worst.label}요일을 좀 가볍게 잡아볼까?`;
  }, [stats]);

  return (
    <Screen>
      <div className="no-scrollbar" style={{ flex: 1, minHeight: 0, overflowY: "auto", display: "flex", flexDirection: "column" }}>
        <div style={{ padding: "28px 20px 2px", flex: "none" }}>
          <div style={{ font: "400 12px 'Pretendard'", color: "rgba(89,55,42,.45)" }}>목표를 향한 지도</div>
          <div style={{ font: "400 14px/1.5 'Gowun Dodum'", color: "#59372A", marginTop: 4 }}>
            여유롭게 사는 삶으로, 이렇게 가까워지고 있어요
          </div>
        </div>

        <div style={{ position: "relative", height: GOAL_MAP_SIZE.height, width: GOAL_MAP_SIZE.width, margin: "0 auto", flex: "none" }}>
          {nodes.map((node) => {
            const on = focusId === node.goal.id;
            return (
              <div
                key={node.goal.id}
                onClick={node.goal.isVision ? undefined : () => setFocusId((current) => (current === node.goal.id ? null : node.goal.id))}
                style={{
                  position: "absolute",
                  left: node.left,
                  top: node.top,
                  width: node.size,
                  height: node.size,
                  borderRadius: node.size / 2,
                  background: node.bg,
                  border: node.border ?? "none",
                  boxSizing: "border-box",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  transition: "all .3s ease",
                  cursor: node.goal.isVision ? "default" : "pointer",
                  zIndex: on ? 5 : 2,
                }}
              >
                <div style={{ textAlign: "center", padding: "0 10px" }}>
                  <div style={{ font: `500 ${node.goal.isVision ? 15 : on ? 14 : 13}px/1.4 'Pretendard'`, color: node.fg, whiteSpace: node.goal.isVision ? "pre-line" : "nowrap" }}>
                    {node.goal.name}
                  </div>
                  {on &&
                    node.goal.items.map((item) => (
                      <div key={item} style={{ font: "400 10.5px/1.5 'Pretendard'", color: node.fg, opacity: 0.8, marginTop: 3, textAlign: "center" }}>
                        {item}
                      </div>
                    ))}
                </div>
              </div>
            );
          })}
        </div>

        <div style={{ padding: "10px 20px 12px", flex: "none" }}>
          <div style={{ font: "400 12px 'Pretendard'", color: "rgba(89,55,42,.45)" }}>
            {stats ? `${stats.days[0]?.date.slice(5).replace("-", "/")} – ${stats.days[6]?.date.slice(5).replace("-", "/")}` : ""}
          </div>
          <div style={{ font: "600 26px/1.2 'Pretendard'", color: "#59372A", marginTop: 3 }}>이번 주 기록</div>
        </div>

        <div style={{ flex: "none", padding: "0 20px 24px", display: "flex", flexDirection: "column", gap: 14 }}>
          <div style={{ background: "#FAF4E4", borderRadius: 20, padding: 18, flex: "none" }}>
            <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
              <div style={{ font: "600 38px/1 'Pretendard'", color: "#59372A" }}>{stats?.doneCount ?? 0}</div>
              <div style={{ font: "400 13px 'Pretendard'", color: "rgba(89,55,42,.45)" }}>/ {stats?.totalCount ?? 0}개 완료</div>
            </div>
            <div style={{ display: "flex", gap: 5, marginTop: 16, alignItems: "flex-end", height: 56 }}>
              {(stats?.days ?? []).map((day) => {
                const isFuture = new Date(day.date) > new Date();
                const ratio = day.totalCount ? day.doneCount / day.totalCount : 0;
                const height = isFuture ? 10 : day.totalCount ? Math.max(15, Math.round(ratio * 100)) : 6;
                const background = isFuture
                  ? "rgba(89,55,42,.12)"
                  : ratio === 1 && day.totalCount
                    ? "#C9DBF2"
                    : ratio > 0
                      ? "rgba(201,219,242,.55)"
                      : "rgba(89,55,42,.12)";
                return (
                  <div key={day.date} style={{ flex: 1, height: `${height}%`, background, borderRadius: 5 }} />
                );
              })}
            </div>
            <div style={{ display: "flex", gap: 5, marginTop: 8 }}>
              {(stats?.days ?? []).map((day) => (
                <div key={day.date} style={{ flex: 1, textAlign: "center", font: "400 10px 'Pretendard'", color: "rgba(89,55,42,.4)" }}>
                  {day.label}
                </div>
              ))}
            </div>
          </div>

          {retro && (
            <div style={{ display: "flex", gap: 12, alignItems: "flex-start", background: "#FFFFFF", border: "1px solid rgba(89,55,42,.1)", borderRadius: 20, padding: 16 }}>
              <MallangAvatar size={40} />
              <div style={{ font: "400 14.5px/1.65 'Gowun Dodum'", color: "#59372A" }}>{retro}</div>
            </div>
          )}

          {stats && stats.postponed.length > 0 && (
            <div style={{ background: "#FAF4E4", borderRadius: 20, padding: "16px 18px" }}>
              <div style={{ font: "600 11px 'Pretendard'", color: "rgba(89,55,42,.45)", letterSpacing: ".06em", marginBottom: 12 }}>미룬 할 일</div>
              {stats.postponed.map((task, index) => (
                <div key={task.id}>
                  {index > 0 && <div style={{ height: 1, background: "rgba(89,55,42,.09)" }} />}
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "11px 0" }}>
                    <div style={{ font: "400 14.5px 'Pretendard'", color: "#59372A" }}>{task.title}</div>
                    <div style={{ font: "400 12px 'Pretendard'", color: task.snoozedCount >= 3 ? "#8C1822" : "rgba(89,55,42,.45)", flex: "none" }}>
                      {task.snoozedCount}번 미룸
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
      <TabBar />
    </Screen>
  );
}
