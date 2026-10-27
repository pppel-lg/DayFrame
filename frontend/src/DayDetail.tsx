import { useEffect, useRef, useState } from "react";
import { Download, ImagePlus, RotateCcw, Star, Trash2 } from "lucide-react";
import {
  api,
  ApiError,
  dateLabel,
  errorText,
  primary,
  send,
  today,
  uploadPhoto,
} from "./api";
import type { Entry } from "./api";
import {
  draftPayload,
  entryDraft,
  EntryFields,
  ErrorBanner,
  Loading,
  Modal,
  PhotoView,
  SaveLabel,
} from "./ui";

export default function DayDetail({
  date,
  onClose,
  onChange,
}: {
  date: string;
  onClose: () => void;
  onChange: () => void;
}) {
  const [entry, setEntry] = useState<Entry | null>(null),
    [draft, setDraft] = useState(entryDraft()),
    [loading, setLoading] = useState(true),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  const input = useRef<HTMLInputElement>(null);
  useEffect(() => {
    let active = true;
    setLoading(true);
    void api<Entry>(`/entries/${date}`)
      .then((e) => {
        if (active) {
          setEntry(e);
          setDraft(entryDraft(e));
        }
      })
      .catch((e) => {
        if (active && !(e instanceof ApiError && e.status === 404))
          setError(errorText(e));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [date]);
  async function mutate(task: () => Promise<Entry>, message: string) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const value = await task();
      setEntry(value);
      setDraft(entryDraft(value));
      setNotice(message);
      onChange();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }
  async function importFile(file?: File) {
    if (!file) return;
    await mutate(async () => {
      const e = await uploadPhoto(date, file, "import");
      return send<Entry>(`/entries/${date}`, draftPayload(draft), "PUT").catch(
        (err) => {
          setEntry(e);
          throw err;
        },
      );
    }, "照片已保存，原始文件已保留。");
    if (input.current) input.current.value = "";
  }
  const chosen = primary(entry);
  return (
    <Modal
      title={dateLabel(date, {
        year: "numeric",
        month: "long",
        day: "numeric",
        weekday: "long",
      })}
      onClose={onClose}
      wide
    >
      <ErrorBanner message={error} />
      {notice ? (
        <p className="success" role="status">
          {notice}
        </p>
      ) : null}
      {loading ? (
        <Loading />
      ) : (
        <div className="detail-grid">
          <section>
            <div className="detail-primary">
              <PhotoView photo={chosen} original alt={`${date} 的主照片`} />
              {entry?.status === "skipped" ? (
                <span className="state-tag">这一天，留给生活</span>
              ) : null}
            </div>
            <input
              className="sr-only"
              ref={input}
              type="file"
              accept="image/*,.heic,.heif"
              onChange={(e) => void importFile(e.target.files?.[0])}
            />
            <div className="button-row">
              <button disabled={busy} onClick={() => input.current?.click()}>
                <ImagePlus size={16} />
                添加照片
              </button>
              {chosen && !chosen.missing ? (
                <a
                  className="button"
                  href={`/api/photos/${chosen.photo_id}?download=true`}
                >
                  <Download size={16} />
                  下载原图
                </a>
              ) : null}
            </div>
            {chosen ? (
              <div className="photo-info">
                <span>
                  实际拍摄：
                  {chosen.captured_at_utc
                    ? new Date(chosen.captured_at_utc).toLocaleString("zh-CN")
                    : "导入文件未提供拍摄时间"}
                </span>
                <span>
                  导入时间：
                  {new Date(chosen.imported_at_utc).toLocaleString("zh-CN")}
                </span>
                <span>
                  记录日期：{date} ·{" "}
                  {chosen.source === "camera" ? "相机拍摄" : "文件导入"}
                </span>
              </div>
            ) : null}
            <h3 className="section-title">
              当天的照片{" "}
              <span>
                {entry?.photos.filter((p) => !p.trashed_at_utc).length || 0}
              </span>
            </h3>
            <div className="photo-list">
              {entry?.photos
                .filter((p) => !p.trashed_at_utc)
                .map((photo) => (
                  <div className="photo-row" key={photo.photo_id}>
                    <PhotoView photo={photo} />
                    <div>
                      <span>
                        {photo.photo_id === entry.primary_photo_id
                          ? "当前主照片"
                          : "附加照片"}
                      </span>
                      <small>
                        {Math.round(photo.byte_size / 1024)} KB ·{" "}
                        {photo.mime_type}
                      </small>
                      <div className="button-row">
                        {photo.photo_id !== entry.primary_photo_id ? (
                          <button
                            className="text-button"
                            disabled={busy || photo.missing}
                            onClick={() => {
                              if (
                                window.confirm(
                                  "将这张照片设为当天主照片？之前的主照片仍会保留。",
                                )
                              )
                                void mutate(
                                  () =>
                                    send<Entry>(`/entries/${date}/primary`, {
                                      photo_id: photo.photo_id,
                                      confirmed: true,
                                    }),
                                  "主照片已更新。",
                                );
                            }}
                          >
                            <Star size={14} />
                            设为主照片
                          </button>
                        ) : null}
                        <button
                          className="text-button danger"
                          disabled={busy}
                          onClick={() => {
                            if (
                              window.confirm(
                                "将这张照片移入回收站？你可以在下方恢复它；移走最后一张照片后当天会标为跳过。",
                              )
                            )
                              void mutate(
                                () =>
                                  send<Entry>(`/entries/${date}/trash`, {
                                    photo_id: photo.photo_id,
                                    confirmed: true,
                                  }),
                                "照片已移入回收站。",
                              );
                          }}
                        >
                          <Trash2 size={14} />
                          移入回收站
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
            </div>
            {entry?.photos.some((p) => p.trashed_at_utc) ? (
              <details className="trash-list">
                <summary>
                  回收站（{entry.photos.filter((p) => p.trashed_at_utc).length}
                  ）
                </summary>
                {entry.photos
                  .filter((p) => p.trashed_at_utc)
                  .map((p) => (
                    <div className="button-row" key={p.photo_id}>
                      <span>
                        {p.photo_id.slice(0, 8)} ·{" "}
                        {Math.round(p.byte_size / 1024)} KB
                      </span>
                      <button
                        disabled={busy}
                        onClick={() =>
                          void mutate(
                            () =>
                              send<Entry>(`/entries/${date}/untrash`, {
                                photo_id: p.photo_id,
                              }),
                            "照片已恢复。",
                          )
                        }
                      >
                        <RotateCcw size={14} />
                        恢复
                      </button>
                    </div>
                  ))}
              </details>
            ) : null}
          </section>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void mutate(
                () =>
                  send<Entry>(`/entries/${date}`, draftPayload(draft), "PUT"),
                "记录已更新。",
              );
            }}
          >
            <h3>这一天的故事</h3>
            <EntryFields draft={draft} onChange={setDraft} disabled={busy} />
            <button className="primary full" disabled={busy || !entry}>
              <SaveLabel busy={busy} />
            </button>
            <button
              type="button"
              className="text-button full rest-button"
              disabled={busy || date > today()}
              onClick={() => {
                if (entry?.photos.some((p) => !p.trashed_at_utc)) {
                  setError("请先将当天照片移入回收站，再标记为跳过。");
                  return;
                }
                void mutate(
                  () =>
                    send<Entry>(
                      `/entries/${date}`,
                      { ...draftPayload(draft), status: "skipped" },
                      "PUT",
                    ),
                  "已标记为跳过。",
                );
              }}
            >
              将这一天标记为跳过
            </button>
            <p className="small muted">
              休息也是生活的一部分，不必每天完成。补记保留照片真实拍摄时间。
            </p>
          </form>
        </div>
      )}
    </Modal>
  );
}
