"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { CheckGlyph, GearGlyph, HomeGlyph, StarGlyph } from "./icons";

const TABS = [
  { href: "/", label: "홈", glyph: <HomeGlyph /> },
  { href: "/tasks", label: "할 일", glyph: <CheckGlyph /> },
  { href: "/records", label: "기록", glyph: <StarGlyph fill="#fff" size={15} /> },
  { href: "/settings", label: "설정", glyph: <GearGlyph /> },
];

export default function TabBar() {
  const pathname = usePathname();

  return (
    <div
      style={{
        display: "flex",
        borderTop: "1px solid rgba(89,55,42,.1)",
        background: "rgba(255,255,255,.96)",
        padding: "9px 0 24px",
        flex: "none",
      }}
    >
      {TABS.map((tab) => {
        const active = pathname === tab.href;
        return (
          <Link
            key={tab.href}
            href={tab.href}
            style={{
              flex: 1,
              textAlign: "center",
              font: `${active ? 600 : 400} 10.5px 'Pretendard'`,
              color: active ? "#59372A" : "rgba(89,55,42,.45)",
              textDecoration: "none",
            }}
          >
            <div
              style={{
                width: 24,
                height: 24,
                borderRadius: 8,
                background: active ? "#C9DBF2" : "rgba(201,219,242,.55)",
                margin: "0 auto 5px",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              {tab.glyph}
            </div>
            {tab.label}
          </Link>
        );
      })}
    </div>
  );
}
