"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import Mallang3D from "@/components/Mallang3D";
import Screen from "@/components/Screen";
import TabBar from "@/components/TabBar";
import { sendMessage } from "@/lib/api";
import { greetingLabel, isSameDay } from "@/lib/format";
import { useMallangProfile, useTasks } from "@/lib/hooks";

export default function HomePage() {
  const router = useRouter();
  const { profile } = useMallangProfile();
  const { tasks } = useTasks();
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");

  const todayTaskCount = useMemo(() => {
    const now = new Date();
    return tasks.filter((task) => {
      if (task.done) return false;
      if (!task.dueAt) return true;
      return isSameDay(new Date(task.dueAt), now);
    }).length;
  }, [tasks]);

  async function handleSend(text: string) {
    const trimmed = text.trim();
    if (!trimmed || sending) return;
    setSending(true);
    setError("");
    try {
      await sendMessage(trimmed);
      router.push("/chat");
    } catch {
      setError("말랑이한테 전달하지 못했어. 다시 시도해 줘.");
    } finally {
      setSending(false);
    }
  }

  return (
    <Screen background="linear-gradient(180deg,#FFFFFF,#FAF6EC)">
      <div style={{ padding: "28px 24px 0", flex: "none" }}>
        <div style={{ font: "400 12px 'Pretendard'", color: "rgba(89,55,42,.45)" }}>
          {greetingLabel()}
        </div>
      </div>

      <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", minHeight: 0 }}>
        <div style={{ position: "relative", width: 300, height: 300 }}>
          <div
            style={{
              position: "absolute",
              top: 6,
              right: -8,
              background: "#FFFFFF",
              border: "1px solid rgba(89,55,42,.1)",
              borderRadius: "18px 18px 18px 5px",
              padding: "11px 14px",
              maxWidth: 196,
              boxShadow: "0 3px 10px rgba(89,55,42,.1)",
              font: "400 14px/1.5 'Gowun Dodum'",
              color: "#59372A",
              zIndex: 2,
            }}
          >
            잘 잤어? 오늘은 할 일 {todayTaskCount}개야
          </div>
          <Mallang3D
            size={300}
            fieldOfView={34}
            interactive
            color={profile?.color ?? "original"}
            style={{ margin: "0 auto" }}
          />
        </div>
      </div>

      <div
        style={{
          background: "rgba(255,255,255,.86)",
          backdropFilter: "blur(18px)",
          borderRadius: "26px 26px 0 0",
          padding: "12px 18px 16px",
          boxShadow: "0 -6px 24px rgba(89,55,42,.08)",
          flex: "none",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
          <div style={{ width: 38, height: 4, borderRadius: 2, background: "rgba(89,55,42,.16)" }} />
          <button
            type="button"
            onClick={() => router.push("/chat")}
            style={{
              font: "500 11.5px 'Pretendard'",
              color: "rgba(89,55,42,.5)",
              whiteSpace: "nowrap",
              background: "none",
              border: "none",
              cursor: "pointer",
            }}
          >
            대화 전체 보기 ↑
          </button>
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 12 }}>
          {[
            { label: "오늘 뭐부터 해?", bg: "#F2E9BB" },
            { label: "이번 주 한가한 날", bg: "#C9DBF2" },
          ].map((chip) => (
            <button
              key={chip.label}
              type="button"
              onClick={() => handleSend(chip.label)}
              disabled={sending}
              style={{
                flex: "none",
                whiteSpace: "nowrap",
                font: "400 13px 'Pretendard'",
                color: "#59372A",
                background: chip.bg,
                padding: "9px 14px",
                borderRadius: 14,
                border: "none",
                cursor: "pointer",
              }}
            >
              {chip.label}
            </button>
          ))}
        </div>
        {error && (
          <div style={{ font: "400 11.5px 'Pretendard'", color: "#8C1822", marginBottom: 8 }}>
            {error}
          </div>
        )}
        <form
          style={{ display: "flex", alignItems: "center", gap: 12 }}
          onSubmit={(event) => {
            event.preventDefault();
            handleSend(input).then(() => setInput(""));
          }}
        >
          <input
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder="말랑이한테 말하기"
            disabled={sending}
            style={{
              flex: 1,
              minWidth: 0,
              background: "#FAF4E4",
              borderRadius: 24,
              padding: "14px 18px",
              font: "400 14.5px 'Pretendard'",
              color: "#59372A",
              border: "none",
              outline: "none",
            }}
          />
          <button
            type="submit"
            aria-label="말랑이에게 보내기"
            disabled={sending}
            style={{
              width: 50,
              height: 50,
              borderRadius: "50%",
              background: "#8C1822",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flex: "none",
              boxShadow: "0 4px 14px rgba(140,24,34,.3)",
              border: "none",
              cursor: "pointer",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 3 }}>
              <div style={{ width: 3, height: 8, borderRadius: 2, background: "#F5EFD3" }} />
              <div style={{ width: 3, height: 14, borderRadius: 2, background: "#F5EFD3" }} />
              <div style={{ width: 3, height: 20, borderRadius: 2, background: "#F5EFD3" }} />
            </div>
          </button>
        </form>
      </div>
      <TabBar />
    </Screen>
  );
}
