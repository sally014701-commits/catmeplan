export default function Screen({
  children,
  background = "#FFFFFF",
}: {
  children: React.ReactNode;
  background?: string;
}) {
  return (
    <div style={{ minHeight: "100dvh", background: "#FAF6EC", display: "flex", justifyContent: "center" }}>
      <div
        className="no-scrollbar"
        style={{
          width: "100%",
          maxWidth: 480,
          minHeight: "100dvh",
          display: "flex",
          flexDirection: "column",
          background,
          position: "relative",
          overflow: "hidden",
          fontFamily: "'Pretendard', sans-serif",
          color: "#59372A",
        }}
      >
        {children}
      </div>
    </div>
  );
}
