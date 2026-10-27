import { useCallback, useEffect, useRef, useState } from "react";

export type Photo = {
  photo_id: string;
  relative_path: string;
  sha256: string;
  byte_size: number;
  mime_type: string;
  captured_at_utc: string | null;
  captured_timezone: string | null;
  captured_offset_minutes: number | null;
  imported_at_utc: string;
  source: string;
  is_original: boolean;
  trashed_at_utc: string | null;
  missing?: boolean;
};
export type Location = {
  label: string;
  city: string;
  region: string;
  country: string;
  latitude: number | null;
  longitude: number | null;
  precision: "none" | "city" | "exact";
  source: "manual";
};
export type Entry = {
  schema_version: 1;
  entry_id: string;
  record_date: string;
  status: "recorded" | "skipped";
  primary_photo_id: string | null;
  mood: string;
  note: string;
  tags: string[];
  location: Location;
  photos: Photo[];
  created_at_utc: string;
  updated_at_utc: string;
};
export type Settings = {
  reminder_enabled: boolean;
  reminder_time: string;
  mirror_preview: boolean;
  mirror_output: boolean;
  week_starts_monday: boolean;
};
export type Status = {
  archive: { archive_start_date: string; archive_id: string };
  settings: Settings;
  health: { issues: unknown[] };
  photo_count: number;
  entry_count: number;
  archive_path: string;
  backup_path: string;
};
export type Stats = {
  recorded_days: number;
  eligible_days: number;
  recording_rate: number;
  skipped_days: number;
  missing_days: number;
  photo_count: number;
  current_streak: number;
  total_days: number;
  monthly: { month: string; count: number }[];
  moods: { mood: string; count: number }[];
};
export type Job = {
  job_id: string;
  kind: string;
  status: "queued" | "running" | "success" | "failed" | "cancelled";
  progress: number;
  result?: Record<string, unknown>;
  error?: string;
};
export type Letter = {
  letter_id: string;
  title: string;
  unlock_date: string;
  created_at_utc: string;
  content?: string;
  locked: boolean;
};
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}
export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (init?.body && !(init.body instanceof FormData))
    headers.set("Content-Type", "application/json");
  const response = await fetch(`/api${path}`, {
    ...init,
    headers,
    credentials: "same-origin",
  });
  if (!response.ok) {
    let message = `请求失败（${response.status}）`;
    try {
      const data = await response.json();
      const d = data.detail;
      message = typeof d === "string" ? d : d?.message || message;
    } catch {
      /* non-JSON error */
    }
    throw new ApiError(response.status, message);
  }
  if (response.status === 204) return undefined as T;
  return response.json();
}
export const send = <T>(path: string, body: unknown, method = "POST") =>
  api<T>(path, { method, body: JSON.stringify(body) });
export function useResource<T>(path: string | null, revision = 0) {
  const [data, setData] = useState<T | null>(null),
    [loading, setLoading] = useState(true),
    [error, setError] = useState("");
  const sequence = useRef(0);
  const reload = useCallback(async () => {
    const id = ++sequence.current;
    if (!path) {
      setData(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError("");
    try {
      const value = await api<T>(path);
      if (id === sequence.current) setData(value);
    } catch (e) {
      if (id === sequence.current) setError(errorText(e));
    } finally {
      if (id === sequence.current) setLoading(false);
    }
  }, [path]);
  const loadedPath = useRef(path);
  useEffect(() => {
    // A refresh must not unmount the active page or discard a draft.
    // Clear stale data only when navigating to a different resource.
    if (loadedPath.current !== path) {
      setData(null);
      loadedPath.current = path;
    }
    void reload();
    return () => {
      sequence.current++;
    };
  }, [path, reload, revision]);
  return { data, loading, error, reload, setData };
}
export function errorText(e: unknown) {
  return e instanceof Error ? e.message : "操作未完成，请重试。";
}
export function today() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
export function dateShift(value: string, days: number) {
  const d = new Date(`${value}T12:00:00`);
  d.setDate(d.getDate() + days);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
export function dateLabel(
  value: string,
  options: Intl.DateTimeFormatOptions = {
    month: "long",
    day: "numeric",
    weekday: "long",
  },
) {
  return new Date(`${value}T12:00:00`).toLocaleDateString("zh-CN", options);
}
export const photoUrl = (id: string, thumbnail = true) =>
  `/api/photos/${encodeURIComponent(id)}${thumbnail ? "?thumbnail=true" : ""}`;
export const primary = (entry?: Entry | null) =>
  entry?.photos.find(
    (p) => p.photo_id === entry.primary_photo_id && !p.trashed_at_utc,
  );
export const cityLocation = (city: string): Location => ({
  label: city,
  city,
  region: "",
  country: "",
  latitude: null,
  longitude: null,
  precision: city ? "city" : "none",
  source: "manual",
});
export const moods = [
  { value: "calm", label: "平静", symbol: "◡" },
  { value: "happy", label: "开心", symbol: "☺" },
  { value: "tired", label: "疲惫", symbol: "⌁" },
  { value: "sad", label: "低落", symbol: "◠" },
  { value: "excited", label: "兴奋", symbol: "✧" },
];
export const moodLabel = (mood: string) =>
  moods.find((m) => m.value === mood)?.label || mood;
export async function uploadPhoto(
  date: string,
  file: File,
  source: "camera" | "import",
  captured?: string,
) {
  const form = new FormData();
  form.set("file", file);
  form.set("source", source);
  form.set("make_primary", "false");
  if (captured) {
    form.set("captured_at_utc", captured);
    form.set(
      "captured_timezone",
      Intl.DateTimeFormat().resolvedOptions().timeZone,
    );
    form.set(
      "captured_offset_minutes",
      String(-new Date().getTimezoneOffset()),
    );
  }
  const path = `/entries/${date}/photos`;
  try {
    return await api<Entry>(path, { method: "POST", body: form });
  } catch (error) {
    if (
      error instanceof ApiError &&
      error.status === 409 &&
      error.message ===
        "duplicate image exists on another date; confirm to copy" &&
      window.confirm("相同原图已存在于其他日期，仍为当前日期保存副本？")
    ) {
      form.set("allow_duplicate", "true");
      return api<Entry>(path, { method: "POST", body: form });
    }
    throw error;
  }
}
