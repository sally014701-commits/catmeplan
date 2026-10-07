"use client";

import { useCallback, useEffect, useState } from "react";

import { getConversation, getProfile, getWeeklyStats, listGoals, listProjects, listTasks } from "./api";
import type { ConversationMessage, Goal, MallangProfile, Project, Task, WeeklyStats } from "./types";

export function useMallangProfile() {
  const [profile, setProfile] = useState<MallangProfile | null>(null);

  const refresh = useCallback(() => {
    getProfile().then(setProfile).catch(() => undefined);
  }, []);

  useEffect(refresh, [refresh]);

  return { profile, refresh };
}

export function useTasks() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(() => {
    setLoading(true);
    listTasks()
      .then(setTasks)
      .catch(() => undefined)
      .finally(() => setLoading(false));
  }, []);

  useEffect(refresh, [refresh]);

  return { tasks, loading, refresh, setTasks };
}

export function useProjects() {
  const [projects, setProjects] = useState<Project[]>([]);
  const refresh = useCallback(() => {
    listProjects().then(setProjects).catch(() => undefined);
  }, []);
  useEffect(refresh, [refresh]);
  return { projects, refresh };
}

export function useGoals() {
  const [goals, setGoals] = useState<Goal[]>([]);
  const refresh = useCallback(() => {
    listGoals().then(setGoals).catch(() => undefined);
  }, []);
  useEffect(refresh, [refresh]);
  return { goals, refresh };
}

export function useWeeklyStats() {
  const [stats, setStats] = useState<WeeklyStats | null>(null);
  const refresh = useCallback(() => {
    getWeeklyStats().then(setStats).catch(() => undefined);
  }, []);
  useEffect(refresh, [refresh]);
  return { stats, refresh };
}

export function useConversation() {
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const refresh = useCallback(() => {
    setLoading(true);
    getConversation()
      .then(setMessages)
      .catch(() => undefined)
      .finally(() => setLoading(false));
  }, []);
  useEffect(refresh, [refresh]);
  return { messages, loading, refresh, setMessages };
}
