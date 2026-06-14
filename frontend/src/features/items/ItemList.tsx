import { useEffect, useState } from "react";
import { ExternalLink } from "lucide-react";
import { api } from "../../api/client";

type Item = {
  id: string;
  title?: string | null;
  url?: string | null;
  normalized_url?: string | null;
  original_url?: string | null;
  domain?: string | null;
  source_domain?: string | null;
  status?: string | null;
  failure_reason?: string | null;
};

type ItemListProps = {
  topic: string;
};

type ItemListResponse = {
  items: Item[];
};

export default function ItemList({ topic }: ItemListProps) {
  const [items, setItems] = useState<Item[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function loadItems() {
      setLoading(true);
      setError("");
      try {
        const data = await api<ItemListResponse>("/api/items");
        if (!cancelled) setItems(data.items);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Unable to load items.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void loadItems();

    return () => {
      cancelled = true;
    };
  }, [topic]);

  return (
    <div className="view-stack">
      <div className="view-heading">
        <div>
          <p className="eyebrow">Topic</p>
          <h1>{topic}</h1>
        </div>
        <p className="muted-text">Backend topic filtering is not enabled yet.</p>
      </div>

      {loading ? <p className="muted-text">Loading items...</p> : null}
      {error ? <p className="error-text">{error}</p> : null}

      <div className="card-grid">
        {!loading && !error && items.length === 0 ? <p className="muted-text">No saved items yet.</p> : null}
        {items.map((item) => (
          <article className="item-card" key={item.id}>
            <div className="card-topline">
              <span>{item.domain ?? item.source_domain ?? "Unknown domain"}</span>
              <span className={`status-pill status-${item.status ?? "unknown"}`}>{item.status ?? "unknown"}</span>
            </div>
            <h2>{item.title ?? item.normalized_url ?? item.original_url ?? item.url}</h2>
            <a
              className="external-link"
              href={item.original_url ?? item.normalized_url ?? item.url ?? "#"}
              rel="noreferrer"
              target="_blank"
            >
              <span>{item.normalized_url ?? item.original_url ?? item.url ?? "Open original"}</span>
              <ExternalLink size={15} aria-hidden="true" />
            </a>
            {item.failure_reason ? <p className="error-text">{item.failure_reason}</p> : null}
          </article>
        ))}
      </div>
    </div>
  );
}
