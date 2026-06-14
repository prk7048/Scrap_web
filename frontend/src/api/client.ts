const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export function apiUrl(path: string): string {
  return `${API_BASE}${path}`;
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(apiUrl(path), {
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(options.headers ?? {}) },
    ...options,
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<T>;
}
