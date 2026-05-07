export function formatRelativeTime(iso: string | null | undefined, now: Date = new Date()): string {
  if (!iso) return "없음";
  const then = new Date(iso);
  if (Number.isNaN(then.getTime())) return iso;
  const diffMs = now.getTime() - then.getTime();
  const sec = Math.round(diffMs / 1000);
  if (sec < 45) return "방금 전";
  if (sec < 90) return "1분 전";
  const min = Math.round(sec / 60);
  if (min < 45) return `${min}분 전`;
  if (min < 90) return "1시간 전";
  const hr = Math.round(min / 60);
  if (hr < 22) return `${hr}시간 전`;
  if (hr < 36) return "어제";
  const day = Math.round(hr / 24);
  if (day < 26) return `${day}일 전`;
  return then.toLocaleDateString();
}

export function formatAbsolute(iso: string | null | undefined): string {
  if (!iso) return "-";
  const then = new Date(iso);
  if (Number.isNaN(then.getTime())) return iso;
  return then.toLocaleString();
}

export function formatBytes(bytes: number | null | undefined): string {
  if (bytes == null) return "-";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

export function formatNumber(value: number): string {
  return value.toLocaleString("ko-KR");
}

export function formatKoreanDateTime(iso: string | null | undefined): string {
  if (!iso) return "-";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const yyyy = d.getFullYear();
  const mm = d.getMonth() + 1;
  const dd = d.getDate();
  const hours = d.getHours();
  const minutes = d.getMinutes().toString().padStart(2, "0");
  const seconds = d.getSeconds().toString().padStart(2, "0");
  const ampm = hours >= 12 ? "PM" : "AM";
  const h = hours % 12 || 12;
  return `${yyyy}년 ${mm}월 ${dd}일, ${h}:${minutes}:${seconds} ${ampm}`;
}
