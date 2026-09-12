/* Gate tests for the landing countdown's timing contract: the animation runs
   the real 7.4 seconds, and the windows it lights are the ones every language
   prints next to each line. */
import { describe, expect, it } from "vitest";
import { LANGS } from "../i18n";
import { copy } from "../pages/Landing";
import {
  COOL_S, LIGHT_S, parseWindowLabel, REWIND_SPEED, SCAN_SECONDS, SCAN_WINDOWS, scanCues,
} from "../pages/landingScan";

describe("landing scan timeline", () => {
  it("windows tile 0 to 7.4 seconds with no gap or overlap", () => {
    expect(SCAN_SECONDS).toBe(7.4);
    expect(SCAN_WINDOWS[0][0]).toBe(0);
    expect(SCAN_WINDOWS[SCAN_WINDOWS.length - 1][1]).toBe(SCAN_SECONDS);
    SCAN_WINDOWS.forEach(([from, to], i) => {
      expect(to).toBeGreaterThan(from);
      if (i > 0) expect(from).toBe(SCAN_WINDOWS[i - 1][1]);
    });
  });

  for (const lang of LANGS) {
    it(`copy.${lang}.scan prints exactly the animated windows`, () => {
      const printed = copy[lang].scan.map(([label]) => parseWindowLabel(label));
      expect(printed).toEqual(SCAN_WINDOWS.map(([from, to]) => [from, to]));
    });
  }

  it("each line lights when its window opens and cools inside the countdown", () => {
    const cues = scanCues();
    expect(cues).toHaveLength(SCAN_WINDOWS.length);
    cues.forEach(({ lightAt, coolAt }, i) => {
      expect(lightAt).toBe(SCAN_WINDOWS[i][0]);
      expect(coolAt).toBeGreaterThanOrEqual(lightAt + LIGHT_S);
      expect(coolAt + COOL_S).toBeLessThanOrEqual(SCAN_SECONDS + 0.5);
    });
  });

  it("rewinds faster than it counts down", () => {
    expect(REWIND_SPEED).toBeGreaterThan(1);
  });

  it("parses both decimal separators and rejects anything else", () => {
    expect(parseWindowLabel("0,9 – 2,3s")).toEqual([0.9, 2.3]);
    expect(parseWindowLabel("4.4 - 6.0s")).toEqual([4.4, 6]);
    expect(parseWindowLabel("soon")).toBeNull();
    expect(parseWindowLabel("1 – 2s")).toBeNull();
  });
});
