"use client";

import { useMemo } from "react";
import { useRouter } from "next/navigation";

import MallangAvatar from "@/components/MallangAvatar";
import Screen from "@/components/Screen";
import { VibrationBars } from "@/components/icons";
import { snoozeTask, toggleTaskDone } from "@/lib/api";
import { formatTimeLabel } from "@/lib/format";
import { useProjects, useTasks } from "@/lib/hooks";

export default function NotificationPage() {
  const router = useRouter();
  const { tasks, refresh } = useTasks();
  const { projects } = useProjects();

  const urgent = useMemo(() => {
    const now = new Date();
    const upcoming = tasks
      .filter((task) => !task.done && task.dueAt && task.dueAt.includes("T"))
      .map((task) => ({ task, due: new Date(task.dueAt as string) }))
      .filter(({ due }) => due.getTime() - now.getTime() < 1000 * 60 * 60 * 3)
      .sort((a, b) => a.due.getTime() - b.due.getTime());
    return upcoming[0]?.task ?? null;
  }, [tasks]);

  if (!urgent) {
    return (
      <Screen>
        <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", flexDirection: "column", gap: 16, padding: 24 }}>
          <div style={{ font: "400 15px 'Pretendard'", color: "rgba(89,55,42,.6)", textAlign: "center" }}>
            지금은 놓치면 안 되는 일정이 없어.
          </div>
          <button
            type="button"
            onClick={() => router.push("/")}
            style={{ font: "500 14px 'Pretendard'", color: "#59372A", background: "#C9DBF2", padding: "10px 18px", borderRadius: 12, border: "none", cursor: "pointer" }}
          >
            홈으로
          </button>
        </div>
      </Screen>
    );
  }

  const project = urgent.projectId ? projects.find((p) => p.id === urgent.projectId) : undefined;
  const timeLabel = formatTimeLabel(urgent.dueAt);

  async function handleSnooze() {
    await snoozeTask(urgent!.id);
    refresh();
    router.push("/");
  }

  async function handleDoNow() {
    await toggleTaskDone(urgent!.id, true);
    refresh();
    router.push("/tasks");
  }

  return (
    <Screen>
      <div
        style={{
          position: "absolute",
          inset: 0,
          background: "radial-gradient(110% 42% at 50% 100%,rgba(201,219,242,.55),transparent)",
        }}
      />
      <div style={{ padding: "40px 20px 0", display: "flex", alignItems: "center", justifyContent: "center", gap: 8, flex: "none", position: "relative" }}>
        <VibrationBars />
        <div style={{ font: "600 11.5px 'Pretendard'", color: "rgba(89,55,42,.6)", letterSpacing: ".04em", whiteSpace: "nowrap" }}>
          진동 · 놓치면 안 되는 일정
        </div>
      </div>
      <div style={{ padding: "14px 20px 0", display: "flex", alignItems: "center", justifyContent: "center", gap: 9, flex: "none", position: "relative" }}>
        <MallangAvatar size={26} />
        <div style={{ font: "400 12px 'Pretendard'", color: "rgba(89,55,42,.5)", whiteSpace: "nowrap" }}>말랑이가 깨우는 중</div>
      </div>
      <div style={{ flex: 1, display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "center", gap: 26, padding: "0 26px", position: "relative" }}>
        <div style={{ alignSelf: "stretch", font: "400 24px/1.5 'Pretendard'", color: "#59372A", textAlign: "center" }}>
          {timeLabel},
          <br />
          {urgent.title}
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", justifyContent: "center" }}>
          <div style={{ flex: "none", whiteSpace: "nowrap", font: "500 12.5px 'Pretendard'", color: "#59372A", background: "#C9DBF2", padding: "8px 13px", borderRadius: 11 }}>
            {timeLabel}
          </div>
          {project && (
            <div style={{ flex: "none", whiteSpace: "nowrap", font: "500 12.5px 'Pretendard'", color: "#59372A", background: "#BFBB80", padding: "8px 13px", borderRadius: 11 }}>
              {project.name}
            </div>
          )}
          <div style={{ flex: "none", whiteSpace: "nowrap", font: "500 12.5px 'Pretendard'", color: "rgba(89,55,42,.8)", background: "rgba(89,55,42,.1)", padding: "8px 13px", borderRadius: 11 }}>
            알림 10분 전
          </div>
        </div>
        <div style={{ alignSelf: "stretch", background: "#FFFFFF", border: "1px solid rgba(89,55,42,.1)", borderRadius: 18, padding: "14px 16px", font: "400 14px/1.6 'Gowun Dodum'", color: "#59372A", textAlign: "center" }}>
          이거 미루면 오늘은 다시 시간 내기 어려워. 지금이 딱이야.
        </div>
      </div>
      <div style={{ padding: "0 24px 150px", display: "flex", gap: 12, alignItems: "center", position: "relative" }}>
        <button
          type="button"
          onClick={handleSnooze}
          style={{ flex: 1, textAlign: "center", whiteSpace: "nowrap", font: "500 15px 'Pretendard'", color: "rgba(89,55,42,.85)", background: "rgba(89,55,42,.1)", padding: "15px 0", borderRadius: 16, border: "none", cursor: "pointer" }}
        >
          30분 뒤에
        </button>
        <button
          type="button"
          onClick={handleDoNow}
          style={{ flex: 1, textAlign: "center", whiteSpace: "nowrap", font: "500 15px 'Pretendard'", color: "#59372A", background: "#C9DBF2", padding: "15px 0", borderRadius: 16, border: "none", cursor: "pointer" }}
        >
          지금 할게
        </button>
      </div>
    </Screen>
  );
}
