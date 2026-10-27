import { Component, useCallback, useEffect, useRef, useState } from "react";
import type { ErrorInfo, ReactNode } from "react";
import {
  ArrowDownToLine,
  Bell,
  CalendarDays,
  Check,
  ChevronDown,
  ChevronUp,
  CircleAlert,
  Frame,
  HardDrive,
  Home,
  Loader2,
  Mail,
  MapPin,
  Menu,
  Image as ImageIcon,
  ChartNoAxesColumnIncreasing,
  List,
  Settings as SettingsIcon,
  ShieldCheck,
  X,
} from "lucide-react";
import { api, errorText, primary, send, today, useResource } from "./api";
import type { Entry, Job, Settings as SettingsType, Status } from "./api";
import Today from "./Today";
import DayDetail from "./DayDetail";
import { Calendar, Timeline } from "./Archive";
import { Locations, Memories, Report } from "./Memories";
import Letters from "./Letters";
import Settings from "./Settings";
import { ErrorBanner, LeafBranch, Loading, SproutMark } from "./ui";

const pages = [
  { id: "today", label: "今日", icon: Home },
  { id: "calendar", label: "日历", icon: CalendarDays },
  { id: "timeline", label: "时间轴", icon: List },
  { id: "memories", label: "回忆", icon: ImageIcon },
  { id: "locations", label: "足迹", icon: MapPin },
  { id: "letters", label: "未来信件", icon: Mail },
  { id: "report", label: "年度报告", icon: ChartNoAxesColumnIncreasing },
  { id: "settings", label: "设置", icon: SettingsIcon },
];
const names: Record<string, string> = {
  verify: "档案完整性校验",
  backup: "独立备份",
  rebuild: "重建索引",
  export_calendar: "导出日历",
  report: "生成年度报告",
  video: "生成延时视频",
};
const route = () =>
  pages.some((p) => p.id === location.hash.slice(1))
    ? location.hash.slice(1)
    : "today";
