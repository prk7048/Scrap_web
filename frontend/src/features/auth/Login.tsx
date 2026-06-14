import { FormEvent, useState } from "react";
import { api } from "../../api/client";

type LoginProps = {
  onLogin: () => void | Promise<void>;
  initialError?: string | null;
};

export default function Login({ onLogin, initialError }: LoginProps) {
  const [email, setEmail] = useState("admin@example.com");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(initialError ?? "");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError("");

    try {
      await api("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      await onLogin();
    } catch (err) {
      setError(err instanceof Error ? err.message : "로그인에 실패했습니다.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="login-page">
      <form className="login-panel" onSubmit={handleSubmit}>
        <div>
          <h1>개인 웹 아카이브</h1>
          <p>저장한 글, 주제, 추천 목록을 보려면 로그인하세요.</p>
        </div>

        <label>
          이메일
          <input
            autoComplete="email"
            onChange={(event) => setEmail(event.target.value)}
            type="email"
            value={email}
          />
        </label>

        <label>
          비밀번호
          <input
            autoComplete="current-password"
            onChange={(event) => setPassword(event.target.value)}
            type="password"
            value={password}
          />
        </label>

        {error ? <p className="error-text">{error}</p> : null}

        <button className="primary-button" disabled={submitting} type="submit">
          {submitting ? "로그인 중..." : "로그인"}
        </button>
      </form>
    </main>
  );
}
