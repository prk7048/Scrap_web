import { FormEvent, useState } from "react";
import { Plus } from "lucide-react";
import { api } from "../../api/client";

type SaveUrlDialogProps = {
  onSaved: () => void;
};

export default function SaveUrlDialog({ onSaved }: SaveUrlDialogProps) {
  const [open, setOpen] = useState(false);
  const [urls, setUrls] = useState("");
  const [message, setMessage] = useState("");
  const [saving, setSaving] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const values = urls.split(/\s+/).map((url) => url.trim()).filter(Boolean);

    if (values.length === 0) {
      setMessage("URL을 하나 이상 입력하세요.");
      return;
    }

    setSaving(true);
    setMessage("");

    try {
      if (values.length === 1) {
        await api("/api/items/save", {
          method: "POST",
          body: JSON.stringify({ url: values[0] }),
        });
      } else {
        await api("/api/items/save-many", {
          method: "POST",
          body: JSON.stringify({ urls: values }),
        });
      }

      setUrls("");
      setMessage(values.length === 1 ? "URL을 저장했습니다." : `URL ${values.length}개를 저장했습니다.`);
      onSaved();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "URL을 저장하지 못했습니다.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="save-url">
      <button className="primary-button icon-button" onClick={() => setOpen((value) => !value)} type="button">
        <Plus size={18} aria-hidden="true" />
        <span>URL 저장</span>
      </button>

      {open ? (
        <form className="save-popover" onSubmit={handleSubmit}>
          <label>
            URL
            <textarea
              onChange={(event) => setUrls(event.target.value)}
              placeholder="https://example.com/article"
              rows={5}
              value={urls}
            />
          </label>
          <div className="popover-actions">
            <button className="secondary-button" onClick={() => setOpen(false)} type="button">
              취소
            </button>
            <button className="primary-button" disabled={saving} type="submit">
              {saving ? "저장 중..." : "저장"}
            </button>
          </div>
          {message ? <p className="status-text">{message}</p> : null}
        </form>
      ) : null}
    </div>
  );
}
