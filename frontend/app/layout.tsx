import type { Metadata } from "next";

import "../globals.css";

export const metadata: Metadata = {
  title: "말랑이 플래너",
  description: "말랑이와 대화하며 할 일을 맡기고, 내 일정을 물어볼 수 있는 AI 생활 플래너",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Gowun+Dodum&display=swap"
          rel="stylesheet"
        />
        <link
          rel="stylesheet"
          href="https://cdn.jsdelivr.net/npm/pretendard@1.3.9/dist/web/static/pretendard.css"
        />
      </head>
      <body className="antialiased" style={{ fontFamily: "'Pretendard', sans-serif" }}>
        {children}
      </body>
    </html>
  );
}
