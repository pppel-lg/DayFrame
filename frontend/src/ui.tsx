import { useEffect, useId, useRef, useState } from "react";
import type { ReactNode } from "react";
import {
  AlertCircle,
  Camera,
  Check,
  Image as ImageIcon,
  Loader2,
  X,
} from "lucide-react";
import { cityLocation, moodLabel, moods, photoUrl } from "./api";
import type { Entry, Location, Photo, Stats } from "./api";

export function ErrorBanner({
  message,
  retry,
}: {
  message: string;
  retry?: () => void;
}) {
  return message ? (
    <div className="error-banner" role="alert">
      <AlertCircle size={17} />
      <span>{message}</span>
      {retry ? (
        <button className="text-button" onClick={retry}>
          重试
        </button>
      ) : null}
    </div>
  ) : null;
}
export function Loading() {
  return (
    <div className="loading" role="status">
      <Loader2 size={20} className="spin" /> 正在读取你的档案…
    </div>
  );
}
export function Empty({
  title,
  children,
  icon = <ImageIcon size={28} />,
}: {
  title: string;
  children?: ReactNode;
  icon?: ReactNode;
}) {
  return (
    <div className="empty">
      <div className="empty-icon">{icon}</div>
      <h3>{title}</h3>
      {children ? <div className="muted">{children}</div> : null}
    </div>
  );
}
export function PageHeader({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children?: ReactNode;
}) {
  return (
    <header className="page-heading">
      <div>
        <h1>{title}</h1>
        {subtitle ? <p>{subtitle}</p> : null}
      </div>
      {children ? <div className="heading-actions">{children}</div> : null}
    </header>
  );
}
export function PhotoView({
  photo,
  original = false,
  className = "",
  alt = "自拍照片",
}: {
  photo?: Photo;
  original?: boolean;
  className?: string;
  alt?: string;
}) {
  const [failed, setFailed] = useState(0);
  useEffect(() => setFailed(0), [photo?.photo_id]);
  const derived =
    !original || /hei[cf]/i.test(photo?.mime_type || "") || failed === 1;
  return !photo || photo.missing || failed >= 2 ? (
    <div className={`photo-placeholder ${className}`}>
      <ImageIcon size={22} />
      <span>{photo ? "原图缺失或格式无法预览" : "暂无记录"}</span>
    </div>
  ) : (
    <img
      className={className}
      src={photoUrl(photo.photo_id, derived)}
      loading="lazy"
      alt={alt}
      onError={() => setFailed(derived ? 2 : 1)}
    />
  );
}
export function Toggle({
  checked,
  onChange,
  children,
  disabled = false,
}: {
  checked: boolean;
  onChange: (value: boolean) => void;
  children: ReactNode;
  disabled?: boolean;
}) {
  return (
    <label className="toggle-label">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        disabled={disabled}
      />
      <span className="toggle-track" />
      <span>{children}</span>
    </label>
  );
}
export function Modal({
  title,
  onClose,
  children,
  wide = false,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
  wide?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const el = ref.current;
    el?.showModal();
    return () => el?.close();
  }, []);
  return (
    <dialog
      ref={ref}
      className={`modal ${wide ? "wide" : ""}`}
      onCancel={onClose}
      onClick={(e) => {
        if (e.target === ref.current) onClose();
      }}
    >
      <div className="modal-inner">
        <header className="modal-heading">
          <h2>{title}</h2>
          <button className="icon-button" aria-label="关闭" onClick={onClose}>
            <X size={21} />
          </button>
        </header>
        {children}
      </div>
    </dialog>
  );
}
export type Draft = {
  mood: string;
  note: string;
  tags: string;
  city: string;
  location?: Location;
};
export const entryDraft = (entry?: Entry | null): Draft => ({
  mood: entry?.mood || "",
  note: entry?.note || "",
  tags: entry?.tags.join(", ") || "",
  city: entry?.location?.city || entry?.location?.label || "",
  location: entry?.location,
});
export const draftPayload = (draft: Draft) => ({
  mood: draft.mood,
  note: draft.note,
  tags: draft.tags
    .split(/[,，]/)
    .map((v) => v.trim())
    .filter(Boolean),
  location:
    draft.location &&
    draft.city === (draft.location.city || draft.location.label)
      ? draft.location
      : cityLocation(draft.city.trim()),
});
export function EntryFields({
  draft,
  onChange,
  disabled = false,
}: {
  draft: Draft;
  onChange: (draft: Draft) => void;
  disabled?: boolean;
}) {
  const id = useId();
  function change(key: keyof Draft, value: string) {
    onChange({ ...draft, [key]: value });
  }
  return (
    <fieldset className="entry-fields" disabled={disabled}>
      <div className="field">
        <label>
          此刻心情 <span className="optional">可选</span>
        </label>
        <div className="mood-options">
          {moods.map((m) => (
            <button
              type="button"
              key={m.value}
              title={m.label}
              className={draft.mood === m.value ? "mood selected" : "mood"}
              onClick={() =>
                change("mood", draft.mood === m.value ? "" : m.value)
              }
              aria-pressed={draft.mood === m.value}
            >
              <span>{m.symbol}</span>
              {m.label}
            </button>
          ))}
        </div>
        <details
          className="custom-mood"
          open={
            draft.mood && !moods.some((m) => m.value === draft.mood)
              ? true
              : undefined
          }
        >
          <summary>
            自定义心情
            {draft.mood && !moods.some((m) => m.value === draft.mood)
              ? `：${moodLabel(draft.mood)}`
              : ""}
          </summary>
          <input
            aria-label="自定义心情"
            placeholder="或写下自己的心情"
            value={moods.some((m) => m.value === draft.mood) ? "" : draft.mood}
            onChange={(e) => change("mood", e.target.value)}
            maxLength={40}
          />
        </details>
      </div>
      <div className="field">
        <label htmlFor={`${id}-note`}>想对自己说</label>
        <textarea
          id={`${id}-note`}
          placeholder="记录此刻的想法、感受，或任何想留下来的东西…"
          value={draft.note}
          maxLength={5000}
          onChange={(e) => change("note", e.target.value)}
          rows={3}
        />
        <span className="char-count">{draft.note.length} / 5000</span>
      </div>
      <div className="field">
        <label htmlFor={`${id}-city`}>
          所在城市 <span className="optional">可选</span>
        </label>
        <input
          id={`${id}-city`}
          value={draft.city}
          placeholder="输入你所在的城市"
          onChange={(e) => change("city", e.target.value)}
          maxLength={200}
        />
      </div>
      <div className="field">
        <label htmlFor={`${id}-tags`}>
          标签 <span className="optional">逗号分隔</span>
        </label>
        <input
          id={`${id}-tags`}
          value={draft.tags}
          placeholder="例如：日常，旅行"
          onChange={(e) => change("tags", e.target.value)}
          maxLength={1000}
        />
      </div>
    </fieldset>
  );
}
export function StatsBar({ stats }: { stats: Stats | null }) {
  return (
    <div className="stats-bar">
      {[
        { label: "已记录", value: stats?.recorded_days, suffix: "天" },
        { label: "应记录", value: stats?.eligible_days, suffix: "天" },
        {
          label: "记录率",
          value: stats
            ? `${Math.round(stats.recording_rate * 100)}%`
            : undefined,
        },
        { label: "跳过休息", value: stats?.skipped_days, suffix: "天" },
        { label: "当前连续", value: stats?.current_streak, suffix: "天" },
        { label: "照片", value: stats?.photo_count, suffix: "张" },
      ].map((s) => (
        <div key={s.label}>
          <span>{s.label}</span>
          <strong>
            {s.value ?? "—"}
            <small>{s.suffix}</small>
          </strong>
        </div>
      ))}
    </div>
  );
}
export function SaveLabel({
  busy,
  children = "保存记录",
}: {
  busy: boolean;
  children?: ReactNode;
}) {
  return (
    <>
      {busy ? <Loader2 className="spin" size={16} /> : <Check size={16} />}{" "}
      {busy ? "正在保存…" : children}
    </>
  );
}
export const CameraSymbol = () => <Camera size={42} strokeWidth={1.3} />;
