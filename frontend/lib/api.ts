import {
  toFromMessageResult,
  toGoal,
  toMessage,
  toProfile,
  toProject,
  toTask,
  toWeeklyStats,
} from "./adapters";
import type {
  ConversationMessage,
  FromMessageResult,
  Goal,
  MallangProfile,
  Project,
  Task,
  TaskDraftAssignment,
  WeeklyStats,
} from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!response.ok) {
    throw new Error(`Request to ${path} failed with ${response.status}`);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export async function listTasks(): Promise<Task[]> {
  const raw = await request<Parameters<typeof toTask>[0][]>("/tasks");
  return raw.map(toTask);
}

export async function toggleTaskDone(taskId: string, done: boolean): Promise<Task> {
  const raw = await request<Parameters<typeof toTask>[0]>(`/tasks/${taskId}`, {
    method: "PATCH",
    body: JSON.stringify({ done }),
  });
  return toTask(raw);
}

export async function rescheduleTask(
  taskId: string,
  changes: { due_date?: string | null; duration_min?: number | null },
): Promise<Task> {
  const raw = await request<Parameters<typeof toTask>[0]>(`/tasks/${taskId}`, {
    method: "PATCH",
    body: JSON.stringify(changes),
  });
  return toTask(raw);
}

export async function snoozeTask(taskId: string): Promise<Task> {
  const raw = await request<Parameters<typeof toTask>[0]>(`/tasks/${taskId}/snooze`, {
    method: "POST",
  });
  return toTask(raw);
}

export async function sendMessage(text: string): Promise<FromMessageResult> {
  const raw = await request<Parameters<typeof toFromMessageResult>[0]>("/tasks/from-message", {
    method: "POST",
    body: JSON.stringify({ text }),
  });
  return toFromMessageResult(raw);
}

export async function confirmProjectForTask(
  taskId: string,
  name: string,
): Promise<TaskDraftAssignment> {
  const raw = await request<{
    status: "matched";
    matched_by: "user_confirmed";
    project_id: string;
  }>(`/tasks/${taskId}/confirm-project`, {
    method: "POST",
    body: JSON.stringify({ name }),
  });
  return { status: "matched", matchedBy: raw.matched_by, projectId: raw.project_id };
}

export async function listProjects(): Promise<Project[]> {
  const raw = await request<Parameters<typeof toProject>[0][]>("/projects");
  return raw.map(toProject);
}

export async function listGoals(): Promise<Goal[]> {
  const raw = await request<Parameters<typeof toGoal>[0][]>("/goals");
  return raw.map(toGoal);
}

export async function getWeeklyStats(): Promise<WeeklyStats> {
  const raw = await request<Parameters<typeof toWeeklyStats>[0]>("/stats/weekly");
  return toWeeklyStats(raw);
}

export async function getProfile(): Promise<MallangProfile> {
  const raw = await request<Parameters<typeof toProfile>[0]>("/profile");
  return toProfile(raw);
}

export async function updateProfile(changes: {
  color?: string;
  accessories?: string[];
}): Promise<MallangProfile> {
  const raw = await request<Parameters<typeof toProfile>[0]>("/profile", {
    method: "PUT",
    body: JSON.stringify(changes),
  });
  return toProfile(raw);
}

export async function getConversation(): Promise<ConversationMessage[]> {
  const raw = await request<Parameters<typeof toMessage>[0][]>("/conversation");
  return raw.map(toMessage);
}
