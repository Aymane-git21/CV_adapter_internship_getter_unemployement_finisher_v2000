/* Gate tests for the sticky Tailor-CV choices store. Per-field validation:
   one rotten field must not spoil the rest of the stored prefs. */
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { loadLaunchPrefs, saveLaunchPrefs, type LaunchPrefs } from "../pages/Studio/launchPrefs";

const KEY = "cvg_launch_prefs.v1";

function fakeStorage() {
  const m = new Map<string, string>();
  return {
    getItem: (k: string) => m.get(k) ?? null,
    setItem: (k: string, v: string) => void m.set(k, v),
    removeItem: (k: string) => void m.delete(k),
    clear: () => m.clear(),
  } as Storage;
}

const FULL: LaunchPrefs = {
  language: "de",
  intensity: "reshape",
  template: "classic",
  accent: "#0E8A66",
  compiler: "latex",
  cvMode: "saved",
  savedCvId: 7,
  saveMaster: false,
};

beforeEach(() => {
  (globalThis as { localStorage?: Storage }).localStorage = fakeStorage();
});
afterEach(() => {
  delete (globalThis as { localStorage?: Storage }).localStorage;
});

describe("launchPrefs", () => {
  it("round-trips a full set of choices", () => {
    saveLaunchPrefs(FULL);
    expect(loadLaunchPrefs()).toEqual(FULL);
  });

  it("returns {} when nothing is stored", () => {
    expect(loadLaunchPrefs()).toEqual({});
  });

  it("returns {} on corrupt JSON", () => {
    localStorage.setItem(KEY, "{not json");
    expect(loadLaunchPrefs()).toEqual({});
  });

  it("returns {} on non-object JSON", () => {
    localStorage.setItem(KEY, "42");
    expect(loadLaunchPrefs()).toEqual({});
  });

  it("drops invalid fields but keeps valid siblings", () => {
    localStorage.setItem(
      KEY,
      JSON.stringify({
        ...FULL,
        language: "xx",
        intensity: "nuke",
        accent: "red",
        compiler: "pdflatex",
        cvMode: "carrier-pigeon",
        savedCvId: "seven",
        saveMaster: "yes",
      }),
    );
    expect(loadLaunchPrefs()).toEqual({ template: "classic" });
  });

  it("drops an empty template but keeps the rest", () => {
    localStorage.setItem(KEY, JSON.stringify({ ...FULL, template: "" }));
    const { template: _omitted, ...rest } = FULL;
    expect(loadLaunchPrefs()).toEqual(rest);
  });

  it("accepts savedCvId null", () => {
    saveLaunchPrefs({ ...FULL, savedCvId: null });
    expect(loadLaunchPrefs().savedCvId).toBeNull();
  });

  it("ignores data written under a different version key", () => {
    localStorage.setItem("cvg_launch_prefs", JSON.stringify(FULL));
    expect(loadLaunchPrefs()).toEqual({});
  });

  it("last save wins", () => {
    saveLaunchPrefs(FULL);
    saveLaunchPrefs({ ...FULL, language: "fr", savedCvId: 12 });
    const got = loadLaunchPrefs();
    expect(got.language).toBe("fr");
    expect(got.savedCvId).toBe(12);
  });

  it("no-ops without throwing when storage is unavailable", () => {
    delete (globalThis as { localStorage?: Storage }).localStorage;
    expect(() => saveLaunchPrefs(FULL)).not.toThrow();
    expect(loadLaunchPrefs()).toEqual({});
  });

  it("survives a storage that throws (private-mode quota)", () => {
    (globalThis as { localStorage?: Storage }).localStorage = {
      getItem: () => { throw new Error("denied"); },
      setItem: () => { throw new Error("denied"); },
    } as unknown as Storage;
    expect(() => saveLaunchPrefs(FULL)).not.toThrow();
    expect(loadLaunchPrefs()).toEqual({});
  });
});
