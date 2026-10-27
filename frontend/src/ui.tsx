import { useEffect, useId, useRef, useState } from "react";
import type { ReactNode } from "react";
import {
  AlertCircle,
  Camera,
  Image as ImageIcon,
  Loader2,
  Smile,
  Meh,
  Cloud,
  Frown,
  Sun,
  Save,
  X,
} from "lucide-react";
import { cityLocation, moodLabel, moods, photoUrl } from "./api";
import type { Entry, Location, Photo, Stats } from "./api";

export function SproutMark({ className = "" }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 48 40"
      fill="none"
      aria-hidden="true"
    >
      <path
        d="M24 37C24 24 19 19 13 14M24 30C25 21 31 14 37 9"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
      />
      <path d="M22 26C9 25 5 16 5 8C16 10 24 14 22 26Z" fill="currentColor" />
      <path d="M26 21C25 11 32 5 43 3C41 15 35 22 26 21Z" fill="currentColor" />
      <path
        d="M9 12L20 23M39 7L28 18"
        stroke="white"
        strokeOpacity=".45"
        strokeWidth="1"
      />
    </svg>
  );
}
export function LeafBranch({ className = "" }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 72 104"
      fill="none"
      aria-hidden="true"
    >
      <path d="M9 98C40 80 50 46 59 7" stroke="#8a8b64" strokeWidth="1.3" />
      <path
        d="M29 81C20 68 22 57 25 51C31 62 34 71 29 81ZM39 66C49 65 59 57 66 47C53 48 43 53 39 66ZM45 48C38 37 42 24 46 18C49 29 50 39 45 48ZM52 28C62 20 64 9 64 2C57 9 52 18 52 28ZM18 91C24 87 32 87 40 88C32 95 25 97 18 91Z"
        fill="#a2aa7f"
      />
      <path
        d="M25 55L29 77M45 22V44M43 63L62 50"
        stroke="#c6c9a8"
        strokeWidth="1"
      />
    </svg>
  );
}
export function PanelHeading({
  icon,
  title,
  subtitle,
}: {
  icon: ReactNode;
  title: string;
  subtitle?: string;
}) {
  return (
    <header className="panel-heading">
      <span className="panel-icon">{icon}</span>
      <div>
        <h2>{title}</h2>
        {subtitle ? <p>{subtitle}</p> : null}
      </div>
    </header>
  );
}

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
      <div className="heading-side">
        <div className="page-quote">
          <span className="quote-mark">“</span>
          <p>
            {title === "未来信件" ? (
              <>
                给未来的自己，
                <br />
                也是给此刻努力生活的你。
              </>
            ) : title === "设置" ? (
              <>
                好的设置，
                <br />
                是为了更安心地记录。
              </>
            ) : title === "回忆" ? (
              <>
                有些瞬间虽然过去，
                <br />
                但依然在今天温柔地闪回。
              </>
            ) : (
              <>
                平凡的日子，
                <br />
                也值得被认真记录。
              </>
            )}
          </p>
          <LeafBranch />
        </div>
        {children ? <div className="heading-actions">{children}</div> : null}
      </div>
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
        <label>心情</label>
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
              <span>
                {m.value === "happy" ? (
                  <Smile />
                ) : m.value === "calm" ? (
                  <Meh />
                ) : m.value === "tired" ? (
                  <Cloud />
                ) : m.value === "sad" ? (
                  <Frown />
                ) : (
                  <Sun />
                )}
              </span>
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
        <label htmlFor={`${id}-note`}>日记</label>
        <textarea
          id={`${id}-note`}
          placeholder={"今天发生了什么？\n此刻的心情如何？有什么想记录的…"}
          value={draft.note}
          maxLength={5000}
          onChange={(e) => change("note", e.target.value)}
          rows={3}
        />
        <span className="char-count">{draft.note.length} / 5000</span>
      </div>
      <div className="field">
        <label htmlFor={`${id}-city`}>城市</label>
        <input
          id={`${id}-city`}
          value={draft.city}
          placeholder="选择或输入城市（可选）"
          onChange={(e) => change("city", e.target.value)}
          maxLength={200}
        />
      </div>
      <div className="field">
        <label htmlFor={`${id}-tags`}>标签</label>
        <input
          id={`${id}-tags`}
          value={draft.tags}
          placeholder="添加标签，用逗号分隔（例如：工作，旅行）"
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
      {busy ? <Loader2 className="spin" size={18} /> : <Save size={18} />}{" "}
      {busy ? "正在保存…" : children}
    </>
  );
}
export const CameraSymbol = () => <Camera size={42} strokeWidth={1.3} />;
