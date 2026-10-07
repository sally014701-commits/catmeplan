const WEEKDAYS = ["일", "월", "화", "수", "목", "금", "토"];

export function isSameDay(a: Date, b: Date): boolean {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}

export function greetingLabel(now: Date = new Date()): string {
  const weekday = WEEKDAYS[now.getDay()];
  const hour = now.getHours();
  const part = hour < 11 ? "아침" : hour < 14 ? "점심" : hour < 19 ? "오후" : "저녁";
  return `${weekday}요일 ${part}`;
}

export function monthLabel(date: Date): string {
  return `${date.getFullYear()}년 ${date.getMonth() + 1}월`;
}

export function dateLabel(date: Date): string {
  return `${date.getMonth() + 1}월 ${date.getDate()}일 ${WEEKDAYS[date.getDay()]}요일`;
}

export function formatDuration(minutes: number | null): string {
  if (!minutes) return "";
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  if (hours && rest) return `${hours}H ${rest}m`;
  if (hours) return `${hours}H`;
  return `${rest}m`;
}

export function formatTimeLabel(dueAt: string | null, now: Date = new Date()): string {
  if (!dueAt) return "시간 미정";
  const due = new Date(dueAt);
  const hasTime = dueAt.includes("T");
  const tomorrow = new Date(now);
  tomorrow.setDate(now.getDate() + 1);

  if (!hasTime) {
    if (isSameDay(due, now)) return "오늘";
    if (isSameDay(due, tomorrow)) return "내일";
    return `${due.getMonth() + 1}/${due.getDate()}`;
  }

  const time = due.toLocaleTimeString("ko-KR", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
  if (isSameDay(due, now)) return time;
  if (isSameDay(due, tomorrow)) return `내일 ${time}`;
  return `${due.getMonth() + 1}/${due.getDate()} ${time}`;
}
