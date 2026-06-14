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
  const [statusText, setStatusText] = useState("Loading");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function loadStatus() {
    setError(null);
    try {
      const data = await api<ExtensionTokenStatus>("/api/auth/extension-token");
      setActive(data.active);
      setStatusText(data.active ? "Active" : "Not configured");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load extension token status.");
      setStatusText("Unavailable");
    }
  }

  async function rotateToken() {
    setBusy(true);
    setError(null);
    try {
      const data = await api<ExtensionTokenCreated>("/api/auth/extension-token", { method: "POST" });
      setToken(data.token);
      setActive(data.active);
      setStatusText("Token ready");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create extension token.");
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
      setStatusText("Revoked");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to revoke extension token.");
    } finally {
      setBusy(false);
    }
  }

  async function copyToken() {
    if (!token) return;
    await navigator.clipboard.writeText(token);
    setStatusText("Copied");
  }

  useEffect(() => {
    void loadStatus();
  }, []);

  return (
    <section className="extension-token-panel" aria-label="Browser extension token">
      <div className="backup-panel-header">
        <div>
          <p className="eyebrow">Extension</p>
          <p className="backup-status-line">{statusText}</p>
        </div>
        <KeyRound size={20} aria-hidden="true" />
      </div>

      <p className="muted-text">
        {token
          ? "Paste this token into the extension popup."
          : active
            ? "Rotate to reveal a new token."
            : "Create a save-only token."}
      </p>

      {token ? (
        <div className="token-reveal">
          <code>{token}</code>
          <button className="secondary-button compact-button" onClick={copyToken} type="button" aria-label="Copy token">
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
          <span>{active ? "Rotate" : "Create"}</span>
        </button>
        <button
          className="secondary-button icon-button compact-button"
          disabled={busy || !active}
          onClick={revokeToken}
          type="button"
        >
          <Trash2 size={15} aria-hidden="true" />
          <span>Revoke</span>
        </button>
      </div>
    </section>
  );
}
