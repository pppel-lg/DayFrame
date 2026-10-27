import { useMemo, useState } from "react";
import {
  ArrowRight,
  CalendarDays,
  FileDown,
  Film,
  Flame,
  Heart,
  Image as ImageIcon,
  MapPin,
  Printer,
  Smile,
  Tag,
} from "lucide-react";
import {
  dateLabel,
  dateShift,
  moodLabel,
  primary,
  today,
  useResource,
} from "./api";
import type { Entry, Stats } from "./api";
import {
  Empty,
  ErrorBanner,
  Loading,
  PageHeader,
  PanelHeading,
  PhotoView,
  Toggle,
} from "./ui";

export type RunJob = (
  kind: string,
  options?: Record<string, unknown>,
) => Promise<void>;
export function Memories({
  revision,
  onDay,
  runJob,
}: {
  revision: number;
  onDay: (date: string) => void;
  runJob: RunJob;
}) {
  const [date, setDate] = useState(today()),
    [left, setLeft] = useState(dateShift(today(), -365)),
    [right, setRight] = useState(today()),
    [start, setStart] = useState(`${new Date().getFullYear()}-01-01`),
    [end, setEnd] = useState(today()),
    [fps, setFps] = useState(12),
    [jobBusy, setJobBusy] = useState(false);
  const memories = useResource<{ entries: Entry[] }>(
      `/memories?date=${date}`,
      revision,
    ),
    a = useResource<{ entries: Entry[] }>(
      `/entries?start=${left}&end=${left}&limit=1`,
      revision,
    ),
    b = useResource<{ entries: Entry[] }>(
      `/entries?start=${right}&end=${right}&limit=1`,
      revision,
    );
  return (
    <>
      <PageHeader
        title="回忆"
        subtitle="在同一天，遇见过去的自己，看看时光里留下的不同风景。"
      />
      <section className="content-section">
        <header className="section-heading">
          <h2>往年同日</h2>
          <input
            aria-label="回忆日期"
            type="date"
            value={date}
            max={today()}
            onChange={(e) => {
              if (e.target.value) setDate(e.target.value);
            }}
          />
        </header>
        <ErrorBanner
          message={memories.error}
          retry={() => void memories.reload()}
        />
        {memories.loading ? (
          <Loading />
        ) : memories.data?.entries.length ? (
          <div className="memory-grid">
            {memories.data.entries.map((e) => (
              <button
                className="memory-item"
                key={e.record_date}
                onClick={() => onDay(e.record_date)}
              >
                <PhotoView photo={primary(e)} />
                <time>
                  {dateLabel(e.record_date, {
                    year: "numeric",
                    month: "long",
                    day: "numeric",
                  })}
                </time>
                <span className="memory-mood">{moodLabel(e.mood)}</span>
                <p>{e.note}</p>
                <div className="memory-meta">
                  <span>
                    <ImageIcon size={15} />
                    {e.photos.filter((p) => !p.trashed_at_utc).length} 张照片
                  </span>
                  <span>{e.tags.slice(0, 2).join("、")}</span>
                </div>
              </button>
            ))}
          </div>
        ) : (
          <Empty title="这一天，还没有往年的照片" icon={<Heart size={28} />}>
            <p>
              只寻找相同的月与日。
              {date.endsWith("02-29")
                ? "闰日不会自动替换为相邻日期。"
                : "从现在开始，给未来留一点回忆。"}
            </p>
          </Empty>
        )}
      </section>
      <section className="content-section">
        <header className="section-heading">
          <h2>日期对比</h2>
        </header>
        <ErrorBanner message={a.error || b.error} />
        <div className="compare-grid">
          {[
            { date: left, set: setLeft, result: a },
            { date: right, set: setRight, result: b },
          ].map((item, i) => (
            <div className="compare-item" key={i}>
              <input
                aria-label={i === 0 ? "对比起始日期" : "对比结束日期"}
                type="date"
                max={today()}
                value={item.date}
                onChange={(e) => {
                  if (e.target.value) item.set(e.target.value);
                }}
              />
              {item.result.loading ? (
                <Loading />
              ) : (
                <div className="compare-photo">
                  <PhotoView
                    photo={primary(item.result.data?.entries[0])}
                    original
                  />
                </div>
              )}
              {item.result.data?.entries[0] ? (
                <div className="compare-description">
                  <strong>{moodLabel(item.result.data.entries[0].mood)}</strong>
                  <p>
                    {item.result.data.entries[0].note || "这一天没有写下文字。"}
                  </p>
                </div>
              ) : null}
              <button className="text-button" onClick={() => onDay(item.date)}>
                查看这一天 <ArrowRight size={14} />
              </button>
            </div>
          ))}
        </div>
      </section>
      <section className="content-section video-section">
        <div>
          <Film size={25} />
          <h2>把日子，连成一段影片</h2>
          <p className="muted">
            每个记录日取一张主照片。缺失日跳过，原始照片保持不变。
          </p>
        </div>
        <form
          className="filter-bar"
          onSubmit={(e) => {
            e.preventDefault();
            setJobBusy(true);
            void runJob("video", { start, end, fps }).finally(() =>
              setJobBusy(false),
            );
          }}
        >
          <label>
            开始日期
            <input
              type="date"
              required
              value={start}
              max={end}
              onChange={(e) => setStart(e.target.value)}
            />
          </label>
          <label>
            结束日期
            <input
              type="date"
              required
              value={end}
              min={start}
              max={today()}
              onChange={(e) => setEnd(e.target.value)}
            />
          </label>
          <label>
            每秒照片数
            <input
              type="number"
              min="1"
              max="60"
              required
              value={fps}
              onChange={(e) => setFps(Number(e.target.value))}
            />
          </label>
          <button className="primary" disabled={jobBusy}>
            生成延时视频
          </button>
        </form>
        <p className="small muted">
          生成结果和下载链接会显示在任务列表。没有可用编码器时会保留照片并显示原因。
        </p>
      </section>
    </>
  );
}

