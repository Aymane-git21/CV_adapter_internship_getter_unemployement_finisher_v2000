/* The landing's recruiter-scan countdown, as data. The seconds are real: the
   timeline runs SCAN_SECONDS of wall-clock time once the numeral scrolls into
   view, and each gaze line lights during the same window its label prints.
   Pure, so the timing contract is unit-testable without GSAP or a browser. */
export const SCAN_SECONDS = 7.4;

/* [from, to] in seconds, one per copy.scan row. Every language's printed
   labels are pinned to these in __tests__/landingScan.test.ts. */
export const SCAN_WINDOWS: readonly (readonly [number, number])[] = [
  [0, 0.9],
  [0.9, 2.3],
  [2.3, 4.4],
  [4.4, 6.0],
  [6.0, 7.4],
];

/* Scrolling back above the numeral rewinds the countdown this many times
   faster than it ran, so the reversal reads as a rewind, not a replay. */
export const REWIND_SPEED = 3;

/* How long a gaze line takes to light up and to cool down again. */
export const LIGHT_S = 0.35;
export const COOL_S = 0.45;

/* When each line lights and starts cooling: it lights as its window opens
   and starts cooling just before the next window takes over. */
export function scanCues(windows: readonly (readonly [number, number])[] = SCAN_WINDOWS) {
  return windows.map(([from, to]) => ({ lightAt: from, coolAt: Math.max(from + LIGHT_S, to - 0.2) }));
}

/* A printed window label ("0.0 – 0.9s", "0,0 – 0,9s") in seconds. */
export function parseWindowLabel(label: string): [number, number] | null {
  const m = label.match(/^\s*(\d+[.,]\d+)\s*[–-]\s*(\d+[.,]\d+)\s*s\s*$/);
  if (!m) return null;
  return [parseFloat(m[1].replace(",", ".")), parseFloat(m[2].replace(",", "."))];
}
