import { useEffect, useState } from "react";
import { DatabaseBackup, RefreshCw } from "lucide-react";
import { api } from "../../api/client";

type BackupRun = {
  id: string;
  status: string;
  path: string | null;
  error: string | null;
  created_at: string;
};

type BackupStatus = {
  retention_count: number;
  interval_hours: number;
  runs: BackupRun[];
};

function formatDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "short",
    timeStyle: "short",
  }).format(new Date(value));
}

export default function BackupStatusPanel() {
  const [status, setStatus] = useState<BackupStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function loadStatus() {
    setError(null);
    try {
      const data = await api<BackupStatus>("/api/backups/status");
      setStatus(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load backup status.");
    } finally {
      setLoading(false);
    }
  }

  async function runBackup() {
    setRunning(true);
    setError(null);
    try {
      await api<{ status: string; manifest: string | null }>("/api/backups/run", { method: "POST" });
      await loadStatus();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to run backup.");
    } finally {
      setRunning(false);
    }
  }

  useEffect(() => {
    void loadStatus();
  }, []);

  const latest = status?.runs[0];

  return (
    <section className="backup-panel" aria-label="Backup status">
      <div className="backup-panel-header">
        <div>
          <p className="eyebrow">Backups</p>
          <p className="backup-status-line">{loading ? "Loading" : latest ? latest.status : "No runs"}</p>
        </div>
        <DatabaseBackup size={20} aria-hidden="true" />
      </div>

      {latest ? (
        <div className="backup-run">
          <span>{formatDate(latest.created_at)}</span>
          <span className={`status-pill status-${latest.status}`}>{latest.status}</span>
        </div>
      ) : null}

      {latest?.path ? <p className="backup-path">{latest.path}</p> : null}
      {latest?.error ? <p className="error-text">{latest.error}</p> : null}
      {error ? <p className="error-text">{error}</p> : null}
      {status ? <p className="muted-text">Keeping {status.retention_count} completed runs</p> : null}

      <button className="secondary-button icon-button backup-run-button" disabled={running} onClick={runBackup} type="button">
        <RefreshCw size={16} aria-hidden="true" />
        <span>{running ? "Running" : "Run Backup"}</span>
      </button>
    </section>
  );
}
