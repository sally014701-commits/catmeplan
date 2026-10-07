export type TaskSource = "user" | "mallang" | "external";

export type Task = {
  id: string;
  title: string;
  content: string;
  projectId: string | null;
  dueAt: string | null;
  durationMin: number | null;
  source: TaskSource;
  done: boolean;
  snoozedCount: number;
};

export type Project = {
  id: string;
  name: string;
  goalId: string | null;
  doneCount: number;
  totalCount: number;
};

export type Goal = {
  id: string;
  name: string;
  isVision: boolean;
  items: string[];
  stalled: boolean;
};

export type DayStat = {
  date: string;
  label: string;
  doneCount: number;
  totalCount: number;
};

export type WeeklyStats = {
  doneCount: number;
  totalCount: number;
  days: DayStat[];
  postponed: { id: string; title: string; snoozedCount: number }[];
};

export type MallangProfile = {
  color: "original" | "blue" | "cream" | "olive" | "red";
  accessories: string[];
  daysTogether: number;
};

export type ConversationMessage = {
  id: string;
  role: "user" | "mallang";
  text: string;
  taskIds: string[];
  createdAt: string;
};

export type TaskDraftAssignment =
  | { status: "matched"; matchedBy: "rule" | "llm_tiebreak" | "user_confirmed"; projectId: string }
  | { status: "needs_confirm"; suggestedName: string; reasoning: string | null };

export type FromMessageResult =
  | { type: "answer"; text: string }
  | { type: "tasks_created"; items: { task: Task; assignment: TaskDraftAssignment }[] };
