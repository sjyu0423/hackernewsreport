export function formatUtcDate(iso: string | null | undefined): string {
  if (!iso) {
    return "Unknown date";
  }
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return "Unknown date";
  }
  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "UTC",
  }).format(date) + " UTC";
}

export function scoreLabel(score: number): string {
  return `${score}/5`;
}
