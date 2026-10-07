export type CalendarCell = { day: number; date: Date } | null;

export function buildMonthGrid(year: number, month: number): CalendarCell[] {
  const first = new Date(year, month, 1);
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const leading = first.getDay();
  const cells: CalendarCell[] = Array.from({ length: leading }, () => null);
  for (let day = 1; day <= daysInMonth; day += 1) {
    cells.push({ day, date: new Date(year, month, day) });
  }
  return cells;
}
