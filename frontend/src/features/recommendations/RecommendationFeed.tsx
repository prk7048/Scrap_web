import { useEffect, useState } from "react";
import { api } from "../../api/client";
import { recommendationReasonLabel, statusLabel, topicLabel } from "../../i18n/display";

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
        if (!cancelled) setError(err instanceof Error ? err.message : "추천 글을 불러오지 못했습니다.");
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
          <p className="eyebrow">추천 읽을거리</p>
          <h1>오늘의 아카이브</h1>
        </div>
      </div>

      {loading ? <p className="muted-text">추천 글을 불러오는 중...</p> : null}
      {error ? <p className="error-text">{error}</p> : null}

      <div className="card-grid">
        {!loading && !error && recommendations.length === 0 ? (
          <p className="muted-text">아직 추천할 글이 없습니다.</p>
        ) : null}
        {recommendations.map((recommendation) => (
          <article className="item-card" key={recommendation.id}>
            <div className="card-topline">
              <span>{recommendation.source_domain ?? "알 수 없는 출처"}</span>
              <span className={`status-pill status-${recommendation.status ?? "unknown"}`}>
                {statusLabel(recommendation.status)}
              </span>
            </div>
            <h2>{recommendation.title ?? "제목 없는 추천"}</h2>
            <div className="metadata-row">
              <span>{topicLabel(recommendation.topic)}</span>
            </div>
            {recommendation.summary ? <p>{recommendation.summary}</p> : null}
            {recommendation.reason ? <p className="muted-text">{recommendationReasonLabel(recommendation.reason)}</p> : null}
          </article>
        ))}
      </div>
    </div>
  );
}
