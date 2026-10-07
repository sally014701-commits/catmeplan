PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS goal (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    is_vision INTEGER NOT NULL DEFAULT 0,
    items TEXT NOT NULL DEFAULT '[]',
    stalled INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS project (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    goal_id TEXT,
    people TEXT NOT NULL DEFAULT '[]',
    FOREIGN KEY (goal_id) REFERENCES goal (id)
);

CREATE TABLE IF NOT EXISTS task (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    content TEXT NOT NULL,
    evidence_date TEXT NOT NULL,
    due_date TEXT,
    project_id TEXT,
    title TEXT,
    external_id TEXT,
    people TEXT NOT NULL DEFAULT '[]',
    done INTEGER NOT NULL DEFAULT 0,
    duration_min INTEGER,
    snoozed_count INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (project_id) REFERENCES project (id)
);

CREATE TABLE IF NOT EXISTS message (
    id TEXT PRIMARY KEY,
    role TEXT NOT NULL,
    text TEXT NOT NULL,
    task_ids TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS profile (
    id TEXT PRIMARY KEY,
    color TEXT NOT NULL DEFAULT 'original',
    accessories TEXT NOT NULL DEFAULT '[]',
    started_at TEXT NOT NULL
);
