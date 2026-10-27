import { useState } from "react";
import { LockKeyhole, Mail, Plus, Send } from "lucide-react";
import {
  dateLabel,
  dateShift,
  errorText,
  send,
  today,
  useResource,
} from "./api";
import type { Letter } from "./api";
import { Empty, ErrorBanner, Loading, Modal, PageHeader } from "./ui";

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
  const [compose, setCompose] = useState(false),
    [opened, setOpened] = useState<Letter | null>(null),
    [title, setTitle] = useState(""),
    [content, setContent] = useState(""),
    [unlock, setUnlock] = useState(dateShift(today(), 365)),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  async function create() {
    setBusy(true);
    setError("");
    try {
      await send("/letters", {
        title,
        content,
        unlock_date: unlock,
        created_on_date: today(),
      });
      setCompose(false);
      setTitle("");
      setContent("");
      onChange();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <PageHeader
        title="寄给未来的自己"
        subtitle="把此刻的想法封好，在约定的日子再打开。"
      >
        <button
          className="primary"
          onClick={() => {
            setError("");
            setCompose(true);
          }}
        >
          <Plus size={17} />
          写一封信
        </button>
      </PageHeader>
      <ErrorBanner message={result.error} retry={() => void result.reload()} />
      {result.loading ? (
        <Loading />
      ) : !result.data?.letters.length ? (
        <Empty title="未来的信箱，等你投递" icon={<Mail size={32} />}>
          <p>写一封信，送给半年、一年，或更久以后的自己。</p>
          <button className="text-button" onClick={() => setCompose(true)}>
            开始写信 <Send size={15} />
          </button>
        </Empty>
      ) : (
        <div className="letter-list">
          {result.data.letters.map((letter) => (
            <button
              className={`letter ${letter.locked ? "locked" : ""}`}
              key={letter.letter_id}
              onClick={() => {
                if (!letter.locked) setOpened(letter);
              }}
              disabled={letter.locked}
            >
              <div className="letter-icon">
                {letter.locked ? <LockKeyhole size={22} /> : <Mail size={22} />}
              </div>
              <div>
                <h2>{letter.title}</h2>
                <p>
                  {letter.locked ? "将在" : "已于"}{" "}
                  {dateLabel(letter.unlock_date, {
                    year: "numeric",
                    month: "long",
                    day: "numeric",
                  })}{" "}
                  开启
                </p>
              </div>
              <span className="letter-state">
                {letter.locked ? "等待约定的日子" : "打开信件"}
              </span>
            </button>
          ))}
        </div>
      )}
      <p className="small muted letter-note">
        信件保存在本地归档中，未到日期时应用不展示正文。它是温柔的约定，并非加密保险箱。
      </p>
      {compose ? (
        <Modal
          title="写给未来的自己"
          onClose={() => {
            if (!busy) setCompose(false);
          }}
        >
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void create();
            }}
          >
            <ErrorBanner message={error} />
            <label className="field">
              信件标题
              <input
                required
                value={title}
                maxLength={200}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="那时的你，还好吗？"
              />
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
            <label className="field">
              想对未来的自己说
              <textarea
                required
                value={content}
                maxLength={50000}
                onChange={(e) => setContent(e.target.value)}
                rows={10}
                placeholder="亲爱的自己，"
              />
            </label>
            <button className="primary full" disabled={busy}>
              <Send size={16} />
              {busy ? "正在封好信件…" : "封好，寄给未来"}
            </button>
          </form>
        </Modal>
      ) : null}
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
