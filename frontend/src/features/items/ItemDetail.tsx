import { useEffect, useMemo, useState } from "react";
import { ArrowLeft, ExternalLink } from "lucide-react";
import { api, apiUrl } from "../../api/client";

type Artifact = {
  id: string;
  type: "html" | "screenshot" | "pdf" | "transcript" | "original_file" | "text";
  path: string;
  mime_type: string;
  created_at: string;
};

type ItemDetailData = {
  id: string;
  original_url: string;
  normalized_url: string;
  source_domain: string;
  title?: string | null;
  description?: string | null;
  body_text?: string | null;
  ai_summary?: string | null;
  ai_recommendation_reason?: string | null;
  status: string;
  classification_status: string;
  failure_reason?: string | null;
  saved_at: string;
  last_processed_at?: string | null;
  artifacts: Artifact[];
};

type DetailTab = "body" | "original" | "snapshot" | "ai" | "meta";

type ItemDetailProps = {
  itemId: string;
  onBack: () => void;
};

const tabs: { id: DetailTab; label: string }[] = [
  { id: "body", label: "Body" },
  { id: "original", label: "Original" },
  { id: "snapshot", label: "Snapshot" },
  { id: "ai", label: "AI" },
  { id: "meta", label: "Meta" },
];

function artifactHref(itemId: string, artifactId: string): string {
  return apiUrl(`/api/items/${encodeURIComponent(itemId)}/artifacts/${encodeURIComponent(artifactId)}`);
}

function ArtifactPreview({ artifact, itemId }: { artifact?: Artifact; itemId: string }) {
  if (!artifact) {
    return <p className="muted-text">No artifact saved for this view.</p>;
  }

  const href = artifactHref(itemId, artifact.id);
  if (artifact.type === "screenshot") {
    return (
      <div className="artifact-viewer">
        <img alt="Archived page screenshot" src={href} />
        <ArtifactLink artifact={artifact} href={href} />
      </div>
    );
  }

  if (artifact.type === "html" || artifact.type === "pdf") {
    return (
      <div className="artifact-viewer">
        <iframe sandbox="" src={href} title={`Archived ${artifact.type}`} />
        <ArtifactLink artifact={artifact} href={href} />
      </div>
    );
  }

  return <ArtifactLink artifact={artifact} href={href} />;
}

function ArtifactLink({ artifact, href }: { artifact: Artifact; href: string }) {
  return (
    <a className="external-link" href={href} rel="noreferrer" target="_blank">
      <span>{artifact.path}</span>
      <ExternalLink size={15} aria-hidden="true" />
    </a>
  );
}

function formatDate(value?: string | null): string {
  if (!value) return "Not set";
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export default function ItemDetail({ itemId, onBack }: ItemDetailProps) {
  const [item, setItem] = useState<ItemDetailData | null>(null);
  const [activeTab, setActiveTab] = useState<DetailTab>("body");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function loadItem() {
      setLoading(true);
      setError("");
      try {
        const data = await api<ItemDetailData>(`/api/items/${encodeURIComponent(itemId)}`);
        if (!cancelled) setItem(data);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Unable to load item.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void loadItem();

    return () => {
      cancelled = true;
    };
  }, [itemId]);

  const artifacts = useMemo(() => {
    const all = item?.artifacts ?? [];
    return {
      html: all.find((artifact) => artifact.type === "html"),
      screenshot: all.find((artifact) => artifact.type === "screenshot"),
      pdf: all.find((artifact) => artifact.type === "pdf"),
    };
  }, [item]);

  if (loading) {
    return <p className="muted-text">Loading item...</p>;
  }

  if (error || !item) {
    return (
      <div className="detail-shell">
        <button className="secondary-button icon-button compact-button" onClick={onBack} type="button">
          <ArrowLeft size={16} aria-hidden="true" />
          <span>Back</span>
        </button>
        <p className="error-text">{error || "Item not found."}</p>
      </div>
    );
  }

  return (
    <article className="detail-shell">
      <header className="detail-header">
        <button className="secondary-button icon-button compact-button" onClick={onBack} type="button">
          <ArrowLeft size={16} aria-hidden="true" />
          <span>Back</span>
        </button>
        <div>
          <div className="card-topline">
            <span>{item.source_domain}</span>
            <span className={`status-pill status-${item.status}`}>{item.status}</span>
          </div>
          <h1>{item.title ?? item.normalized_url}</h1>
          {item.description ? <p className="muted-text">{item.description}</p> : null}
        </div>
        <a className="secondary-button icon-button compact-button" href={item.original_url} rel="noreferrer" target="_blank">
          <span>Original</span>
          <ExternalLink size={16} aria-hidden="true" />
        </a>
      </header>

      <div className="tab-list" role="tablist" aria-label="Item detail">
        {tabs.map((tab) => (
          <button
            aria-selected={activeTab === tab.id}
            className={activeTab === tab.id ? "tab-button active" : "tab-button"}
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            role="tab"
            type="button"
          >
            {tab.label}
          </button>
        ))}
      </div>

      <section className="detail-panel" role="tabpanel">
        {activeTab === "body" ? <pre className="body-text">{item.body_text || "No readable body text saved."}</pre> : null}
        {activeTab === "original" ? (
          <div className="panel-stack">
            <a className="external-link" href={item.original_url} rel="noreferrer" target="_blank">
              <span>{item.original_url}</span>
              <ExternalLink size={15} aria-hidden="true" />
            </a>
            <ArtifactPreview artifact={artifacts.html} itemId={item.id} />
          </div>
        ) : null}
        {activeTab === "snapshot" ? (
          <ArtifactPreview artifact={artifacts.screenshot ?? artifacts.pdf ?? artifacts.html} itemId={item.id} />
        ) : null}
        {activeTab === "ai" ? (
          <div className="panel-stack">
            <section>
              <h2>Summary</h2>
              <p>{item.ai_summary || "No summary saved."}</p>
            </section>
            <section>
              <h2>Recommendation</h2>
              <p>{item.ai_recommendation_reason || "No recommendation reason saved."}</p>
            </section>
          </div>
        ) : null}
        {activeTab === "meta" ? (
          <dl className="metadata-list">
            <div>
              <dt>URL</dt>
              <dd>{item.normalized_url}</dd>
            </div>
            <div>
              <dt>Status</dt>
              <dd>{item.status}</dd>
            </div>
            <div>
              <dt>Classification</dt>
              <dd>{item.classification_status}</dd>
            </div>
            <div>
              <dt>Failure</dt>
              <dd>{item.failure_reason || "None"}</dd>
            </div>
            <div>
              <dt>Saved</dt>
              <dd>{formatDate(item.saved_at)}</dd>
            </div>
            <div>
              <dt>Processed</dt>
              <dd>{formatDate(item.last_processed_at)}</dd>
            </div>
          </dl>
        ) : null}
      </section>
    </article>
  );
}
