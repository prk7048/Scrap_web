import { useEffect, useState } from "react";
import { api } from "../../api/client";

type Recommendation = {
  id: string;
  title?: string | null;
  source_domain?: string | null;
  topic?: string | null;
  status?: string | null;
  summary?: string | null;
  reason?: string | null;
};

type RecommendationListResponse = {
  items: Recommendation[];
};

type RecommendationFeedProps = {
  refreshKey: number;
};

export default function RecommendationFeed({ refreshKey }: RecommendationFeedProps) {
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function loadRecommendations() {
      setLoading(true);
      setError("");
      try {
        const data = await api<RecommendationListResponse>("/api/recommendations");
        if (!cancelled) setRecommendations(data.items);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Unable to load recommendations.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void loadRecommendations();

    return () => {
      cancelled = true;
    };
  }, [refreshKey]);

  return (
    <div className="view-stack">
      <div className="view-heading">
        <div>
          <p className="eyebrow">Recommended reading</p>
          <h1>For your archive</h1>
        </div>
      </div>

      {loading ? <p className="muted-text">Loading recommendations...</p> : null}
      {error ? <p className="error-text">{error}</p> : null}

      <div className="card-grid">
        {!loading && !error && recommendations.length === 0 ? (
          <p className="muted-text">No recommendations yet.</p>
        ) : null}
        {recommendations.map((recommendation) => (
          <article className="item-card" key={recommendation.id}>
            <div className="card-topline">
              <span>{recommendation.source_domain ?? "Unknown source"}</span>
              <span className={`status-pill status-${recommendation.status ?? "unknown"}`}>
                {recommendation.status ?? "unknown"}
              </span>
            </div>
            <h2>{recommendation.title ?? "Untitled recommendation"}</h2>
            <div className="metadata-row">
              <span>{recommendation.topic ?? "Unsorted"}</span>
            </div>
            {recommendation.summary ? <p>{recommendation.summary}</p> : null}
            {recommendation.reason ? <p className="muted-text">{recommendation.reason}</p> : null}
          </article>
        ))}
      </div>
    </div>
  );
}