function JobPanel({
  jobs,
  setJobs,
  onChange,
}: {
  jobs: Job[];
  setJobs: React.Dispatch<React.SetStateAction<Job[]>>;
  onChange: () => void;
}) {
  const [expanded, setExpanded] = useState(true),
    [error, setError] = useState("");
  const active = jobs.filter(
    (j) => j.status === "queued" || j.status === "running",
  );
  const activeKey = active.map((j) => j.job_id).join(",");
  useEffect(() => {
    if (!activeKey) return;
    let stopped = false;
    const ids = activeKey.split(",");
    const poll = async () => {
      const results = await Promise.allSettled(
        ids.map((id) => api<Job>(`/jobs/${id}`)),
      );
      if (stopped) return;
      const updates: Job[] = [];
      let changed = false;
      for (const r of results) {
        if (r.status === "fulfilled") {
          updates.push(r.value);
          if (["success", "failed", "cancelled"].includes(r.value.status))
            changed = true;
        } else setError(errorText(r.reason));
      }
      setJobs((previous) =>
        previous.map(
          (job) => updates.find((u) => u.job_id === job.job_id) || job,
        ),
      );
      if (changed) onChange();
    };
    void poll();
    const id = setInterval(() => void poll(), 1500);
    return () => {
      stopped = true;
      clearInterval(id);
    };
  }, [activeKey, setJobs, onChange]);
  if (!jobs.length) return null;
  return (
    <aside className="job-panel" aria-label="后台任务">
      <button className="job-toggle" onClick={() => setExpanded((v) => !v)}>
        <span>
          {active.length ? (
            <Loader2 size={17} className="spin" />
          ) : (
            <Check size={17} />
          )}
          归档任务 {active.length ? `· ${active.length} 项进行中` : ""}
        </span>
        {expanded ? <ChevronDown size={18} /> : <ChevronUp size={18} />}
      </button>
      {expanded ? (
        <div className="job-body">
          <ErrorBanner message={error} />
          {jobs.map((job) => (
            <div key={job.job_id} className="job-row">
              <div className="job-name">
                <span>{names[job.kind] || job.kind}</span>
                <span className={`job-status ${job.status}`}>
                  {
                    {
                      queued: "等待中",
                      running: "进行中",
                      success: "已完成",
                      failed: "失败",
                      cancelled: "已取消",
                    }[job.status]
                  }
                </span>
              </div>
              {job.status === "running" || job.status === "queued" ? (
                <>
                  <progress max={100} value={job.progress} />
                  <button
                    className="text-button small"
                    onClick={() =>
                      void send<Job>(`/jobs/${job.job_id}/cancel`, {})
                        .then((value) =>
                          setJobs((previous) =>
                            previous.map((j) =>
                              j.job_id === value.job_id ? value : j,
                            ),
                          ),
                        )
                        .catch((e) => setError(errorText(e)))
                    }
                  >
                    取消
                  </button>
                </>
              ) : null}
              {job.error ? (
                <p className="job-error" role="alert">
                  {job.error}
                </p>
              ) : null}
              {job.status === "success" && job.result ? (
                <>
                  <div className="job-result">
                    {typeof job.result.url === "string" &&
                    job.result.url.startsWith("/api/exports/") ? (
                      <a href={job.result.url} className="text-button" download>
                        <ArrowDownToLine size={15} />
                        打开或下载结果
                      </a>
                    ) : null}
                    {typeof job.result.csv_url === "string" &&
                    job.result.csv_url.startsWith("/api/exports/") ? (
                      <a
                        href={job.result.csv_url}
                        className="text-button"
                        download
                      >
                        <ArrowDownToLine size={15} />
                        下载 CSV 数据
                      </a>
                    ) : null}
                    {typeof job.result.name === "string" ? (
                      <p>备份：{job.result.name}</p>
                    ) : null}
                    {Array.isArray(job.result.issues) ? (
                      <p>
                        {job.result.issues.length
                          ? `发现 ${job.result.issues.length} 项问题，请查看详情。`
                          : "校验完成，未发现完整性问题。"}
                      </p>
                    ) : null}
                  </div>
                  <details>
                    <summary>查看结果详情</summary>
                    <pre>{JSON.stringify(job.result, null, 2)}</pre>
                  </details>
                </>
              ) : null}
            </div>
          ))}
        </div>
      ) : null}
    </aside>
  );
}
function App() {
  const [page, setPage] = useState(route),
    [mobile, setMobile] = useState(false),
    [revision, setRevision] = useState(0),
    [day, setDay] = useState<string | null>(null),
    [jobs, setJobs] = useState<Job[]>([]),
    [error, setError] = useState(""),
    [reminder, setReminder] = useState(false);
  const status = useResource<Status>("/status", revision);
  const refresh = useCallback(() => setRevision((v) => v + 1), []);
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>;
    const schedule = () => {
      const now = new Date();
      const midnight = new Date(
        now.getFullYear(),
        now.getMonth(),
        now.getDate() + 1,
      );
      timer = setTimeout(
        () => {
          refresh();
          schedule();
        },
        midnight.getTime() - now.getTime() + 500,
      );
    };
    schedule();
    return () => clearTimeout(timer);
  }, [refresh]);
  const reminded = useRef("");
  useEffect(() => {
    const listener = () => setPage(route());
    window.addEventListener("hashchange", listener);
    return () => window.removeEventListener("hashchange", listener);
  }, []);
  function navigate(value: string) {
    location.hash = value;
    setPage(value);
    setMobile(false);
    window.scrollTo({ top: 0, behavior: "instant" });
  }
  const updateSettings = useCallback(
    async (value: Partial<SettingsType>) => {
      const result = await send<SettingsType>("/settings", value, "PUT");
      status.setData((previous) =>
        previous ? { ...previous, settings: result } : previous,
      );
    },
    [status.setData],
  );
  const runJob = useCallback(
    async (kind: string, options: Record<string, unknown> = {}) => {
      setError("");
      try {
        const value = await send<{ job_id: string }>("/jobs", {
          kind,
          ...options,
        });
        setJobs((previous) => [
          { job_id: value.job_id, kind, status: "queued", progress: 0 },
          ...previous,
        ]);
      } catch (e) {
        setError(errorText(e));
      }
    },
    [],
  );
  const enabled = status.data?.settings.reminder_enabled,
    time = status.data?.settings.reminder_time;
  useEffect(() => {
    if (!enabled || !time) return;
    let active = true;
    async function check() {
      const date = today(),
        clock = new Date().toTimeString().slice(0, 5);
      if (clock < time! || reminded.current === date) return;
      try {
        if (localStorage.getItem("dayframe.reminder.v1") === date) return;
      } catch {
        /* storage optional */
      }
      try {
        const result = await api<{ entries: Entry[] }>(
          `/entries?start=${date}&end=${date}&limit=1`,
        );
        if (
          !active ||
          result.entries.some(
            (e) =>
              (primary(e) && !primary(e)?.missing) || e.status === "skipped",
          )
        )
          return;
        reminded.current = date;
        try {
          localStorage.setItem("dayframe.reminder.v1", date);
        } catch {
          /* storage optional */
        }
        setReminder(true);
        if (
          typeof Notification !== "undefined" &&
          Notification.permission === "granted"
        )
          new Notification("留下今天的一帧", {
            body: "有空的时候，给今天的自己留一张照片。",
            tag: "dayframe-daily",
          });
      } catch {
        /* don't mark a failed check as reminded */
      }
    }
    void check();
    const id = setInterval(() => void check(), 60000);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, [enabled, time]);
  return (
    <div className="app-shell">
      <button
        className="mobile-menu icon-button"
        aria-label="展开导航"
        onClick={() => setMobile((v) => !v)}
      >
        <Menu size={23} />
      </button>
      {mobile ? (
        <button
          className="sidebar-backdrop"
          aria-label="关闭导航"
          onClick={() => setMobile(false)}
        />
      ) : null}
      <aside className={`sidebar ${mobile ? "open" : ""}`}>
        <a
          href="#today"
          className="brand"
          aria-label="Dayframe 今日"
          onClick={() => setMobile(false)}
        >
          <SproutMark />
          <span>dayframe</span>
          <small>用影像记录生活</small>
        </a>
        <nav aria-label="主导航">
          {pages.map(({ id, label, icon: Icon }) => (
            <a
              href={`#${id}`}
              key={id}
              className={`nav-item ${page === id ? "active" : ""} ${id === "settings" ? "settings-nav" : ""}`}
              aria-current={page === id ? "page" : undefined}
              onClick={() => navigate(id)}
            >
              <Icon size={19} strokeWidth={1.7} />
              <span>{label}</span>
            </a>
          ))}
        </nav>
        <div className="sidebar-poem">
          <p>
            每一帧，
            <br />
            都是生活的答案。
          </p>
          <LeafBranch />
        </div>
        <div className="sidebar-bottom">
          <HardDrive size={17} />
          <div>
            仅存储在你的设备<span>本地保存，隐私安全</span>
          </div>
        </div>
      </aside>
      <main className="main">
        <ErrorBanner message={error} />
        {reminder ? (
          <div className="reminder-banner" role="status">
            <Bell size={18} />
            <span>有空的时候，留下今天的一帧。</span>
            <button
              onClick={() => {
                navigate("today");
                setReminder(false);
              }}
            >
              去记录
            </button>
            <button
              className="icon-button"
              aria-label="关闭提醒"
              onClick={() => setReminder(false)}
            >
              <X size={17} />
            </button>
          </div>
        ) : null}
        {status.loading && !status.data ? (
          <Loading />
        ) : status.error ? (
          <div className="connection-error">
            <CircleAlert size={34} />
            <h1>暂时连接不到本地档案</h1>
            <p>请确认 Dayframe 服务正在运行。</p>
            <ErrorBanner
              message={status.error}
              retry={() => void status.reload()}
            />
          </div>
        ) : status.data ? (
          <>
            {status.data.health.issues.length ? (
              <div className="health-warning">
                <ShieldCheck size={19} />
                <span>
                  档案检查发现 {status.data.health.issues.length}{" "}
                  项问题。照片记录仍然保留，请到设置运行完整性校验。
                </span>
                <button
                  className="text-button"
                  onClick={() => navigate("settings")}
                >
                  查看设置
                </button>
              </div>
            ) : null}
            {page === "today" ? (
              <Today
                revision={revision}
                onChange={refresh}
                settings={status.data.settings}
                onSettings={updateSettings}
                onDay={setDay}
                onCalendar={() => navigate("calendar")}
              />
            ) : page === "calendar" ? (
              <Calendar
                revision={revision}
                onDay={setDay}
                settings={status.data.settings}
              />
            ) : page === "timeline" ? (
              <Timeline revision={revision} onDay={setDay} />
            ) : page === "memories" ? (
              <Memories revision={revision} onDay={setDay} runJob={runJob} />
            ) : page === "locations" ? (
              <Locations revision={revision} onDay={setDay} />
            ) : page === "letters" ? (
              <Letters revision={revision} onChange={refresh} />
            ) : page === "report" ? (
              <Report revision={revision} runJob={runJob} onDay={setDay} />
            ) : (
              <Settings
                status={status.data}
                onSettings={updateSettings}
                revision={revision}
                onChange={refresh}
                runJob={runJob}
              />
            )}
            <footer className="page-footer">
              <Frame size={13} />
              <span>Dayframe · 慢慢记录，好好生活</span>
            </footer>
          </>
        ) : null}
      </main>
      {day ? (
        <DayDetail
          key={day}
          date={day}
          onClose={() => setDay(null)}
          onChange={refresh}
        />
      ) : null}
      <JobPanel jobs={jobs} setJobs={setJobs} onChange={refresh} />
    </div>
  );
}
export class ErrorBoundary extends Component<
  { children: ReactNode },
  { error: boolean }
> {
  state = { error: false };
  static getDerivedStateFromError() {
    return { error: true };
  }
  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Dayframe rendering error", error.name, info.componentStack);
  }
  render() {
    return this.state.error ? (
      <main className="fatal-error">
        <Frame size={32} />
        <h1>页面遇到了一点问题</h1>
        <p>已保存的档案仍在本地。刷新页面再试一次。</p>
        <button className="primary" onClick={() => location.reload()}>
          重新打开
        </button>
      </main>
    ) : (
      this.props.children
    );
  }
}
export default App;
