import { useEffect, useState } from "react";
import { Archive, Search } from "lucide-react";
import { api } from "./api/client";
import Login from "./features/auth/Login";
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
  const [selectedTopic, setSelectedTopic] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
        <TopicTree selectedTopic={selectedTopic} onSelect={setSelectedTopic} />
      </aside>

      <main className="main-panel">
        <header className="toolbar">
          <label className="search-box">
            <Search size={18} aria-hidden="true" />
            <input aria-label="Search archive" placeholder="Search saved pages" type="search" />
          </label>
          <SaveUrlDialog />
        </header>

        <section className="content-region">
          {selectedTopic ? <ItemList topic={selectedTopic} /> : <RecommendationFeed />}
        </section>
      </main>
    </div>
  );
}
