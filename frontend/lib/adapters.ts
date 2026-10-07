import type {
  ConversationMessage,
  DayStat,
  FromMessageResult,
  Goal,
  MallangProfile,
  Project,
  Task,
  TaskDraftAssignment,
  WeeklyStats,
} from "./types";

type BackendTask = {
  id: string;
  source: string;
  content: string;
  evidence_date: string;
  due_date: string | null;
  project_id: string | null;
  title: string | null;
  people: string[];
  done: boolean;
  duration_min: number | null;
  snoozed_count: number;
};

export function toTask(raw: BackendTask): Task {
  return {
    id: raw.id,
    title: raw.title ?? raw.content,
    content: raw.content,
    projectId: raw.project_id,
    dueAt: raw.due_date,
    durationMin: raw.duration_min,
    source: raw.source === "google_calendar" ? "external" : raw.source === "mallang" ? "mallang" : "user",
    done: raw.done,
    snoozedCount: raw.snoozed_count,
  };
}

type BackendProject = {
  id: string;
  name: string;
  goal_id: string | null;
  people: string[];
  done_count: number;
  total_count: number;
};

export function toProject(raw: BackendProject): Project {
  return {
    id: raw.id,
    name: raw.name,
    goalId: raw.goal_id,
    doneCount: raw.done_count,
    totalCount: raw.total_count,
  };
}

type BackendGoal = {
  id: string;
  name: string;
  is_vision: boolean;
  items: string[];
  stalled: boolean;
};

export function toGoal(raw: BackendGoal): Goal {
  return {
    id: raw.id,
    name: raw.name,
    isVision: raw.is_vision,
    items: raw.items,
    stalled: raw.stalled,
  };
}

type BackendDayStat = { date: string; label: string; done_count: number; total_count: number };
type BackendWeeklyStats = {
  done_count: number;
  total_count: number;
  days: BackendDayStat[];
  postponed: { id: string; title: string; snoozed_count: number }[];
};

export function toWeeklyStats(raw: BackendWeeklyStats): WeeklyStats {
  const days: DayStat[] = raw.days.map((day) => ({
    date: day.date,
    label: day.label,
    doneCount: day.done_count,
    totalCount: day.total_count,
  }));
  return {
    doneCount: raw.done_count,
    totalCount: raw.total_count,
    days,
    postponed: raw.postponed.map((task) => ({
      id: task.id,
      title: task.title,
      snoozedCount: task.snoozed_count,
    })),
  };
}

type BackendProfile = { color: string; accessories: string[]; days_together: number };

export function toProfile(raw: BackendProfile): MallangProfile {
  return {
    color: (raw.color as MallangProfile["color"]) ?? "original",
    accessories: raw.accessories,
    daysTogether: raw.days_together,
  };
}

type BackendMessage = {
  id: string;
  role: "user" | "mallang";
  text: string;
  task_ids: string[];
  created_at: string;
};

export function toMessage(raw: BackendMessage): ConversationMessage {
  return {
    id: raw.id,
    role: raw.role,
    text: raw.text,
    taskIds: raw.task_ids,
    createdAt: raw.created_at,
  };
}

type BackendAssignment =
  | { status: "matched"; matched_by: "rule" | "llm_tiebreak" | "user_confirmed"; project_id: string }
  | { status: "needs_confirm"; suggested_name: string; reasoning: string | null };

function toAssignment(raw: BackendAssignment): TaskDraftAssignment {
  if (raw.status === "matched") {
    return { status: "matched", matchedBy: raw.matched_by, projectId: raw.project_id };
  }
  return { status: "needs_confirm", suggestedName: raw.suggested_name, reasoning: raw.reasoning };
}

type BackendFromMessage =
  | { type: "answer"; text: string }
  | { type: "task_created"; task: BackendTask; assignment: BackendAssignment }[];

export function toFromMessageResult(raw: BackendFromMessage): FromMessageResult {
  if (Array.isArray(raw)) {
    return {
      type: "tasks_created",
      items: raw.map((item) => ({ task: toTask(item.task), assignment: toAssignment(item.assignment) })),
    };
  }
  return raw;
}
