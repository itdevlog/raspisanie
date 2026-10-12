/**
 * Formats a duration in minutes as hours and minutes, e.g.
 * `123 → «2 ч 3 мин»`, `45 → «45 мин»`, `60 → «1 ч»`.
 */
export function formatDuration(minutes: number): string {
  const total = Math.max(0, Math.round(minutes));
  if (total < 60) {
    return `${total} мин`;
  }
  const hours = Math.floor(total / 60);
  const rest = total % 60;
  return rest === 0 ? `${hours} ч` : `${hours} ч ${rest} мин`;
}
