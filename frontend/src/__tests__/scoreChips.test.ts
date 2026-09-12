/* Gate tests for the score card's keyword chips: pressing "+N" must reveal
   every keyword that was not displayed, and nothing may be lost either way. */
import { describe, expect, it } from "vitest";
import { CHIP_LIMIT, chipWindow } from "../pages/Studio/scoreChips";

const EIGHT = ["Python", "Kubernetes", "Rust", "Terraform", "Kafka", "Scala", "Go", "Airflow"];

describe("chipWindow", () => {
  it("collapsed: shows the first five and counts the rest", () => {
    const w = chipWindow(EIGHT, false);
    expect(w.shown).toEqual(EIGHT.slice(0, CHIP_LIMIT));
    expect(w.hidden).toBe(3);
    expect(w.canToggle).toBe(true);
  });

  it("expanded: shows every keyword, in order, with nothing hidden", () => {
    const w = chipWindow(EIGHT, true);
    expect(w.shown).toEqual(EIGHT);
    expect(w.hidden).toBe(0);
    expect(w.canToggle).toBe(true);
  });

  it("collapsed shown + the +N count always equals the full list", () => {
    for (let n = 0; n <= 12; n++) {
      const list = EIGHT.concat(EIGHT).slice(0, n);
      const w = chipWindow(list, false);
      expect(w.shown.length + w.hidden).toBe(n);
      expect(chipWindow(list, true).shown).toEqual(list);
    }
  });

  it("offers no toggle when everything already fits", () => {
    for (const expanded of [false, true]) {
      const w = chipWindow(EIGHT.slice(0, CHIP_LIMIT), expanded);
      expect(w.hidden).toBe(0);
      expect(w.canToggle).toBe(false);
    }
    expect(chipWindow([], false)).toEqual({ shown: [], hidden: 0, canToggle: false });
  });

  it("honours a custom limit", () => {
    expect(chipWindow(EIGHT, false, 2).hidden).toBe(6);
  });
});
