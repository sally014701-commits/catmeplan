"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import MallangAvatar from "@/components/MallangAvatar";
import Screen from "@/components/Screen";
import TaskRow from "@/components/TaskRow";
import { confirmProjectForTask, sendMessage, toggleTaskDone, rescheduleTask } from "@/lib/api";
import { dateLabel } from "@/lib/format";
import { useConversation, useProjects, useTasks } from "@/lib/hooks";
import type { TaskDraftAssignment } from "@/lib/types";

export default function ChatPage() {
  const router = useRouter();
  const { messages, refresh: refreshConversation } = useConversation();
  const { tasks, refresh: refreshTasks, setTasks } = useTasks();
  const { projects } = useProjects();
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [drafts, setDrafts] = useState<Record<string, { suggestedName: string; reasoning: string | null }>>({});
  const [draftNames, setDraftNames] = useState<Record<string, string>>({});
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "end" });
  }, [messages.length]);

  const taskById = useMemo(() => new Map(tasks.map((task) => [task.id, task])), [tasks]);
  const projectById = useMemo(() => new Map(projects.map((project) => [project.id, project])), [projects]);

  const todayCount = tasks.filter((task) => !task.done).length;

  async function handleSend() {
    const text = input.trim();
    if (!text || sending) return;
    setInput("");
    setSending(true);
    try {
      const result = await sendMessage(text);
      refreshConversation();
      refreshTasks();
      if (result.type === "tasks_created") {
        const nextDrafts: typeof drafts = {};
        for (const item of result.items) {
          if (item.assignment.status === "needs_confirm") {
            nextDrafts[item.task.id] = {
              suggestedName: item.assignment.suggestedName,
              reasoning: item.assignment.reasoning,
            };
          }
        }
        setDrafts((current) => ({ ...current, ...nextDrafts }));
      }
    } catch {
      refreshConversation();
    } finally {
      setSending(false);
    }
  }

  async function handleToggleDone(task: { id: string; done: boolean }) {
    setTasks((current) => current.map((t) => (t.id === task.id ? { ...t, done: !t.done } : t)));
    try {
      await toggleTaskDone(task.id, !task.done);
    } catch {
      refreshTasks();
    }
  }

  async function handleConfirmProject(taskId: string) {
    const name = (draftNames[taskId] ?? drafts[taskId]?.suggestedName ?? "").trim();
    if (!name) return;
    const assignment: TaskDraftAssignment = await confirmProjectForTask(taskId, name);
    if (assignment.status === "matched") {
      setDrafts((current) => {
        const next = { ...current };
        delete next[taskId];
        return next;
      });
      refreshTasks();
    }
  }

  let lastDate = "";

  return (
    <Screen>
      <div
        style={{
          padding: "28px 18px 14px",
          display: "flex",
          alignItems: "center",
          gap: 12,
          borderBottom: "1px solid rgba(89,55,42,.1)",
          flex: "none",
        }}
      >
        <button
          type="button"
          onClick={() => router.push("/")}
          aria-label="홈으로"
          style={{ font: "400 20px 'Pretendard'", color: "rgba(89,55,42,.5)", flex: "none", background: "none", border: "none", cursor: "pointer" }}
        >
          ↓
        </button>
        <MallangAvatar size={40} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ font: "600 17px/1.2 'Pretendard'", color: "#59372A" }}>말랑이</div>
          <div style={{ font: "400 12px/1.4 'Pretendard'", color: "#8C1822", marginTop: 2, whiteSpace: "nowrap" }}>
            오늘 일정 {todayCount}개 보고 있어
          </div>
        </div>
        <div style={{ width: 34, height: 34, borderRadius: 12, background: "#FAF4E4", display: "flex", alignItems: "center", justifyContent: "center", font: "400 15px monospace", color: "rgba(89,55,42,.5)", flex: "none" }}>
          ⋯
        </div>
      </div>

      <div className="no-scrollbar" style={{ flex: 1, overflowY: "auto", padding: "20px 18px 18px", display: "flex", flexDirection: "column", gap: 13, minHeight: 0 }}>
        {messages.map((message) => {
          const createdDate = new Date(message.createdAt);
          const label = dateLabel(createdDate);
          const showDivider = label !== lastDate;
          lastDate = label;

          return (
            <div key={message.id}>
              {showDivider && (
                <div style={{ textAlign: "center", font: "400 11px 'Pretendard'", color: "rgba(89,55,42,.35)", marginBottom: 13 }}>
                  {label}
                </div>
              )}
              {message.role === "user" ? (
                <div style={{ alignSelf: "flex-end", display: "flex", justifyContent: "flex-end" }}>
                  <div style={{ maxWidth: "78%", background: "#C9DBF2", color: "#59372A", padding: "12px 15px", borderRadius: "20px 20px 6px 20px", font: "400 15px/1.5 'Pretendard'" }}>
                    {message.text}
                  </div>
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                  <div style={{ display: "flex", gap: 9, alignItems: "flex-end" }}>
                    <MallangAvatar size={28} />
                    <div style={{ maxWidth: "80%", background: "#FFFFFF", border: "1px solid rgba(89,55,42,.1)", padding: "12px 15px", borderRadius: "20px 20px 20px 6px", font: "400 15px/1.55 'Gowun Dodum'", color: "#59372A" }}>
                      {message.text}
                    </div>
                  </div>
                  {message.taskIds.length > 0 && (
                    <div style={{ marginLeft: 37, background: "#FAF4E4", borderRadius: 18, padding: 6, display: "flex", flexDirection: "column", gap: 2 }}>
                      {message.taskIds.map((taskId, index) => {
                        const task = taskById.get(taskId);
                        if (!task) return null;
                        const draft = drafts[taskId];
                        return (
                          <div key={taskId}>
                            <TaskRow
                              task={task}
                              project={task.projectId ? projectById.get(task.projectId) : undefined}
                              size={20}
                              divider={index > 0}
                              onToggleDone={handleToggleDone}
                              onReschedule={(t, dueAt) => rescheduleTask(t.id, { due_date: dueAt }).then(refreshTasks)}
                            />
                            {draft && (
                              <div style={{ padding: "8px 12px 6px", display: "flex", flexDirection: "column", gap: 6 }}>
                                <div style={{ font: "400 11.5px/1.4 'Pretendard'", color: "rgba(89,55,42,.6)" }}>
                                  이 할 일을 담을 프로젝트 이름이 필요해 — &apos;{draft.suggestedName}&apos; 어때?
                                </div>
                                <div style={{ display: "flex", gap: 6 }}>
                                  <input
                                    value={draftNames[taskId] ?? draft.suggestedName}
                                    onChange={(event) => setDraftNames((current) => ({ ...current, [taskId]: event.target.value }))}
                                    style={{ flex: 1, font: "400 12px 'Pretendard'", border: "1px solid rgba(89,55,42,.2)", borderRadius: 8, padding: "6px 10px" }}
                                  />
                                  <button
                                    type="button"
                                    onClick={() => handleConfirmProject(taskId)}
                                    style={{ font: "500 12px 'Pretendard'", color: "#F5EFD3", background: "#8C1822", padding: "7px 13px", borderRadius: 9, border: "none", cursor: "pointer" }}
                                  >
                                    확정
                                  </button>
                                </div>
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
        <div ref={bottomRef} />
      </div>

      <form
        onSubmit={(event) => {
          event.preventDefault();
          handleSend();
        }}
        style={{ padding: "12px 16px 34px", display: "flex", alignItems: "center", gap: 10, borderTop: "1px solid rgba(89,55,42,.1)", flex: "none" }}
      >
        <input
          value={input}
          onChange={(event) => setInput(event.target.value)}
          disabled={sending}
          placeholder="말하듯 입력해 보세요"
          style={{ flex: 1, minWidth: 0, background: "#FAF4E4", borderRadius: 22, padding: "13px 16px", font: "400 14.5px 'Pretendard'", color: "#59372A", border: "none", outline: "none" }}
        />
        <button
          type="submit"
          disabled={sending}
          aria-label="보내기"
          style={{ width: 48, height: 48, borderRadius: "50%", background: "#8C1822", display: "flex", alignItems: "center", justifyContent: "center", flex: "none", border: "none", cursor: "pointer" }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 3 }}>
            <div style={{ width: 3, height: 8, borderRadius: 2, background: "#F5EFD3" }} />
            <div style={{ width: 3, height: 14, borderRadius: 2, background: "#F5EFD3" }} />
            <div style={{ width: 3, height: 20, borderRadius: 2, background: "#F5EFD3" }} />
          </div>
        </button>
      </form>
    </Screen>
  );
}
