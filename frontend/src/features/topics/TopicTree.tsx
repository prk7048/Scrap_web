import { useEffect, useState } from "react";
import { api } from "../../api/client";
import { topicLabel } from "../../i18n/display";

type Topic = {
  id?: string;
  name: string;
  count?: number;
  children?: Topic[];
};

type TopicTreeProps = {
  selectedTopic: string | null;
  onSelect: (topic: { label: string; filter: string }) => void;
};

type TopicTreeResponse = {
  topics: Topic[];
};

export default function TopicTree({ selectedTopic, onSelect }: TopicTreeProps) {
  const [topics, setTopics] = useState<Topic[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function loadTopics() {
      try {
        const data = await api<TopicTreeResponse>("/api/topics/tree");
        if (!cancelled) setTopics(data.topics);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "주제 목록을 불러오지 못했습니다.");
      }
    }

    void loadTopics();

    return () => {
      cancelled = true;
    };
  }, []);

  function renderTopic(topic: Topic, depth = 0) {
    const topicFilter = topic.id ?? topic.name;

    return (
      <li key={topic.id ?? topic.name}>
        <button
          className={selectedTopic === topicFilter ? "topic-button selected" : "topic-button"}
          onClick={() => onSelect({ label: topicLabel(topic.name), filter: topicFilter })}
          style={{ paddingLeft: `${12 + depth * 16}px` }}
          type="button"
        >
          <span>{topicLabel(topic.name)}</span>
          <span className="topic-count">{topic.count ?? 0}</span>
        </button>
        {topic.children?.length ? <ul>{topic.children.map((child) => renderTopic(child, depth + 1))}</ul> : null}
      </li>
    );
  }

  return (
    <nav className="topic-tree" aria-label="주제">
      <h2>주제</h2>
      {error ? <p className="error-text">{error}</p> : null}
      <ul>{topics.map((topic) => renderTopic(topic))}</ul>
    </nav>
  );
}
