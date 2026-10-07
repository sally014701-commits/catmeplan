"use client";

import MallangAvatar from "@/components/MallangAvatar";
import Screen from "@/components/Screen";
import TabBar from "@/components/TabBar";
import { useMallangProfile } from "@/lib/hooks";

export default function SettingsPage() {
  const { profile } = useMallangProfile();

  return (
    <Screen>
      <div style={{ padding: "28px 20px 2px", font: "600 26px 'Pretendard'", color: "#59372A", flex: "none" }}>말랑이 꾸미기</div>
      <div style={{ padding: "0 20px 14px", font: "400 13px 'Pretendard'", color: "rgba(89,55,42,.45)", flex: "none" }}>
        같이 지낸 지 {profile?.daysTogether ?? 0}일
      </div>
      <div style={{ margin: "0 20px", height: 250, display: "flex", alignItems: "center", justifyContent: "center", position: "relative", flex: "none" }}>
        <MallangAvatar size={250} interactive />
      </div>
      <div style={{ flex: 1, padding: "18px 20px 0", display: "flex", flexDirection: "column", gap: 16, overflow: "hidden" }}>
        <div>
          <div style={{ font: "600 12px 'Pretendard'", color: "rgba(89,55,42,.45)", letterSpacing: ".06em", marginBottom: 10 }}>옷 · 소품</div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 11 }}>
            {["후드", "안경", "모자"].map((label) => (
              <div
                key={label}
                style={{
                  aspectRatio: "1",
                  borderRadius: 16,
                  background: "#FAF4E4",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  font: "400 9px ui-monospace, monospace",
                  color: "rgba(89,55,42,.4)",
                }}
              >
                {label}
              </div>
            ))}
          </div>
        </div>
      </div>
      <TabBar />
    </Screen>
  );
}
