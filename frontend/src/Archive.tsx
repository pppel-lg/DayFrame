import { useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  Search,
} from "lucide-react";
import {
  dateLabel,
  dateShift,
  moodLabel,
  moods,
  primary,
  today,
  useResource,
} from "./api";
import type { Entry, Settings, Stats } from "./api";
import {
  Empty,
  ErrorBanner,
  Loading,
  PageHeader,
  PhotoView,
  StatsBar,
} from "./ui";

const monthStart = (year: number, month: number) =>
  `${year}-${String(month + 1).padStart(2, "0")}-01`;
const monthEnd = (year: number, month: number) =>
  dateShift(monthStart(month === 11 ? year + 1 : year, (month + 1) % 12), -1);
function MonthGrid({
  year,
  month,
  entries,
  onDay,
  monday,
  mini = false,
}: {
  year: number;
  month: number;
  entries: Entry[];
  onDay: (date: string) => void;
  monday: boolean;
  mini?: boolean;
}) {
  const first = monthStart(year, month);
  const weekday = new Date(`${first}T12:00:00`).getDay();
  const pad = monday ? (weekday + 6) % 7 : weekday;
  const count = new Date(year, month + 1, 0).getDate();
  const dates = Array.from(
    { length: mini ? Math.ceil((pad + count) / 7) * 7 : 42 },
    (_, i) => dateShift(first, i - pad),
  );
  const map = new Map(entries.map((e) => [e.record_date, e]));
  return (
    <div className={mini ? "mini-month" : "month-grid"}>
      <div className="weekdays">
        {(monday
          ? ["一", "二", "三", "四", "五", "六", "日"]
          : ["日", "一", "二", "三", "四", "五", "六"]
        ).map((d) => (
          <span key={d}>{mini ? d : `周${d}`}</span>
        ))}
      </div>
      <div className="date-grid">
        {dates.map((d) => {
          const entry = map.get(d),
            photo = primary(entry),
            valid = !!photo && !photo.missing,
            missing = entry?.status === "recorded" && !valid,
            outside = d.slice(0, 7) !== first.slice(0, 7),
            future = d > today();
          return (
            <button
              key={d}
              disabled={future || (mini && outside)}
              title={`${d} ${missing ? "原图缺失，待恢复" : valid ? "已记录" : entry?.status === "skipped" ? "已跳过" : "尚未记录"}`}
              className={`date-cell ${outside ? "outside" : ""} ${future ? "future" : ""} ${d === today() ? "current" : ""} ${missing ? "missing" : entry?.status || ""}`}
              onClick={() => onDay(d)}
            >
              <span className="date-number">{Number(d.slice(-2))}</span>
              {!mini && photo ? (
                <PhotoView photo={photo} alt={`${d} 的主照片`} />
              ) : null}
              {!mini && entry?.mood ? (
                <span className="calendar-mood">{moodLabel(entry.mood)}</span>
              ) : null}
              {!mini && entry?.status === "skipped" ? (
                <span className="calendar-skipped">休息日</span>
              ) : null}
              {mini && valid ? <span className="sr-only">已记录</span> : null}
              {missing ? (
                <span className={mini ? "sr-only" : "calendar-missing"}>
                  原图缺失
                </span>
              ) : null}
            </button>
          );
        })}
      </div>
    </div>
  );
}
export function Calendar({
  revision,
  onDay,
  settings,
}: {
  revision: number;
  onDay: (date: string) => void;
  settings: Settings;
}) {
  const now = new Date(),
    [year, setYear] = useState(now.getFullYear()),
    [month, setMonth] = useState(now.getMonth()),
    [view, setView] = useState<"month" | "year">("month");
  const start = view === "year" ? `${year}-01-01` : monthStart(year, month),
    end = view === "year" ? `${year}-12-31` : monthEnd(year, month);
  const entries = useResource<{ entries: Entry[] }>(
      `/entries?start=${start}&end=${end}&limit=400`,
      revision,
    ),
    stats = useResource<Stats>(
      `/stats?start=${start}&end=${end}&today=${today()}`,
      revision,
    );
  function step(direction: number) {
    if (view === "year") {
      setYear((y) => y + direction);
      return;
    }
    const d = new Date(year, month + direction, 1);
    setYear(d.getFullYear());
    setMonth(d.getMonth());
  }
  return (
    <>
      <PageHeader
        title="日子，一格一格"
        subtitle="有记录的日子值得珍藏，留白的日子也很好。"
      >
        <div className="segmented">
          <button
            className={view === "month" ? "active" : ""}
            onClick={() => setView("month")}
          >
            月历
          </button>
          <button
            className={view === "year" ? "active" : ""}
            onClick={() => setView("year")}
          >
            年历
          </button>
        </div>
      </PageHeader>
      <ErrorBanner
        message={entries.error || stats.error}
        retry={() => {
          void entries.reload();
          void stats.reload();
        }}
      />
      <StatsBar stats={stats.data} />
      <div className="calendar-toolbar">
        <div className="button-row">
          <button
            className="icon-button"
            aria-label="上一页日历"
            onClick={() => step(-1)}
          >
            <ChevronLeft size={20} />
          </button>
          <h2>
            {year}年{view === "month" ? `${month + 1}月` : ""}
          </h2>
          <button
            className="icon-button"
            aria-label="下一页日历"
            onClick={() => step(1)}
          >
            <ChevronRight size={20} />
          </button>
        </div>
        <button
          onClick={() => {
            setYear(now.getFullYear());
            setMonth(now.getMonth());
          }}
        >
          回到今天
        </button>
      </div>
      {entries.loading ? (
        <Loading />
      ) : view === "month" ? (
        <MonthGrid
          year={year}
          month={month}
          entries={entries.data?.entries || []}
          onDay={onDay}
          monday={settings.week_starts_monday}
        />
      ) : (
        <div className="year-grid">
          {Array.from({ length: 12 }, (_, i) => (
            <section key={i}>
              <button
                className="month-title"
                onClick={() => {
                  setMonth(i);
                  setView("month");
                }}
              >
                {i + 1}月 <ChevronRight size={13} />
              </button>
              <MonthGrid
                year={year}
                month={i}
                entries={entries.data?.entries || []}
                onDay={onDay}
                monday={settings.week_starts_monday}
                mini
              />
            </section>
          ))}
        </div>
      )}
      <div className="calendar-legend">
        <span>
          <i className="recorded" />
          已记录
        </span>
        <span>
          <i className="skipped" />
          已跳过
        </span>
        <span>
          <i />
          尚未记录
        </span>
        <span>未来日期不计入记录率</span>
      </div>
      <p className="small muted">
        记录率按归档开始日至今天计算。点击日期即可补记、编辑或管理照片。
      </p>
    </>
  );
}