export function Locations({
  revision,
  onDay,
}: {
  revision: number;
  onDay: (date: string) => void;
}) {
  const [year, setYear] = useState("");
  const result = useResource<{
    locations: {
      label: string;
      count: number;
      dates: string[];
      latitude: number | null;
      longitude: number | null;
    }[];
  }>(`/locations${year ? `?year=${year}` : ""}`, revision);
  return (
    <>
      <PageHeader
        title="足迹"
        subtitle="用城市记住旅程，收藏每一处生活留下的坐标。"
      >
        <input
          aria-label="足迹年份"
          type="number"
          min="1900"
          max="2200"
          placeholder="全部年份"
          value={year}
          onChange={(e) => setYear(e.target.value)}
        />
      </PageHeader>
      <ErrorBanner message={result.error} retry={() => void result.reload()} />
      {result.loading ? (
        <Loading />
      ) : !result.data?.locations.length ? (
        <Empty title="还没有留下城市足迹" icon={<MapPin size={30} />}>
          <p>在每日记录里填写城市，这里会慢慢连起你的旅程。</p>
        </Empty>
      ) : (
        <div className="location-list">
          {result.data.locations.map((place, i) => (
            <section className="location-row" key={place.label}>
              <div className="location-index">
                {String(i + 1).padStart(2, "0")}
              </div>
              <div>
                <h2>
                  <MapPin size={20} />
                  {place.label || "未命名地点"}
                </h2>
                <p className="muted">{place.count} 个记录日</p>
                <div className="location-dates">
                  {place.dates.map((d) => (
                    <button key={d} onClick={() => onDay(d)}>
                      {dateLabel(d, {
                        year: "numeric",
                        month: "short",
                        day: "numeric",
                      })}
                      <ArrowRight size={13} />
                    </button>
                  ))}
                </div>
                {place.latitude !== null && place.longitude !== null ? (
                  <p className="small muted">
                    已保存的位置：{place.latitude.toFixed(3)},{" "}
                    {place.longitude.toFixed(3)}
                  </p>
                ) : null}
              </div>
            </section>
          ))}
        </div>
      )}
      <div className="privacy-note">
        <MapPin size={17} />
        <p>城市由你填写；应用不会在后台获取位置。照片和日记不传给地图服务。</p>
      </div>
    </>
  );
}

