import { useState } from "react";
import { ArrowRight, Film, Heart, MapPin } from "lucide-react";
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
  PhotoView,
  StatsBar,
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
        title="与过去的自己，见一面"
        subtitle="时间没有声音，照片记得。"
      />
      <section className="content-section">
        <header className="section-heading">
          <h2>往年的今天</h2>
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
                <p>{e.note}</p>
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
          <h2>把两个时刻，并排放好</h2>
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
        title="走过的地方，留下的自己"
        subtitle="用城市记住旅程。地点列表离线可用，不加载第三方地图。"
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
    ),
    photos = useResource<{ entries: Entry[] }>(
      `/entries?start=${year}-01-01&end=${year}-12-31&limit=12`,
      revision,
    );
  const max = Math.max(1, ...(stats.data?.monthly.map((m) => m.count) || []));
  return (
    <>
      <PageHeader
        title="这一年，你留下了什么"
        subtitle="一份属于自己的年度生活报告。"
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
      </PageHeader>
      <ErrorBanner message={stats.error || photos.error} />
      <StatsBar stats={stats.data} />
      {stats.loading ? (
        <Loading />
      ) : stats.data ? (
        <>
          <div className="report-grid">
            <section className="content-section">
              <h2>十二个月的记录</h2>
              <div className="month-chart">
                {Array.from({ length: 12 }, (_, i) => {
                  const value =
                    stats.data?.monthly.find(
                      (m) =>
                        String(m.month).slice(-2) ===
                          String(i + 1).padStart(2, "0") ||
                        Number(m.month) === i + 1,
                    )?.count || 0;
                  return (
                    <div key={i}>
                      <span>{value}</span>
                      <div className="bar-track">
                        <i style={{ height: `${(value / max) * 100}%` }} />
                      </div>
                      <small>{i + 1}月</small>
                    </div>
                  );
                })}
              </div>
            </section>
            <section className="content-section">
              <h2>写下过的心情</h2>
              {stats.data.moods.length ? (
                <div className="mood-report">
                  {stats.data.moods.map((m) => (
                    <div key={m.mood}>
                      <span>{moodLabel(m.mood) || "未填写"}</span>
                      <strong>
                        {m.count}
                        <small> 天</small>
                      </strong>
                    </div>
                  ))}
                </div>
              ) : (
                <Empty title="心情还留在心里" />
              )}
            </section>
          </div>
          <section className="content-section">
            <h2>这一年的最近照片</h2>
            {photos.data?.entries.some((e) => primary(e)) ? (
              <div className="report-mosaic">
                {photos.data.entries
                  .filter((e) => primary(e))
                  .map((e) => (
                    <button
                      key={e.record_date}
                      onClick={() => onDay(e.record_date)}
                    >
                      <PhotoView photo={primary(e)} alt={e.record_date} />
                      <span>{e.record_date}</span>
                    </button>
                  ))}
              </div>
            ) : (
              <Empty title="这一年还没有照片" />
            )}
          </section>
        </>
      ) : null}
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
          onClick={() => {
            setBusy(true);
            void runJob("report", { year, include_notes: notes }).finally(() =>
              setBusy(false),
            );
          }}
        >
          生成年度报告 <ArrowRight size={16} />
        </button>
      </section>
    </>
  );
}