type Filters = {
  year: string;
  month: string;
  mood: string;
  tag: string;
  q: string;
};
export function Timeline({
  revision,
  onDay,
}: {
  revision: number;
  onDay: (date: string) => void;
}) {
  const [filters, setFilters] = useState<Filters>({
      year: "",
      month: "",
      mood: "",
      tag: "",
      q: "",
    }),
    [applied, setApplied] = useState(filters),
    [offset, setOffset] = useState(0);
  const params = new URLSearchParams({ offset: String(offset), limit: "24" });
  if (applied.year) {
    params.set(
      "start",
      applied.month
        ? monthStart(Number(applied.year), Number(applied.month) - 1)
        : `${applied.year}-01-01`,
    );
    params.set(
      "end",
      applied.month
        ? monthEnd(Number(applied.year), Number(applied.month) - 1)
        : `${applied.year}-12-31`,
    );
  }
  if (applied.mood) params.set("mood", applied.mood);
  if (applied.tag) params.set("tag", applied.tag);
  if (applied.q) params.set("q", applied.q);
  const entries = useResource<{ entries: Entry[]; total: number }>(
    `/entries?${params}`,
    revision,
  );
  function change(key: keyof Filters, value: string) {
    setFilters({ ...filters, [key]: value });
  }
  return (
    <>
      <PageHeader
        title="沿着时间，看看自己"
        subtitle="每一帧和每一句话，都有它的位置。"
      />
      <form
        className="filter-bar"
        onSubmit={(e) => {
          e.preventDefault();
          setOffset(0);
          setApplied({ ...filters });
        }}
      >
        <label>
          年份
          <input
            type="number"
            min="1900"
            max="2200"
            placeholder="全部年份"
            value={filters.year}
            onChange={(e) => change("year", e.target.value)}
          />
        </label>
        <label>
          月份
          <select
            value={filters.month}
            onChange={(e) => change("month", e.target.value)}
            disabled={!filters.year}
          >
            <option value="">全部月份</option>
            {Array.from({ length: 12 }, (_, i) => (
              <option value={i + 1} key={i}>
                {i + 1}月
              </option>
            ))}
          </select>
        </label>
        <label>
          心情
          <select
            value={filters.mood}
            onChange={(e) => change("mood", e.target.value)}
          >
            <option value="">全部心情</option>
            {moods.map((m) => (
              <option key={m.value} value={m.value}>
                {m.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          标签
          <input
            placeholder="精确标签"
            value={filters.tag}
            onChange={(e) => change("tag", e.target.value)}
          />
        </label>
        <label className="search-field">
          关键词
          <input
            placeholder="搜索日记与地点"
            value={filters.q}
            onChange={(e) => change("q", e.target.value)}
          />
        </label>
        <button className="primary" type="submit">
          <Search size={17} />
          筛选
        </button>
        <button
          type="button"
          className="text-button"
          onClick={() => {
            const clear = { year: "", month: "", mood: "", tag: "", q: "" };
            setFilters(clear);
            setApplied(clear);
            setOffset(0);
          }}
        >
          清除
        </button>
      </form>
      <ErrorBanner
        message={entries.error}
        retry={() => void entries.reload()}
      />
      {entries.loading ? (
        <Loading />
      ) : !entries.data?.entries.length ? (
        <Empty title="时间轴还很安静" icon={<CalendarDays size={30} />}>
          <p>拍下第一张照片，或换一个筛选条件。</p>
        </Empty>
      ) : (
        <>
          <div className="timeline-grid">
            {entries.data.entries.map((e) => (
              <button
                key={e.record_date}
                className="timeline-card"
                onClick={() => onDay(e.record_date)}
              >
                <div className="timeline-photo">
                  <PhotoView
                    photo={primary(e)}
                    alt={`${e.record_date} 的主照片`}
                  />
                  {e.status === "skipped" ? (
                    <span className="state-tag">休息日</span>
                  ) : null}
                </div>
                <div className="timeline-content">
                  <time>
                    {dateLabel(e.record_date, {
                      year: "numeric",
                      month: "long",
                      day: "numeric",
                    })}
                  </time>
                  <span className="small muted">
                    {[moodLabel(e.mood), e.location?.city]
                      .filter(Boolean)
                      .join(" · ")}
                  </span>
                  {e.note ? <p>{e.note}</p> : null}
                  {e.tags.length ? (
                    <div className="tags">
                      {e.tags.map((tag) => (
                        <span key={tag}>#{tag}</span>
                      ))}
                    </div>
                  ) : null}
                </div>
              </button>
            ))}
          </div>
          <div className="pagination">
            <button
              disabled={offset === 0}
              onClick={() => setOffset(Math.max(0, offset - 24))}
            >
              <ArrowLeft size={16} />
              上一页
            </button>
            <span>
              {offset + 1}–{Math.min(offset + 24, entries.data.total)} /{" "}
              {entries.data.total}
            </span>
            <button
              disabled={offset + 24 >= entries.data.total}
              onClick={() => setOffset(offset + 24)}
            >
              下一页
              <ArrowRight size={16} />
            </button>
          </div>
        </>
      )}
    </>
  );
}
