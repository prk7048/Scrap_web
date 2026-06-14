import { useEffect, useState } from "react";
import { DatabaseBackup, RefreshCw } from "lucide-react";
import { api } from "../../api/client";
import { formatDateTime, statusLabel } from "../../i18n/display";

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
      setError(err instanceof Error ? err.message : "백업 상태를 불러오지 못했습니다.");
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
      setError(err instanceof Error ? err.message : "백업을 실행하지 못했습니다.");
    } finally {
      setRunning(false);
    }
  }

  useEffect(() => {
    void loadStatus();
  }, []);

  const latest = status?.runs[0];

  return (
    <section className="backup-panel" aria-label="백업 상태">
      <div className="backup-panel-header">
        <div>
          <p className="eyebrow">백업</p>
          <p className="backup-status-line">{loading ? "불러오는 중" : latest ? statusLabel(latest.status) : "실행 기록 없음"}</p>
        </div>
        <DatabaseBackup size={20} aria-hidden="true" />
      </div>

      {latest ? (
        <div className="backup-run">
          <span>{formatDateTime(latest.created_at)}</span>
          <span className={`status-pill status-${latest.status}`}>{statusLabel(latest.status)}</span>
        </div>
      ) : null}

      {latest?.path ? <p className="backup-path">{latest.path}</p> : null}
      {latest?.error ? <p className="error-text">{latest.error}</p> : null}
      {error ? <p className="error-text">{error}</p> : null}
      {status ? <p className="muted-text">완료된 백업 {status.retention_count}개 보관</p> : null}

      <button className="secondary-button icon-button backup-run-button" disabled={running} onClick={runBackup} type="button">
        <RefreshCw size={16} aria-hidden="true" />
        <span>{running ? "실행 중" : "백업 실행"}</span>
      </button>
    </section>
  );
}
