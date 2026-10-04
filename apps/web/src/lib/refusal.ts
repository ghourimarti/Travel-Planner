/**
 * The sentence a user sees when a plan/trip request is refused.
 *
 * A 503 has three causes that need different words: the kill switch or spend breaker (an
 * operator decision - "temporarily disabled"), a task-queue outage and a database outage
 * (both transient - retrying helps). The backend names the cause in its `detail`, and the
 * BFF forwards that body verbatim as `error`, so the outages are told apart by their text.
 */
export function refusalMessage(status: number, error?: string): string {
  if (status === 503) {
    if (/task queue/i.test(error ?? "")) {
      return "We couldn't queue your request just now. Please try again in a moment.";
    }
    if (/database/i.test(error ?? "")) {
      return "We couldn't save your request just now. Please try again in a moment.";
    }
    return "Planning is temporarily disabled. Please try again shortly.";
  }
  if (status === 429) return "You've hit the rate limit. Please wait a moment.";
  return error ?? `Request failed (${status}).`;
}
