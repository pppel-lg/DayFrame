import { useEffect, useRef, useState } from "react";
import {
  Camera,
  CameraOff,
  Check,
  ChevronRight,
  ImagePlus,
  NotebookPen,
  Clock3,
  Plus,
  RefreshCw,
  Square,
  Upload,
} from "lucide-react";
import {
  api,
  ApiError,
  dateLabel,
  dateShift,
  errorText,
  photoUrl,
  primary,
  send,
  today,
  uploadPhoto,
  useResource,
} from "./api";
import type { Entry, Settings } from "./api";
import {
  CameraSymbol,
  draftPayload,
  entryDraft,
  EntryFields,
  ErrorBanner,
  PageHeader,
  PanelHeading,
  PhotoView,
  SaveLabel,
  Toggle,
} from "./ui";

export default function Today({
  revision,
  onChange,
  settings,
  onSettings,
  onDay,
  onCalendar,
}: {
  revision: number;
  onChange: () => void;
  settings: Settings;
  onSettings: (s: Partial<Settings>) => Promise<void>;
  onDay: (date: string) => void;
  onCalendar: () => void;
}) {
  const date = today();
  const recent = useResource<{ entries: Entry[] }>(
    `/entries?start=${dateShift(date, -30)}&end=${date}&limit=40`,
    revision,
  );
  const [entry, setEntry] = useState<Entry | null>(null),
    [draft, setDraft] = useState(entryDraft()),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(false),
    [camera, setCamera] = useState(false),
    [starting, setStarting] = useState(false),
    [devices, setDevices] = useState<MediaDeviceInfo[]>([]),
    [device, setDevice] = useState(""),
    [captured, setCaptured] = useState<File | null>(null),
    [captureUrl, setCaptureUrl] = useState(""),
    [capturedAt, setCapturedAt] = useState(""),
    [capturedDate, setCapturedDate] = useState(""),
    [pendingMetadataDate, setPendingMetadataDate] = useState(""),
    [overlay, setOverlay] = useState(false),
    [opacity, setOpacity] = useState(0.35);
  const video = useRef<HTMLVideoElement>(null),
    stream = useRef<MediaStream | null>(null),
    fileInput = useRef<HTMLInputElement>(null),
    request = useRef(0),
    loadedDate = useRef(date),
    dirtyDraft = useRef(false);
  useEffect(() => {
    let active = true;
    if (loadedDate.current !== date) {
      loadedDate.current = date;
      setEntry(null);
      setNotice("");
      if (!captured && !pendingMetadataDate) {
        dirtyDraft.current = false;
        setDraft(entryDraft());
      }
    }
    void api<Entry>(`/entries/${date}`)
      .then((e) => {
        if (active) {
          setEntry(e);
          if (!dirtyDraft.current && !captured && !pendingMetadataDate)
            setDraft(entryDraft(e));
        }
      })
      .catch((e) => {
        if (!active) return;
        if (e instanceof ApiError && e.status === 404) {
          setEntry(null);
          if (!dirtyDraft.current && !captured && !pendingMetadataDate)
            setDraft(entryDraft());
        } else setError(errorText(e));
      });
    return () => {
      active = false;
    };
  }, [date, revision]);
  function stopCamera() {
    request.current++;
    stream.current?.getTracks().forEach((t) => t.stop());
    stream.current = null;
    setCamera(false);
    setStarting(false);
  }
  useEffect(
    () => () => {
      request.current++;
      stream.current?.getTracks().forEach((t) => t.stop());
    },
    [],
  );
  useEffect(() => {
    if (!captured) {
      setCaptureUrl("");
      return;
    }
    const url = URL.createObjectURL(captured);
    setCaptureUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [captured]);
  useEffect(() => {
    if (camera && video.current && stream.current) {
      video.current.srcObject = stream.current;
      void video.current
        .play()
        .catch(() => setError("相机已连接，请点击预览画面以开始播放。"));
    }
  }, [camera]);
  async function startCamera(id = device) {
    const token = ++request.current;
    setStarting(true);
    setError("");
    setNotice("");
    try {
      if (!navigator.mediaDevices?.getUserMedia)
        throw new Error(
          "当前环境无法访问摄像头。请在本机 localhost 或 HTTPS 中打开；也可以从本地导入。",
        );
      stream.current?.getTracks().forEach((t) => t.stop());
      const media = await navigator.mediaDevices.getUserMedia({
        video: id
          ? {
              deviceId: { exact: id },
              width: { ideal: 1920 },
              height: { ideal: 1080 },
            }
          : {
              facingMode: "user",
              width: { ideal: 1920 },
              height: { ideal: 1080 },
            },
        audio: false,
      });
      if (token !== request.current) {
        media.getTracks().forEach((t) => t.stop());
        return;
      }
      stream.current = media;
      if (video.current) {
        video.current.srcObject = media;
        void video.current.play().catch(() => {});
      }
      setDevices(
        (await navigator.mediaDevices.enumerateDevices()).filter(
          (d) => d.kind === "videoinput",
        ),
      );
      setDevice(media.getVideoTracks()[0]?.getSettings().deviceId || id);
      setCaptured(null);
      setCamera(true);
    } catch (e) {
      if (token === request.current) {
        setCamera(false);
        setError(
          e instanceof DOMException && e.name === "NotAllowedError"
            ? "摄像头权限未开启。请在浏览器地址栏允许相机，或直接导入照片。"
            : e instanceof DOMException && e.name === "NotFoundError"
              ? "没有找到可用摄像头。连接摄像头后重试，或从本地导入。"
              : errorText(e),
        );
      }
    } finally {
      if (token === request.current) setStarting(false);
    }
  }
  async function capture() {
    const el = video.current;
    if (!el?.videoWidth) {
      setError("相机画面尚未就绪，请稍后再拍。");
      return;
    }
    const canvas = document.createElement("canvas");
    canvas.width = el.videoWidth;
    canvas.height = el.videoHeight;
    const ctx = canvas.getContext("2d");
    if (!ctx) {
      setError("当前浏览器无法生成照片，请尝试导入。");
      return;
    }
    if (settings.mirror_output) {
      ctx.translate(canvas.width, 0);
      ctx.scale(-1, 1);
    }
    ctx.drawImage(el, 0, 0);
    const time = new Date().toISOString();
    const blob = await new Promise<Blob | null>((resolve) =>
      canvas.toBlob(resolve, "image/png"),
    );
    if (!blob) {
      setError("未能生成照片，请重拍。");
      return;
    }
    setCaptured(
      new File([blob], `dayframe-${date}.png`, { type: "image/png" }),
    );
    setCapturedAt(time);
    setCapturedDate(date);
    stopCamera();
  }
  async function save(file = captured, source: "camera" | "import" = "camera") {
    setError("");
    setNotice("");
    setBusy(true);
    const targetDate = file
      ? source === "camera"
        ? capturedDate || date
        : date
      : pendingMetadataDate || date;
    try {
      let saved = entry;
      if (file) {
        saved = await uploadPhoto(
          targetDate,
          file,
          source,
          source === "camera" ? capturedAt : undefined,
        );
        if (targetDate === date) setEntry(saved);
        setPendingMetadataDate(targetDate);
        setCaptured(null);
      }
      if (!saved && !pendingMetadataDate)
        throw new Error("请先拍摄或选择一张照片。");
      try {
        const value = await send<Entry>(
          `/entries/${targetDate}`,
          draftPayload(draft),
          "PUT",
        );
        if (targetDate === date) setEntry(value);
        else setDraft(entryDraft());
        dirtyDraft.current = false;
        setPendingMetadataDate("");
        setCapturedDate("");
        setNotice(
          targetDate !== date
            ? `照片已补记到 ${targetDate}，记录日期与实际拍摄时间均已保留。`
            : file
              ? "今天的一帧，已经好好保存。"
              : "今天的记录已更新。",
        );
      } catch (e) {
        void recent.reload();
        throw new Error(
          `照片已保存，但文字信息未完成：${errorText(e)}。请再次点击保存。`,
        );
      }
      onChange();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  }
  const previous = recent.data?.entries.find(
    (e) => e.record_date < date && primary(e) && !primary(e)?.missing,
  );
  const current = primary(entry);
  const missingRecord =
    entry?.status === "recorded" && (!current || current.missing);
  const dates = Array.from({ length: 7 }, (_, i) => dateShift(date, i - 6));
  return (
    <>
      <PageHeader
        title="今天，留下一帧"
        subtitle="用一张照片，一段文字，记录此刻的生活。"
      >
        <span
          className={`today-state ${missingRecord ? "missing" : current ? "complete" : ""}`}
        >
          <span />
          {missingRecord
            ? "原图缺失，待恢复"
            : current
              ? "今天已记录"
              : entry?.status === "skipped"
                ? "今天休息一下"
                : "尚未记录"}
        </span>
      </PageHeader>
      <ErrorBanner
        message={error || recent.error}
        retry={recent.error ? () => void recent.reload() : undefined}
      />
      {notice ? (
        <p className="success" role="status">
          <Check size={16} />
          {notice}
        </p>
      ) : null}
      <div className="today-grid">
        <section className="camera-panel">
          <PanelHeading
            icon={<Camera size={25} />}
            title="拍一张照片"
            subtitle="定格此刻的光影，留住今天的模样。"
          />
          <div
            className={`camera-stage ${camera || captureUrl || current ? "has-media" : ""}`}
          >
            {camera ? (
              <>
                <video
                  ref={video}
                  className={settings.mirror_preview ? "mirrored" : ""}
                  muted
                  playsInline
                  autoPlay
                  onClick={() => void video.current?.play()}
                />
                {overlay && previous ? (
                  <img
                    alt="仅用于构图的参考叠层"
                    className={`camera-overlay ${settings.mirror_preview ? "mirrored" : ""}`}
                    src={photoUrl(previous.primary_photo_id!)}
                    style={{ opacity }}
                  />
                ) : null}
                <div className="camera-live">
                  <span className="live-dot" />
                  相机预览 · 尚未保存
                </div>
                <button
                  className="camera-stop icon-button"
                  aria-label="关闭相机"
                  onClick={stopCamera}
                >
                  <CameraOff size={18} />
                </button>
              </>
            ) : captureUrl ? (
              <>
                <img
                  src={captureUrl}
                  className="captured-image"
                  alt="刚刚拍摄的照片，尚未保存"
                />
                <span className="camera-live">
                  {capturedDate && capturedDate !== date
                    ? `${capturedDate} 的照片 · 尚未保存`
                    : "照片预览 · 尚未保存"}
                </span>
              </>
            ) : current ? (
              <>
                <PhotoView photo={current} original alt="今天的主照片" />
                <span className="camera-live">
                  {current.missing ? "原图缺失，文字记录仍保留" : "今天已记录"}
                </span>
              </>
            ) : (
              <div className="camera-empty">
                <CameraSymbol />
                <h3>还没有照片</h3>
                <p>打开摄像头拍摄，或从本地导入照片</p>
              </div>
            )}
            {camera || captureUrl || current ? (
              <div className="camera-actions">
                {camera ? (
                  <button
                    className="shutter"
                    onClick={() => void capture()}
                    aria-label="拍下今天"
                  >
                    <span />
                  </button>
                ) : (
                  <>
                    <button
                      onClick={() => void startCamera()}
                      disabled={starting || busy}
                    >
                      <RefreshCw size={16} />
                      {captureUrl ? "重拍" : "再拍一张"}
                    </button>
                    <button
                      disabled={busy}
                      onClick={() => fileInput.current?.click()}
                    >
                      <Upload size={16} />
                      导入照片
                    </button>
                    {current ? (
                      <button onClick={() => onDay(date)}>管理今日照片</button>
                    ) : null}
                  </>
                )}
              </div>
            ) : null}
          </div>
          {!camera && !captureUrl && !current ? (
            <div className="camera-entry-actions">
              <button
                className="primary"
                disabled={starting}
                onClick={() => void startCamera()}
              >
                <Camera size={20} />
                {starting ? "正在连接相机…" : "打开摄像头"}
              </button>
              <button
                disabled={busy}
                onClick={() => fileInput.current?.click()}
              >
                <ImagePlus size={20} />
                导入照片
              </button>
            </div>
          ) : null}
          <div className="camera-controls">
            <Toggle
              checked={settings.mirror_preview}
              onChange={(v) =>
                void onSettings({ mirror_preview: v }).catch((e) =>
                  setError(errorText(e)),
                )
              }
            >
              预览镜像
            </Toggle>
            <Toggle
              checked={settings.mirror_output}
              onChange={(v) =>
                void onSettings({ mirror_output: v }).catch((e) =>
                  setError(errorText(e)),
                )
              }
            >
              输出镜像
            </Toggle>
          </div>
          <p className="camera-hint">
            预览与保存方向独立设置；导入文件不翻转、不压缩。
          </p>
          {camera ? (
            <div className="camera-options">
              <label>
                摄像头
                <select
                  value={device}
                  onChange={(e) => {
                    setDevice(e.target.value);
                    void startCamera(e.target.value);
                  }}
                >
                  {devices.map((d, i) => (
                    <option key={d.deviceId} value={d.deviceId}>
                      {d.label || `摄像头 ${i + 1}`}
                    </option>
                  ))}
                </select>
              </label>
              {previous ? (
                <>
                  <Toggle checked={overlay} onChange={setOverlay}>
                    上一帧对齐叠层
                  </Toggle>
                  {overlay ? (
                    <label>
                      透明度
                      <input
                        aria-label="叠层透明度"
                        type="range"
                        min="0.05"
                        max="0.8"
                        step="0.05"
                        value={opacity}
                        onChange={(e) => setOpacity(Number(e.target.value))}
                      />
                    </label>
                  ) : null}
                </>
              ) : (
                <span className="small muted">
                  保存第一张照片后即可使用对齐叠层。
                </span>
              )}
            </div>
          ) : null}
          <input
            className="sr-only"
            ref={fileInput}
            type="file"
            accept="image/*,.heic,.heif"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) void save(file, "import");
            }}
            disabled={busy}
          />
        </section>
        <form
          className="story-panel"
          onSubmit={(e) => {
            e.preventDefault();
            void save();
          }}
        >
          <PanelHeading
            icon={<NotebookPen size={25} />}
            title="写下今天"
            subtitle="记录此刻的心情、想法或发生的事情。"
          />
          {captured && capturedDate && capturedDate !== date ? (
            <p className="small muted">
              这张未保存的照片将保留在拍摄时的记录日期 {capturedDate}
              。保存后可在日历里查看。
            </p>
          ) : null}
          {pendingMetadataDate ? (
            <p className="small muted">
              照片已存入 {pendingMetadataDate}，文字信息等待保存。
            </p>
          ) : null}
          <EntryFields
            draft={draft}
            onChange={(value) => {
              dirtyDraft.current = true;
              setDraft(value);
            }}
            disabled={busy}
          />
          <button
            className="primary full"
            disabled={busy || (!captured && !entry && !pendingMetadataDate)}
          >
            <SaveLabel busy={busy}>
              {pendingMetadataDate
                ? "重试保存文字"
                : captured && capturedDate !== date
                  ? `补记 ${capturedDate} 的一帧`
                  : captured
                    ? "保存今天的一帧"
                    : "保存记录"}
            </SaveLabel>
          </button>
          {entry && !captured ? (
            <p className="small muted">
              新照片将作为附加照片保留。更换主照片需要单独确认。
            </p>
          ) : null}
        </form>
      </div>
      <section className="recent-section">
        <header className="section-heading">
          <h2>
            <Clock3 size={23} />
            最近七天
          </h2>
          <button className="text-button" onClick={onCalendar}>
            查看完整日历 <ChevronRight size={16} />
          </button>
        </header>
        <div className="recent-strip">
          {dates.map((d) => {
            const e = recent.data?.entries.find((e) => e.record_date === d);
            return (
              <button
                className={`recent-day ${d === date ? "is-today" : ""}`}
                key={d}
                onClick={() => onDay(d)}
              >
                <span>{dateLabel(d, { month: "long", day: "numeric" })}</span>
                <small>{dateLabel(d, { weekday: "long" })}</small>
                <div className="recent-image">
                  {primary(e) ? (
                    <PhotoView photo={primary(e)} alt={`${d} 的照片`} />
                  ) : (
                    <div className="recent-empty">
                      <Plus size={21} />
                      <span>
                        {e?.status === "skipped" ? "休息日" : "暂无记录"}
                      </span>
                    </div>
                  )}
                  {e?.status === "skipped" ? (
                    <span className="rest-label">休息日</span>
                  ) : null}
                </div>
              </button>
            );
          })}
        </div>
      </section>
      {!recent.loading && !recent.data?.entries.length ? (
        <div className="gentle-note">
          <Square size={14} />
          从今天开始，慢慢收藏每一天的自己。
        </div>
      ) : null}
    </>
  );
}
