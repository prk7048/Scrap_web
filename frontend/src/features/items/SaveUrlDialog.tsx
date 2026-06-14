import { FormEvent, useState } from "react";
import { Plus } from "lucide-react";
import { api } from "../../api/client";

export default function SaveUrlDialog() {
  const [open, setOpen] = useState(false);
  const [urls, setUrls] = useState("");
  const [message, setMessage] = useState("");
  const [saving, setSaving] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const values = urls.split(/\s+/).map((url) => url.trim()).filter(Boolean);

    if (values.length === 0) {
      setMessage("Enter at least one URL.");
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
      setMessage(values.length === 1 ? "Saved URL." : `Saved ${values.length} URLs.`);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Could not save URL.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="save-url">
      <button className="primary-button icon-button" onClick={() => setOpen((value) => !value)} type="button">
        <Plus size={18} aria-hidden="true" />
        <span>Save URL</span>
      </button>

      {open ? (
        <form className="save-popover" onSubmit={handleSubmit}>
          <label>
            URLs
            <textarea
              onChange={(event) => setUrls(event.target.value)}
              placeholder="https://example.com/article"
              rows={5}
              value={urls}
            />
          </label>
          <div className="popover-actions">
            <button className="secondary-button" onClick={() => setOpen(false)} type="button">
              Cancel
            </button>
            <button className="primary-button" disabled={saving} type="submit">
              {saving ? "Saving..." : "Save"}
            </button>
          </div>
          {message ? <p className="status-text">{message}</p> : null}
        </form>
      ) : null}
    </div>
  );
}
