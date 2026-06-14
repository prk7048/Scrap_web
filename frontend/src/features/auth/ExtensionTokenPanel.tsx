import { useEffect, useState } from "react";
import { Copy, KeyRound, RefreshCw, Trash2 } from "lucide-react";
import { api } from "../../api/client";

type ExtensionTokenStatus = {
  active: boolean;
};

type ExtensionTokenCreated = ExtensionTokenStatus & {
  token: string;
};

export default function ExtensionTokenPanel() {
  const [active, setActive] = useState(false);
  const [token, setToken] = useState<string | null>(null);
  const [statusText, setStatusText] = useState("불러오는 중");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function loadStatus() {
    setError(null);
    try {
      const data = await api<ExtensionTokenStatus>("/api/auth/extension-token");
      setActive(data.active);
      setStatusText(data.active ? "사용 중" : "설정 안 됨");
    } catch (err) {
      setError(err instanceof Error ? err.message : "확장 프로그램 토큰 상태를 불러오지 못했습니다.");
      setStatusText("사용 불가");
    }
  }

  async function rotateToken() {
    setBusy(true);
    setError(null);
    try {
      const data = await api<ExtensionTokenCreated>("/api/auth/extension-token", { method: "POST" });
      setToken(data.token);
      setActive(data.active);
      setStatusText("토큰 준비됨");
    } catch (err) {
      setError(err instanceof Error ? err.message : "확장 프로그램 토큰을 만들지 못했습니다.");
    } finally {
      setBusy(false);
    }
  }

  async function revokeToken() {
    setBusy(true);
    setError(null);
    try {
      await api<{ status: string }>("/api/auth/extension-token", { method: "DELETE" });
      setToken(null);
      setActive(false);
      setStatusText("해제됨");
    } catch (err) {
      setError(err instanceof Error ? err.message : "확장 프로그램 토큰을 해제하지 못했습니다.");
    } finally {
      setBusy(false);
    }
  }

  async function copyToken() {
    if (!token) return;
    await navigator.clipboard.writeText(token);
    setStatusText("복사됨");
  }

  useEffect(() => {
    void loadStatus();
  }, []);

  return (
    <section className="extension-token-panel" aria-label="브라우저 확장 토큰">
      <div className="backup-panel-header">
        <div>
          <p className="eyebrow">확장 프로그램</p>
          <p className="backup-status-line">{statusText}</p>
        </div>
        <KeyRound size={20} aria-hidden="true" />
      </div>

      <p className="muted-text">
        {token
          ? "이 토큰을 확장 프로그램 팝업에 붙여넣으세요."
          : active
            ? "새 토큰이 필요하면 다시 발급하세요."
            : "저장 전용 토큰을 만드세요."}
      </p>

      {token ? (
        <div className="token-reveal">
          <code>{token}</code>
          <button className="secondary-button compact-button" onClick={copyToken} type="button" aria-label="토큰 복사">
            <Copy size={15} aria-hidden="true" />
          </button>
        </div>
      ) : null}

      {error ? <p className="error-text">{error}</p> : null}

      <div className="token-actions">
        <button
          className="secondary-button icon-button compact-button"
          disabled={busy}
          onClick={rotateToken}
          type="button"
        >
          <RefreshCw size={15} aria-hidden="true" />
          <span>{active ? "재발급" : "만들기"}</span>
        </button>
        <button
          className="secondary-button icon-button compact-button"
          disabled={busy || !active}
          onClick={revokeToken}
          type="button"
        >
          <Trash2 size={15} aria-hidden="true" />
          <span>해제</span>
        </button>
      </div>
    </section>
  );
}
