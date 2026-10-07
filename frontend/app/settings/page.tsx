"use client";

import { useEffect, useState } from "react";

import Mallang3D, { type MallangColor } from "@/components/Mallang3D";
import Screen from "@/components/Screen";
import TabBar from "@/components/TabBar";
import { useMallangProfile } from "@/lib/hooks";
import { updateProfile } from "@/lib/api";

const SWATCHES: { id: MallangColor; hex: string }[] = [
  { id: "original", hex: "#F2B9C4" },
  { id: "blue", hex: "#C9DBF2" },
  { id: "cream", hex: "#F2E9BB" },
  { id: "olive", hex: "#BFBB80" },
  { id: "red", hex: "#8C1822" },
];

export default function SettingsPage() {
  const { profile, refresh } = useMallangProfile();
  const [previewColor, setPreviewColor] = useState<MallangColor | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (profile && previewColor === null) setPreviewColor(profile.color);
  }, [profile, previewColor]);

  const activeColor = previewColor ?? profile?.color ?? "original";

  async function handleSave() {
    setSaving(true);
    try {
      await updateProfile({ color: activeColor });
      refresh();
      setSaved(true);
      setTimeout(() => setSaved(false), 1600);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Screen>
      <div style={{ padding: "28px 20px 2px", font: "600 26px 'Pretendard'", color: "#59372A", flex: "none" }}>말랑이 꾸미기</div>
      <div style={{ padding: "0 20px 14px", font: "400 13px 'Pretendard'", color: "rgba(89,55,42,.45)", flex: "none" }}>
        같이 지낸 지 {profile?.daysTogether ?? 0}일
      </div>
      <div style={{ margin: "0 20px", height: 250, display: "flex", alignItems: "center", justifyContent: "center", position: "relative", flex: "none" }}>
        <Mallang3D size={250} fieldOfView={34} interactive color={activeColor} />
      </div>
      <div style={{ flex: 1, padding: "18px 20px 0", display: "flex", flexDirection: "column", gap: 16, overflow: "hidden" }}>
        <div>
          <div style={{ font: "600 12px 'Pretendard'", color: "rgba(89,55,42,.45)", letterSpacing: ".06em", marginBottom: 10 }}>색</div>
          <div style={{ display: "flex", gap: 9 }}>
            {SWATCHES.map((swatch) => (
              <button
                key={swatch.id}
                type="button"
                onClick={() => setPreviewColor(swatch.id)}
                style={{
                  width: 44,
                  height: 44,
                  borderRadius: 14,
                  background: swatch.hex,
                  cursor: "pointer",
                  border: activeColor === swatch.id ? "2.5px solid #59372A" : "2.5px solid transparent",
                  boxSizing: "border-box",
                  transition: "border-color .18s ease",
                }}
              />
            ))}
          </div>
        </div>
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
      <div style={{ padding: "10px 20px 10px", flex: "none" }}>
        <button
          type="button"
          onClick={handleSave}
          disabled={saving}
          style={{
            width: "100%",
            textAlign: "center",
            font: "500 15px 'Pretendard'",
            color: "#F5EFD3",
            background: "#8C1822",
            padding: "14px 0",
            borderRadius: 16,
            border: "none",
            cursor: "pointer",
          }}
        >
          {saved ? "저장했어" : "저장하기"}
        </button>
      </div>
      <TabBar />
    </Screen>
  );
}