export function Report({
  revision,
  runJob,
  onDay,
}: {
  revision: number;
  runJob: RunJob;
  onDay: (date: string) => void;
}) {
  const [year, setYear] = useState(new Date().getFullYear()),
    [notes, setNotes] = useState(false),
    [busy, setBusy] = useState(false);
  const stats = useResource<Stats>(
    `/stats?start=${year}-01-01&end=${year}-12-31&today=${today()}`,
    revision,
  );
  const records = useResource<{ entries: Entry[] }>(
    `/entries?start=${year}-01-01&end=${year}-12-31&limit=400`,
    revision,
  );
  const analysis = useMemo(() => {
    const entries = records.data?.entries || [];
    const valid = entries.filter(
      (entry) => primary(entry) && !primary(entry)?.missing,
    );
    const tags = new Map<string, number>(),
      cities = new Map<string, number>();
    for (const entry of entries) {
      for (const tag of new Set(entry.tags))
        tags.set(tag, (tags.get(tag) || 0) + 1);
      const city = entry.location?.city || entry.location?.label;
      if (city) cities.set(city, (cities.get(city) || 0) + 1);
    }
    let longest = 0,
      streak = 0,
      previous = "";
    for (const entry of [...valid].sort((a, b) =>
      a.record_date.localeCompare(b.record_date),
    )) {
      streak =
        previous && dateShift(previous, 1) === entry.record_date
          ? streak + 1
          : 1;
      longest = Math.max(longest, streak);
      previous = entry.record_date;
    }
    return {
      valid,
      map: new Map(valid.map((entry) => [entry.record_date, entry])),
      tags: [...tags].sort((a, b) => b[1] - a[1]),
      cities: [...cities].sort((a, b) => b[1] - a[1]),
      longest,
    };
  }, [records.data]);
  const moods = (stats.data?.moods || []).filter((mood) => mood.mood);
  const moodTotal = moods.reduce((sum, mood) => sum + mood.count, 0);
  const colors = [
    "#86a084",
    "#b9c7ad",
    "#e9ce83",
    "#a8c4da",
    "#c1c2c5",
    "#d5bca7",
  ];
  let position = 0;
  const gradient = moods
    .map((mood, i) => {
      const from = position;
      position += (mood.count / Math.max(1, moodTotal)) * 100;
      return `${colors[i % colors.length]} ${from}% ${position}%`;
    })
    .join(", ");
  const first = `${year}-01-01`;
  const dayCount = Math.round(
    (new Date(`${year + 1}-01-01T12:00:00`).getTime() -
      new Date(`${first}T12:00:00`).getTime()) /
      86400000,
  );
  const padding = (new Date(`${first}T12:00:00`).getDay() + 6) % 7;
  const generate = () => {
    setBusy(true);
    void runJob("report", { year, include_notes: notes }).finally(() =>
      setBusy(false),
    );
  };
  return (
    <>
      <PageHeader
        title="年度报告"
        subtitle="用一年的照片与文字，回顾生活的点滴，看看这一年成为了怎样的自己。"
      >
        <label className="year-select">
          <input
            aria-label="报告年份"
            type="number"
            min="1900"
            max="2200"
            value={year}
            onChange={(e) => {
              const value = Number(e.target.value);
              if (value >= 1900 && value <= 2200) setYear(value);
            }}
          />
          年
        </label>
        <button
          className="primary"
          disabled={busy || !stats.data?.recorded_days}
          onClick={generate}
        >
          <FileDown size={17} />
          导出 HTML
        </button>
        <button onClick={() => window.print()}>
          <Printer size={17} />
          打印为 PDF
        </button>
      </PageHeader>
      <ErrorBanner message={stats.error || records.error} />
      <div className="report-kpis">
        {[
          {
            icon: <CalendarDays />,
            label: "总记录天数",
            value: stats.data?.recorded_days ?? "—",
            unit: "天",
            note: `占应记录日 ${stats.data ? (stats.data.recording_rate * 100).toFixed(1) : "—"}%`,
          },
          {
            icon: <ImageIcon />,
            label: "照片数量",
            value: stats.data?.photo_count ?? "—",
            unit: "张",
            note: "每一张，都值得珍藏",
          },
          {
            icon: <Smile />,
            label: "最常心情",
            value: moods.length ? moodLabel(moods[0].mood) : "未填写",
            unit: "",
            note: moods.length
              ? `出现 ${moods[0].count} 次`
              : "在记录中写下此刻的心情",
          },
          {
            icon: <Flame />,
            label: "连续记录",
            value: analysis.longest,
            unit: "天",
            note: "本年最长连续记录",
          },
        ].map((item) => (
          <div className="report-kpi" key={item.label}>
            <span className="panel-icon">{item.icon}</span>
            <div>
              <span>{item.label}</span>
              <strong>
                {item.value}
                <small>{item.unit}</small>
              </strong>
              <p>{item.note}</p>
            </div>
          </div>
        ))}
      </div>
      {stats.loading || records.loading ? (
        <Loading />
      ) : (
        <>
          <div className="report-main-grid">
            <section className="report-panel heatmap-panel">
              <PanelHeading
                icon={<CalendarDays size={22} />}
                title="全年记录热力图"
                subtitle="每一个有记录的日子，都是生活发光的瞬间。"
              />
              <div className="heatmap-months">
                {Array.from({ length: 12 }, (_, i) => (
                  <span key={i}>{i + 1}月</span>
                ))}
              </div>
              <div className="heatmap-layout">
                <div className="heatmap-weekdays">
                  {["周一", "周二", "周三", "周四", "周五", "周六", "周日"].map(
                    (label) => (
                      <span key={label}>{label}</span>
                    ),
                  )}
                </div>
                <div
                  className="year-heatmap"
                  style={{
                    gridTemplateColumns: `repeat(${Math.ceil((dayCount + padding) / 7)}, minmax(0, 1fr))`,
                  }}
                >
                  {Array.from({ length: dayCount + padding }, (_, i) => {
                    if (i < padding)
                      return <span className="heatmap-padding" key={i} />;
                    const date = dateShift(first, i - padding),
                      entry = analysis.map.get(date),
                      count =
                        entry?.photos.filter(
                          (p) => !p.trashed_at_utc && !p.missing,
                        ).length || 0;
                    return (
                      <button
                        key={date}
                        aria-label={`${date}，${count ? count + " 张照片" : "暂无记录"}`}
                        title={`${date}：${count} 张照片`}
                        className={`heatmap-day level-${Math.min(4, count)}`}
                        disabled={date > today()}
                        onClick={() => onDay(date)}
                      />
                    );
                  })}
                </div>
              </div>
              <div className="heatmap-legend">
                <span>没有记录</span>
                {[0, 1, 2, 3, 4].map((level) => (
                  <i className={`level-${level}`} key={level} />
                ))}
                <span>照片较多</span>
              </div>
              <p className="report-stat-note">
                应记录 {stats.data?.eligible_days || 0} 天 · 跳过{" "}
                {stats.data?.skipped_days || 0} 天 · 当前连续{" "}
                {stats.data?.current_streak || 0} 天
              </p>
            </section>
            <section className="report-panel">
              <PanelHeading icon={<Smile size={22} />} title="心情分布" />
              <div className="mood-distribution">
                <div
                  className="mood-donut"
                  style={{
                    background: moodTotal
                      ? `conic-gradient(${gradient})`
                      : "#eff0ea",
                  }}
                  role="img"
                  aria-label={`共 ${moodTotal} 天填写心情`}
                >
                  <div>
                    <span>心情记录</span>
                    <strong>{moodTotal}</strong>
                    <span>天</span>
                  </div>
                </div>
                <div className="mood-legend">
                  {moods.length ? (
                    moods.map((mood, i) => (
                      <div key={mood.mood}>
                        <i style={{ background: colors[i % colors.length] }} />
                        <span>{moodLabel(mood.mood)}</span>
                        <strong>{mood.count}</strong>
                        <small>
                          {Math.round((mood.count / moodTotal) * 100)}%
                        </small>
                      </div>
                    ))
                  ) : (
                    <p className="muted">这一年还没有填写心情。</p>
                  )}
                </div>
              </div>
            </section>
          </div>
          <div className="report-bottom-grid">
            <section className="report-panel">
              <PanelHeading icon={<Tag size={22} />} title="高频标签" />
              {analysis.tags.length ? (
                <div className="ranking-list">
                  {analysis.tags.slice(0, 7).map(([tag, count], i) => (
                    <div key={tag}>
                      <span>{i + 1}</span>
                      <div>
                        <i
                          style={{
                            width: `${(count / analysis.tags[0][1]) * 100}%`,
                          }}
                        />
                        <strong>{tag}</strong>
                      </div>
                      <span>{count}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <Empty title="还没有标签">
                  <p>在记录里添加标签，收藏生活的主题。</p>
                </Empty>
              )}
            </section>
            <section className="report-panel">
              <PanelHeading icon={<MapPin size={22} />} title="最常去的城市" />
              {analysis.cities.length ? (
                <div className="city-ranking">
                  {analysis.cities.slice(0, 7).map(([city, count], i) => (
                    <div key={city}>
                      <span>{i + 1}</span>
                      <MapPin size={18} />
                      <strong>{city}</strong>
                      <span>{count} 天</span>
                    </div>
                  ))}
                </div>
              ) : (
                <Empty title="还没有城市足迹">
                  <p>在记录里写下城市，记住走过的地方。</p>
                </Empty>
              )}
            </section>
            <section className="report-panel">
              <PanelHeading
                icon={<ImageIcon size={22} />}
                title="年度精选回忆"
              />
              {analysis.valid.length ? (
                <div className="report-mosaic">
                  {analysis.valid.slice(0, 6).map((entry) => (
                    <button
                      key={entry.record_date}
                      onClick={() => onDay(entry.record_date)}
                    >
                      <PhotoView
                        photo={primary(entry)}
                        alt={entry.record_date}
                      />
                      <span>{entry.record_date}</span>
                    </button>
                  ))}
                </div>
              ) : (
                <Empty title="这一年还没有照片">
                  <p>从今天开始，慢慢收藏每一天。</p>
                </Empty>
              )}
            </section>
          </div>
        </>
      )}
      <section className="export-section">
        <div>
          <h2>保存一份，可以离线打开的报告</h2>
          <p className="muted">
            导出 HTML，包含年度统计和照片拼贴；默认不含日记和精确坐标。
          </p>
          <Toggle checked={notes} onChange={setNotes}>
            在报告中包含日记文字
          </Toggle>
        </div>
        <button
          className="primary"
          disabled={busy || !stats.data?.recorded_days}
          onClick={generate}
        >
          生成年度报告 <ArrowRight size={16} />
        </button>
      </section>
    </>
  );
}
