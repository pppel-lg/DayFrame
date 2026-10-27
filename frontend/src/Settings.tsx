import { useEffect, useState } from "react";
import {
  Archive,
  Bell,
  Check,
  Database,
  Download,
  HardDrive,
  Loader2,
  QrCode,
  RefreshCw,
  ShieldCheck,
  Smartphone,
  X,
  FolderOpen,
  LockKeyhole,
  EyeOff,
  WifiOff,
} from "lucide-react";
import { api, errorText, send, today, useResource } from "./api";
import type { Settings as SettingsType, Status } from "./api";
import type { RunJob } from "./Memories";
import { ErrorBanner, Loading, PageHeader, Toggle } from "./ui";
import { chooseDirectory, isDesktop, restartDesktop } from "./desktop";
import type { DesktopStatus } from "./desktop";

type Pairing = {
  active: boolean;
  pending: { upload_id: string; record_date: string; filename: string }[];
};
type PairCode = { url: string; code: string; expires_at: string; port: number };
export default function Settings({
  status,
  onSettings,
  revision,
  onChange,
  runJob,
}: {
  status: Status;
  onSettings: (s: Partial<SettingsType>) => Promise<void>;
  revision: number;
  onChange: () => void;
  runJob: RunJob;
}) {
  const [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(""),
    [restoreName, setRestoreName] = useState(""),
    [target, setTarget] = useState(`restored-${today()}`),
    [restorePath, setRestorePath] = useState(""),
    [year, setYear] = useState(new Date().getFullYear()),
    [baseUrl, setBaseUrl] = useState(""),
    [code, setCode] = useState<PairCode | null>(null),
    [qr, setQr] = useState(""),
    [desktop, setDesktop] = useState<DesktopStatus | null>(null),
    [paths, setPaths] = useState({
      archive: status.archive_path,
      backups: status.backup_path,
    }),
    [permission, setPermission] = useState(
      typeof Notification !== "undefined"
        ? Notification.permission
        : "unsupported",
    );
  const backups = useResource<{
      backups: { name: string; created_at_utc: string; file_count: number }[];
    }>("/backups", revision),
    pairing = useResource<Pairing>("/pairing", revision);
  const native = isDesktop();
  useEffect(() => {
    if (!native) return;
    let active = true;
    void api<DesktopStatus>("/desktop")
      .then((value) => {
        if (active) {
          setDesktop(value);
          setPaths(value.paths);
        }
      })
      .catch((e) => {
        if (active) setError(errorText(e));
      });
    return () => {
      active = false;
    };
  }, [native]);
  useEffect(() => {
    const id = window.setInterval(() => void pairing.reload(), 5000);
    return () => window.clearInterval(id);
  }, [pairing.reload]);
  useEffect(() => {
    if (!code) {
      setQr("");
      return;
    }
    let active = true;
    void import("qrcode")
      .then((m) =>
        m.toDataURL(code.url, {
          width: 256,
          margin: 2,
          color: { dark: "#253e32", light: "#ffffff" },
        }),
      )
      .then((url) => {
        if (active) setQr(url);
      })
      .catch((e) => setError(errorText(e)));
    return () => {
      active = false;
    };
  }, [code]);
  async function action(name: string, task: () => Promise<void>) {
    setBusy(name);
    setError("");
    setNotice("");
    try {
      await task();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy("");
    }
  }
  async function pref(value: Partial<SettingsType>) {
    await action("settings", () => onSettings(value));
  }
  return (
    <>
      <PageHeader
        title="设置"
        subtitle="自定义 DayFrame 的使用方式，让记录更贴合你的生活。"
      />
      <ErrorBanner message={error} />
      {notice ? (
        <p className="success" role="status">
          <Check size={16} />
          {notice}
        </p>
      ) : null}
      <div className="settings-stack">
        <div className="settings-column">
          <section className="settings-section storage-settings">
            <header>
              <HardDrive size={21} />
              <div>
                <h2>本地归档与备份路径</h2>
                <p>照片、文字和所有记录都保存在你的设备中。</p>
              </div>
            </header>
            <div className="settings-body">
              {native ? (
                <>
                  <div className="path-editor">
                    {(
                      [
                        ["archive", "归档目录"],
                        ["backups", "备份目录"],
                      ] as const
                    ).map(([key, label]) => (
                      <label className="field" key={key}>
                        {label}
                        <div className="path-input">
                          <input
                            aria-label={label}
                            value={paths[key]}
                            disabled={!!busy || !desktop}
                            onChange={(e) =>
                              setPaths((previous) => ({
                                ...previous,
                                [key]: e.target.value,
                              }))
                            }
                          />
                          <button
                            type="button"
                            aria-label={`选择${label}`}
                            disabled={!!busy || !desktop}
                            onClick={() =>
                              void action("directory", async () => {
                                const path = await chooseDirectory();
                                if (path)
                                  setPaths((previous) => ({
                                    ...previous,
                                    [key]: path,
                                  }));
                              })
                            }
                          >
                            <FolderOpen size={19} />
                            更改…
                          </button>
                        </div>
                      </label>
                    ))}
                  </div>
                  <div className="button-row">
                    <button
                      className="primary"
                      disabled={
                        !!busy ||
                        !desktop ||
                        (paths.archive === desktop.paths.archive &&
                          paths.backups === desktop.paths.backups)
                      }
                      onClick={() =>
                        void action("paths", async () => {
                          const value = await send<DesktopStatus>(
                            "/desktop/paths",
                            paths,
                            "PUT",
                          );
                          setDesktop(value);
                          setNotice(
                            "目录设置已保存，重新启动后生效。现有文件不会自动移动。",
                          );
                        })
                      }
                    >
                      保存目录设置
                    </button>
                    {desktop?.pending_restart ? (
                      <button
                        disabled={!!busy}
                        onClick={() => void action("restart", restartDesktop)}
                      >
                        <RefreshCw size={17} />
                        立即重新启动
                      </button>
                    ) : null}
                  </div>
                  <p className="small muted">
                    目录更改将在重新启动后生效；现有文件不会移动或覆盖。备份请保存在归档目录以外。
                  </p>
                </>
              ) : (
                <>
                  <div className="path-row">
                    <span>当前归档目录</span>
                    <code>{status.archive_path}</code>
                  </div>
                  <div className="path-row">
                    <span>独立备份目录</span>
                    <code>{status.backup_path}</code>
                  </div>
                </>
              )}
              <div className="settings-summary">
                <span>{status.photo_count} 张照片</span>
                <span>{status.entry_count} 条记录</span>
                <span>开始于 {status.archive.archive_start_date}</span>
              </div>
              {!native ? (
                <p className="small muted">
                  Docker 的 /data 与 /backups
                  应挂载到独立持久目录。更换归档位置请先备份，再修改宿主机挂载路径。
                </p>
              ) : null}
            </div>
          </section>
          <section className="settings-section reminder-settings">
            <header>
              <Bell size={21} />
              <div>
                <h2>温和提醒</h2>
                <p>只提醒，不会自动打开摄像头。</p>
              </div>
            </header>
            <div className="settings-body">
              <div className="setting-row">
                <div>
                  <strong>每日记录提醒</strong>
                  <p>
                    此页面打开时，在设定时间之后提醒一次；当天已记录则不提醒。
                  </p>
                </div>
                <Toggle
                  checked={status.settings.reminder_enabled}
                  onChange={(v) => void pref({ reminder_enabled: v })}
                  disabled={!!busy}
                >
                  开启
                </Toggle>
              </div>
              <label className="setting-row">
                <span>提醒时间</span>
                <input
                  type="time"
                  value={status.settings.reminder_time}
                  disabled={!!busy}
                  onChange={(e) => void pref({ reminder_time: e.target.value })}
                />
              </label>
              <div className="setting-row">
                <div>
                  <strong>系统通知</strong>
                  <p>
                    {permission === "granted"
                      ? "已允许通知"
                      : permission === "denied"
                        ? "通知已被浏览器阻止，可在地址栏权限中修改"
                        : permission === "unsupported"
                          ? "当前浏览器不支持系统通知"
                          : "允许后可在页面打开时显示系统通知"}
                  </p>
                </div>
                <button
                  disabled={
                    permission === "unsupported" || permission === "granted"
                  }
                  onClick={() =>
                    void action("notifications", async () => {
                      setPermission(await Notification.requestPermission());
                    })
                  }
                >
                  允许通知
                </button>
              </div>
              {!native ? (
                <div className="setting-row">
                  <div>
                    <strong>Windows 登录启动</strong>
                    <p>
                      请使用项目附带的 Windows 启动脚本在宿主机配置。Docker
                      页面无法更改系统登录项。
                    </p>
                  </div>
                </div>
              ) : null}
            </div>
          </section>
          <section className="settings-section capture-settings">
            <header>
              <Archive size={21} />
              <div>
                <h2>拍摄与日历</h2>
                <p>预览方向不改变导入原文件。</p>
              </div>
            </header>
            <div className="settings-body">
              <div className="setting-row">
                <span>镜像相机预览</span>
                <Toggle
                  checked={status.settings.mirror_preview}
                  disabled={!!busy}
                  onChange={(v) => void pref({ mirror_preview: v })}
                >
                  开启
                </Toggle>
              </div>
              <div className="setting-row">
                <span>新拍照片以镜像方向保存</span>
                <Toggle
                  checked={status.settings.mirror_output}
                  disabled={!!busy}
                  onChange={(v) => void pref({ mirror_output: v })}
                >
                  开启
                </Toggle>
              </div>
              <div className="setting-row">
                <span>每周从星期一开始</span>
                <Toggle
                  checked={status.settings.week_starts_monday}
                  disabled={!!busy}
                  onChange={(v) => void pref({ week_starts_monday: v })}
                >
                  开启
                </Toggle>
              </div>
            </div>
          </section>
          <section
            className="settings-section tools-settings"
            id="data-settings"
          >
            <header>
              <ShieldCheck size={21} />
              <div>
                <h2>维护与工具</h2>
                <p>备份到归档以外的位置；定期校验，才能放心保存。</p>
              </div>
            </header>
            <div className="settings-body">
              <div className="button-row">
                <button disabled={!!busy} onClick={() => void runJob("verify")}>
                  <ShieldCheck size={16} />
                  完整性校验
                </button>
                <button
                  disabled={!!busy}
                  className="primary"
                  onClick={() => void runJob("backup")}
                >
                  <Database size={16} />
                  立即备份
                </button>
                <button
                  disabled={!!busy}
                  onClick={() => {
                    if (
                      window.confirm(
                        "从原始文件和 JSON 元数据重建索引？此操作不会改写原始照片。",
                      )
                    )
                      void runJob("rebuild");
                  }}
                >
                  <RefreshCw size={16} />
                  重建索引
                </button>
              </div>
              <ErrorBanner
                message={backups.error}
                retry={() => void backups.reload()}
              />
              {backups.loading ? (
                <Loading />
              ) : !backups.data?.backups.length ? (
                <p className="muted backup-empty">
                  还没有备份。先为现在的档案留一个安全副本。
                </p>
              ) : (
                <form
                  className="restore-form"
                  onSubmit={(e) => {
                    e.preventDefault();
                    if (
                      !window.confirm(
                        "将备份恢复到一个新目录？当前归档保持不变，完成后会显示新目录路径。",
                      )
                    )
                      return;
                    void action("restore", async () => {
                      const result = await send<{ path: string }>("/restore", {
                        name: restoreName,
                        target_name: target,
                        confirmed: true,
                      });
                      setRestorePath(result.path);
                      setNotice(
                        native
                          ? "备份已恢复到新目录。核对后可在上方选择归档目录。"
                          : "备份已恢复到新目录。请核对后手动切换归档挂载。",
                      );
                    });
                  }}
                >
                  <h3>从备份恢复到新目录</h3>
                  <label className="field">
                    选择备份
                    <select
                      required
                      value={restoreName}
                      onChange={(e) => setRestoreName(e.target.value)}
                    >
                      <option value="">请选择一个备份</option>
                      {backups.data.backups.map((b) => (
                        <option key={b.name} value={b.name}>
                          {b.name} · {b.file_count} 个文件
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="field">
                    新目录名称
                    <input
                      required
                      pattern="[a-zA-Z0-9_-]+"
                      title="使用英文字母、数字、下划线或短横线"
                      value={target}
                      onChange={(e) => setTarget(e.target.value)}
                    />
                  </label>
                  <button disabled={!!busy}>
                    {busy === "restore" ? (
                      <Loader2 size={16} className="spin" />
                    ) : (
                      <Download size={16} />
                    )}
                    恢复到新目录
                  </button>
                </form>
              )}
              {restorePath ? (
                <div className="restore-result" role="status">
                  <strong>已恢复的位置</strong>
                  <code>{restorePath}</code>
                  <p>当前运行的归档没有自动切换。</p>
                </div>
              ) : null}
              <div className="calendar-export">
                <label>
                  日历年份
                  <input
                    type="number"
                    min="1900"
                    max="2200"
                    value={year}
                    onChange={(e) => setYear(Number(e.target.value))}
                  />
                </label>
                <button
                  onClick={() => void runJob("export_calendar", { year })}
                >
                  <Download size={16} />
                  导出 CSV 与离线日历
                </button>
              </div>
              <p className="small muted">
                原始照片和 sidecar
                元数据包含在完整备份里，可复制到另一台电脑。导出与校验状态见页面下方的任务列表。
              </p>
            </div>
          </section>
        </div>
        <div className="settings-column">
          <section className="settings-section pairing-settings">
            <header>
              <Smartphone size={21} />
              <div>
                <h2>手机临时配对</h2>
                <p>仅在同一局域网内临时开启，每张上传都需要你在电脑上批准。</p>
              </div>
            </header>
            <div className="settings-body">
              <ErrorBanner
                message={pairing.error}
                retry={() => void pairing.reload()}
              />
              {!code ? (
                <div className="pair-intro">
                  <div className="pair-placeholder">
                    <QrCode size={64} />
                    <span>开启临时配对以生成二维码</span>
                  </div>
                  <div>
                    <h3>使用说明</h3>
                    <ol>
                      <li>手机和电脑连接同一局域网</li>
                      <li>点击开启临时配对</li>
                      <li>用手机扫描生成的二维码</li>
                      <li>上传后，在电脑批准照片</li>
                    </ol>
                  </div>
                </div>
              ) : null}
              <div className="setting-row">
                <div>
                  <strong>
                    {pairing.data?.active
                      ? "临时上传服务已开启"
                      : "临时上传服务未开启"}
                  </strong>
                  <p>配对凭证约十分钟后过期。照片先进入待批准区。</p>
                </div>
                {pairing.data?.active ? (
                  <button
                    className="danger"
                    disabled={!!busy}
                    onClick={() =>
                      void action("pairing", async () => {
                        await api("/pairing", { method: "DELETE" });
                        setCode(null);
                        await pairing.reload();
                        setNotice("手机上传服务已关闭。");
                      })
                    }
                  >
                    <X size={16} />
                    关闭服务
                  </button>
                ) : (
                  <button
                    className="primary"
                    disabled={!!busy}
                    onClick={() =>
                      void action("pairing", async () => {
                        const value = await send<PairCode>(
                          "/pairing",
                          baseUrl ? { base_url: baseUrl } : {},
                        );
                        setCode(value);
                        await pairing.reload();
                      })
                    }
                  >
                    <QrCode size={16} />
                    开启临时配对
                  </button>
                )}
              </div>
              {!pairing.data?.active ? (
                <label className="field">
                  电脑的局域网地址 <span className="optional">可选</span>
                  <input
                    placeholder="例如：http://192.168.1.10:8766"
                    value={baseUrl}
                    onChange={(e) => setBaseUrl(e.target.value)}
                  />
                  <small className="muted">
                    手机无法访问 localhost；需要电脑在 Wi-Fi 中的 IP
                    地址，并允许端口 8766。
                  </small>
                </label>
              ) : null}
              {code && pairing.data?.active ? (
                <div className="pair-code">
                  {qr ? (
                    <img src={qr} alt="手机配对二维码，包含临时上传凭证" />
                  ) : (
                    <Loading />
                  )}
                  <div>
                    <h3>用手机相机扫码</h3>
                    <p>
                      配对码 <strong>{code.code}</strong>
                    </p>
                    <p className="small muted">
                      有效至{" "}
                      {new Date(code.expires_at).toLocaleTimeString("zh-CN")}
                    </p>
                    <a
                      className="text-button"
                      href={code.url}
                      target="_blank"
                      rel="noreferrer"
                    >
                      打开手机上传页
                    </a>
                    <p className="small muted">
                      二维码在本地生成，不会发送给第三方。
                    </p>
                  </div>
                </div>
              ) : null}
              {pairing.data?.active && !code ? (
                <p className="small muted">
                  当前服务仍在运行。若需要新的二维码，请先关闭再开启。
                </p>
              ) : null}
              <h3>
                待批准上传{" "}
                <span className="muted">
                  {pairing.data?.pending.length || 0}
                </span>
              </h3>
              {pairing.data?.pending.length ? (
                <div className="pending-list">
                  {pairing.data.pending.map((item) => (
                    <div className="pending-row" key={item.upload_id}>
                      <div>
                        <strong>{item.filename}</strong>
                        <small>记录日期 {item.record_date}</small>
                      </div>
                      <div className="button-row">
                        <button
                          className="primary"
                          disabled={!!busy}
                          onClick={() =>
                            void action("approve", async () => {
                              await send("/pairing/approve", {
                                upload_id: item.upload_id,
                                confirmed: true,
                              });
                              await pairing.reload();
                              onChange();
                              setNotice("手机照片已保存到归档。");
                            })
                          }
                        >
                          <Check size={16} />
                          批准
                        </button>
                        <button
                          disabled={!!busy}
                          onClick={() =>
                            void action("reject", async () => {
                              await api(
                                `/pairing/pending/${encodeURIComponent(item.upload_id)}`,
                                { method: "DELETE" },
                              );
                              await pairing.reload();
                            })
                          }
                        >
                          拒绝
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="small muted">没有待批准的照片。</p>
              )}
            </div>
          </section>
          <section className="settings-section privacy-settings">
            <header>
              <ShieldCheck size={23} />
              <div>
                <h2>安全与隐私</h2>
              </div>
            </header>
            <div className="settings-body">
              <div className="privacy-item">
                <LockKeyhole size={23} />
                <div>
                  <strong>本地存储</strong>
                  <p>所有记录保存在你的设备上，不会上传到云端。</p>
                </div>
              </div>
              <div className="privacy-item">
                <EyeOff size={23} />
                <div>
                  <strong>无数据收集</strong>
                  <p>无需账号，不包含广告、追踪或云端照片分析。</p>
                </div>
              </div>
              <div className="privacy-item">
                <WifiOff size={23} />
                <div>
                  <strong>离线可用</strong>
                  <p>日常记录无需网络。请妥善保管归档与备份磁盘。</p>
                </div>
              </div>
            </div>
          </section>
        </div>
      </div>
    </>
  );
}
