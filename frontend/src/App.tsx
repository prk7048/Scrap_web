import { useEffect, useState } from "react";
import { Archive, Search } from "lucide-react";
import { api } from "./api/client";
import Login from "./features/auth/Login";
import BackupStatusPanel from "./features/backup/BackupStatusPanel";
import ItemList from "./features/items/ItemList";
import SaveUrlDialog from "./features/items/SaveUrlDialog";
import RecommendationFeed from "./features/recommendations/RecommendationFeed";
import TopicTree from "./features/topics/TopicTree";

type User = {
  id: string;
  email: string;
};

export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [selectedTopic, setSelectedTopic] = useState<{ label: string; filter: string } | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const trimmedSearch = searchQuery.trim();

  async function loadUser() {
    setLoading(true);
    setError(null);
    try {
      const data = await api<User>("/api/auth/me");
      setUser(data);
    } catch (err) {
      setUser(null);
      setError(err instanceof Error ? err.message : "Unable to load session.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadUser();
  }, []);

  if (loading) {
    return <div className="screen-message">Loading archive...</div>;
  }

  if (!user) {
    return <Login onLogin={loadUser} />;
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <button className="brand-button" onClick={() => setSelectedTopic(null)} type="button">
          <Archive size={22} aria-hidden="true" />
          <span>Archive</span>
        </button>
            <TopicTree selectedTopic={selectedTopic?.filter ?? null} onSelect={setSelectedTopic} />
        <BackupStatusPanel />
      </aside>

      <main className="main-panel">
        <header className="toolbar">
          <label className="search-box">
            <Search size={18} aria-hidden="true" />
            <input
              aria-label="Search archive"
              onChange={(event) => setSearchQuery(event.target.value)}
              placeholder="Search saved pages"
              type="search"
              value={searchQuery}
            />
          </label>
          <SaveUrlDialog onSaved={() => setRefreshKey((value) => value + 1)} />
        </header>

        <section className="content-region">
          {trimmedSearch ? (
            <ItemList query={trimmedSearch} refreshKey={refreshKey} topic="Search results" />
          ) : selectedTopic ? (
            <ItemList refreshKey={refreshKey} topic={selectedTopic.label} topicFilter={selectedTopic.filter} />
          ) : (
            <RecommendationFeed refreshKey={refreshKey} />
          )}
        </section>
      </main>
    </div>
  );
}
