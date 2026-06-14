import { useEffect, useState } from "react";
import { api } from "../../api/client";

type Topic = {
  id?: string;
  name: string;
  count?: number;
  children?: Topic[];
};

type TopicTreeProps = {
  selectedTopic: string | null;
  onSelect: (topic: string) => void;
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
        if (!cancelled) setError(err instanceof Error ? err.message : "Unable to load topics.");
      }
    }

    void loadTopics();

    return () => {
      cancelled = true;
    };
  }, []);

  function renderTopic(topic: Topic, depth = 0) {
    return (
      <li key={topic.id ?? topic.name}>
        <button
          className={selectedTopic === topic.name ? "topic-button selected" : "topic-button"}
          onClick={() => onSelect(topic.name)}
          style={{ paddingLeft: `${12 + depth * 16}px` }}
          type="button"
        >
          <span>{topic.name}</span>
          <span className="topic-count">{topic.count ?? 0}</span>
        </button>
        {topic.children?.length ? <ul>{topic.children.map((child) => renderTopic(child, depth + 1))}</ul> : null}
      </li>
    );
  }

  return (
    <nav className="topic-tree" aria-label="Topics">
      <h2>Topics</h2>
      {error ? <p className="error-text">{error}</p> : null}
      <ul>{topics.map((topic) => renderTopic(topic))}</ul>
    </nav>
  );
}
