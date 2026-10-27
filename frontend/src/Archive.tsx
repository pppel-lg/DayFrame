import { useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  MapPin,
  NotebookPen,
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
  selected,
}: {
  year: number;
  month: number;
  entries: Entry[];
  onDay: (date: string) => void;
  monday: boolean;
  mini?: boolean;
  selected?: string;
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
              className={`date-cell ${outside ? "outside" : ""} ${future ? "future" : ""} ${d === today() ? "current" : ""} ${selected === d ? "selected" : ""} ${missing ? "missing" : entry?.status || ""}`}
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
    [view, setView] = useState<"month" | "year">("month"),
    [selected, setSelected] = useState(today()),
    [filter, setFilter] = useState("all");
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
  const all = entries.data?.entries || [];
  const selection = selected.startsWith(start.slice(0, 7)) ? selected : start;
  const selectedEntry = all.find((e) => e.record_date === selection);
  const filtered = all.filter((e) =>
    filter === "photos"
      ? !!primary(e)
      : filter === "notes"
        ? !!e.note
        : filter === "places"
          ? !!e.location?.city
          : true,
  );
  return (
    <>
      <PageHeader
        title="日历"
        subtitle="浏览每月的记录，重温那些值得珍藏的日子。"
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
        <div className="calendar-filters">
          {[
            ["all", "全部", all.length],
            ["photos", "有照片", all.filter((e) => primary(e)).length],
            ["notes", "有文字", all.filter((e) => e.note).length],
            ["places", "有地点", all.filter((e) => e.location?.city).length],
          ].map(([value, label, count]) => (
            <button
              key={value}
              className={filter === value ? "active" : ""}
              onClick={() => setFilter(String(value))}
            >
              {label}
              <span>{count}</span>
            </button>
          ))}
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
        <div className="calendar-layout">
          <div>
            <MonthGrid
              year={year}
              month={month}
              entries={filtered}
              selected={selection}
              onDay={setSelected}
              monday={settings.week_starts_monday}
            />
            <StatsBar stats={stats.data} />
          </div>
          <aside className="selected-day-panel">
            <header>
              <h2>
                {dateLabel(selection, {
                  year: "numeric",
                  month: "long",
                  day: "numeric",
                })}
              </h2>
              <span>{dateLabel(selection, { weekday: "long" })}</span>
            </header>
            <div className="selected-day-photo">
              <PhotoView photo={primary(selectedEntry)} />
            </div>
            {selectedEntry ? (
              <>
                <div className="selected-day-mood">
                  <span>心情</span>
                  <strong>{moodLabel(selectedEntry.mood) || "未填写"}</strong>
                </div>
                <div className="selected-day-note">
                  <span>日记</span>
                  <p>{selectedEntry.note || "这一天还没有写下文字。"}</p>
                </div>
                <div className="selected-day-location">
                  <MapPin size={17} />
                  {selectedEntry.location?.city || "未填写城市"}
                </div>
                <div className="tags">
                  {selectedEntry.tags.map((tag) => (
                    <span key={tag}>{tag}</span>
                  ))}
                </div>
              </>
            ) : (
              <p className="muted">
                这一天还没有记录。可以添加照片，或留下一段文字。
              </p>
            )}
            <button className="primary full" onClick={() => onDay(selection)}>
              <NotebookPen size={18} />
              {selectedEntry ? "查看详情与管理照片" : "记录这一天"}
            </button>
          </aside>
        </div>
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
      {view === "year" ? <StatsBar stats={stats.data} /> : null}
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
        title="时间轴"
        subtitle="按时间顺序，回顾生活中的每一个瞬间。"
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
                <div className="timeline-date">
                  <time>
                    {dateLabel(e.record_date, {
                      month: "long",
                      day: "numeric",
                    })}
                  </time>
                  <small>{dateLabel(e.record_date, { weekday: "long" })}</small>
                  <span>{e.record_date.slice(0, 4)}</span>
                </div>
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
                  <h2>
                    {e.note
                      ? e.note.split(/[。！？\n]/)[0].slice(0, 32)
                      : e.status === "skipped"
                        ? "留给生活的一天"
                        : "这一天的一帧"}
                  </h2>
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
                  <span className="timeline-open">
                    {e.photos.filter((p) => !p.trashed_at_utc).length} 张照片{" "}
                    <ChevronRight size={16} /> 查看当天
                  </span>
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
