const STATUS_LABELS: Record<string, string> = {
  inbox: "받은 글",
  queued: "대기 중",
  processing: "처리 중",
  preserved: "보존 완료",
  classification_needed: "분류 필요",
  failed: "실패",
  running: "실행 중",
  complete: "완료",
  revoked: "해제됨",
  pending: "대기 중",
  unknown: "알 수 없음",
};

const TOPIC_LABELS: Record<string, string> = {
  AI: "AI",
  Development: "개발",
  YouTube: "유튜브",
  Unsorted: "미분류",
  "Search results": "검색 결과",
};

export function formatDateTime(value?: string | null): string {
  if (!value) return "없음";
  return new Intl.DateTimeFormat("ko-KR", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Asia/Seoul",
  }).format(new Date(value));
}

export function statusLabel(value?: string | null): string {
  if (!value) return STATUS_LABELS.unknown;
  return STATUS_LABELS[value] ?? value;
}

export function topicLabel(value?: string | null): string {
  if (!value) return "미분류";
  return TOPIC_LABELS[value] ?? value;
}

export function recommendationReasonLabel(value?: string | null): string | null {
  if (!value) return null;
  if (value === "Needs retry before it can be preserved.") return "보존하려면 다시 시도해야 합니다.";
  if (value === "Recently saved and preserved.") return "최근 저장되어 보존된 글입니다.";
  return value;
}
