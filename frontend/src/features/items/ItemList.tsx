import { useEffect, useState } from "react";
import { ExternalLink } from "lucide-react";
import { api } from "../../api/client";
import { statusLabel, topicLabel } from "../../i18n/display";
import ItemDetail from "./ItemDetail";

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
  topicFilter?: string;
  query?: string;
  refreshKey: number;
};

type ItemListResponse = {
  items: Item[];
};

export function buildItemListPath({ topic, topicFilter, query = "" }: Pick<ItemListProps, "topic" | "topicFilter" | "query">) {
  const params = new URLSearchParams();
  const trimmedQuery = query.trim();
  if (trimmedQuery) params.set("q", trimmedQuery);
  if (topic !== "Search results" && topic !== "검색 결과") params.set("topic", topicFilter ?? topic);

  const queryString = params.toString();
  return queryString ? `/api/items?${queryString}` : "/api/items";
}

export default function ItemList({ topic, topicFilter, query = "", refreshKey }: ItemListProps) {
  const [items, setItems] = useState<Item[]>([]);
  const [selectedItemId, setSelectedItemId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function loadItems() {
      setLoading(true);
      setError("");
      try {
        const data = await api<ItemListResponse>(buildItemListPath({ topic, topicFilter, query }));
        if (!cancelled) setItems(data.items);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "저장한 글을 불러오지 못했습니다.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void loadItems();

    return () => {
      cancelled = true;
    };
  }, [topic, topicFilter, query, refreshKey]);

  if (selectedItemId) {
    return <ItemDetail itemId={selectedItemId} onBack={() => setSelectedItemId(null)} />;
  }

  return (
    <div className="view-stack">
      <div className="view-heading">
        <div>
          <p className="eyebrow">{query ? "검색" : "주제"}</p>
          <h1>{topicLabel(topic)}</h1>
        </div>
        {query ? (
          <p className="muted-text">"{query}" 검색 결과</p>
        ) : (
          <p className="muted-text">이 주제에 저장된 글입니다.</p>
        )}
      </div>

      {loading ? <p className="muted-text">저장한 글을 불러오는 중...</p> : null}
      {error ? <p className="error-text">{error}</p> : null}

      <div className="card-grid">
        {!loading && !error && items.length === 0 ? <p className="muted-text">아직 저장한 글이 없습니다.</p> : null}
        {items.map((item) => (
          <article className="item-card" key={item.id}>
            <div className="card-topline">
              <span>{item.domain ?? item.source_domain ?? "알 수 없는 출처"}</span>
              <span className={`status-pill status-${item.status ?? "unknown"}`}>{statusLabel(item.status)}</span>
            </div>
            <button className="item-title-button" onClick={() => setSelectedItemId(item.id)} type="button">
              {item.title ?? item.normalized_url ?? item.original_url ?? item.url}
            </button>
            <a
              className="external-link"
              href={item.original_url ?? item.normalized_url ?? item.url ?? "#"}
              rel="noreferrer"
              target="_blank"
            >
              <span>{item.normalized_url ?? item.original_url ?? item.url ?? "원문 열기"}</span>
              <ExternalLink size={15} aria-hidden="true" />
            </a>
            {item.failure_reason ? <p className="error-text">{item.failure_reason}</p> : null}
          </article>
        ))}
      </div>
    </div>
  );
}
