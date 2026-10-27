import { useState } from "react";
import {
  BookOpen,
  Check,
  Hourglass,
  LockKeyhole,
  Mail,
  PenLine,
  Save,
} from "lucide-react";
import {
  dateLabel,
  dateShift,
  errorText,
  send,
  today,
  useResource,
} from "./api";
import type { Letter } from "./api";
import {
  Empty,
  ErrorBanner,
  LeafBranch,
  Loading,
  Modal,
  PageHeader,
  PanelHeading,
} from "./ui";

export default function Letters({
  revision,
  onChange,
}: {
  revision: number;
  onChange: () => void;
}) {
  const result = useResource<{ letters: Letter[] }>(
    `/letters?today=${today()}`,
    revision,
  );
  const [opened, setOpened] = useState<Letter | null>(null),
    [title, setTitle] = useState(""),
    [content, setContent] = useState(""),
    [unlock, setUnlock] = useState(dateShift(today(), 365)),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [saved, setSaved] = useState(false);
  async function create() {
    setBusy(true);
    setError("");
    setSaved(false);
    try {
      await send("/letters", {
        title,
        content,
        unlock_date: unlock,
        created_on_date: today(),
      });
      setTitle("");
      setContent("");
      setSaved(true);
      onChange();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }
  const letters = result.data?.letters || [];
  return (
    <>
      <PageHeader
        title="未来信件"
        subtitle="写一封信给未来的自己，在某个特别的日子，与未来重逢。"
      />
      <ErrorBanner message={result.error} retry={() => void result.reload()} />
      <div className="letters-layout">
        <form
          className="letter-composer"
          onSubmit={(e) => {
            e.preventDefault();
            void create();
          }}
        >
          <PanelHeading
            icon={<PenLine size={25} />}
            title="写一封未来信"
            subtitle="记录此刻的心情、想法或对未来的期许。"
          />
          <ErrorBanner message={error} />
          {saved ? (
            <p className="success" role="status">
              <Check size={17} />
              信件已保存，等待约定的日子。
            </p>
          ) : null}
          <fieldset disabled={busy}>
            <label className="field">
              标题
              <input
                aria-label="标题"
                required
                value={title}
                maxLength={200}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="给未来的我…"
              />
              <span className="char-count">{title.length} / 200</span>
            </label>
            <label className="field">
              开启日期
              <input
                type="date"
                required
                min={dateShift(today(), 1)}
                value={unlock}
                onChange={(e) => setUnlock(e.target.value)}
              />
            </label>
            <label className="field letter-content-field">
              信件内容
              <textarea
                aria-label="信件内容"
                required
                value={content}
                maxLength={50000}
                onChange={(e) => setContent(e.target.value)}
                rows={12}
                placeholder={
                  "此刻的你在想什么？\n可以是对未来的期待、对自己的鼓励，\n也可以是想要记住的心情、愿望或问题……"
                }
              />
              <span className="char-count">{content.length} / 50000</span>
            </label>
            <button className="primary full" disabled={busy}>
              <Save size={20} />
              {busy ? "正在保存信件…" : "保存信件"}
            </button>
          </fieldset>
          <p className="letter-note">
            <LockKeyhole size={16} />
            信件保存在本地，到设定日期后可在这里阅读。归档为明文文件，并未加密。
          </p>
        </form>
        <div className="letter-groups">
          {result.loading ? (
            <Loading />
          ) : (
            [true, false].map((locked) => {
              const group = letters.filter(
                (letter) => letter.locked === locked,
              );
              return (
                <section className="letter-group" key={String(locked)}>
                  <PanelHeading
                    icon={
                      locked ? <Hourglass size={24} /> : <BookOpen size={24} />
                    }
                    title={`${locked ? "未开启" : "今天可阅读"}（${group.length}）`}
                  />
                  {group.length ? (
                    <div className="letter-list">
                      {group.map((letter) => (
                        <button
                          className={`letter ${letter.locked ? "locked" : "readable"}`}
                          key={letter.letter_id}
                          onClick={() => setOpened(letter)}
                          disabled={letter.locked}
                        >
                          <div className="letter-icon">
                            <Mail size={30} />
                            <LeafBranch />
                          </div>
                          <div className="letter-text">
                            <h2>{letter.title}</h2>
                            <p>
                              {locked
                                ? "正文留待约定的日子开启。"
                                : letter.content?.slice(0, 60)}
                            </p>
                            <time>
                              {dateLabel(letter.unlock_date, {
                                year: "numeric",
                                month: "long",
                                day: "numeric",
                              })}
                            </time>
                          </div>
                          <span className="letter-state">
                            {locked ? "未开启" : "今天可阅读"}
                          </span>
                        </button>
                      ))}
                    </div>
                  ) : (
                    <Empty
                      title={
                        locked ? "未来的信箱，等你投递" : "还没有到约定的日子"
                      }
                      icon={
                        locked ? <Mail size={28} /> : <BookOpen size={28} />
                      }
                    >
                      <p>
                        {locked
                          ? "写一封信，送给半年、一年，或更久以后的自己。"
                          : "当信件的开启日期到来，就可以在这里重读。"}
                      </p>
                    </Empty>
                  )}
                </section>
              );
            })
          )}
        </div>
      </div>
      {opened ? (
        <Modal title={opened.title} onClose={() => setOpened(null)}>
          <p className="small muted">
            写于 {new Date(opened.created_at_utc).toLocaleDateString("zh-CN")} ·
            开启于 {opened.unlock_date}
          </p>
          <div className="letter-body">{opened.content}</div>
        </Modal>
      ) : null}
    </>
  );
}
