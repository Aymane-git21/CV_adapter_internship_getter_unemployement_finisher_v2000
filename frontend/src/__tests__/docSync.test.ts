/* Gate tests for the document-echo merge rules: the keyword match must follow
   every server response without clobbering keystrokes typed mid-request. */
import { describe, expect, it } from "vitest";
import type { DocumentPayload } from "../api";
import { mergeEcho, withScore } from "../pages/Studio/docSync";

type Data = DocumentPayload["data"];

function doc(over: Partial<DocumentPayload> = {}): DocumentPayload {
  return {
    id: "d1", job_id: "j1", kind: "cv", title: "T", template: "onyx",
    settings: {
      template: "onyx", accent: "#0F62FE", density: "normal", show_photo: false,
      font_scale: 1, lang: "en", page_mode: "continuous", compiler: "typst",
    },
    data: null, source: "src", mode: "data", text_content: null, photo_id: null,
    score_before: 40, score_after: 60,
    keywords: { matched: ["Python"], missing: ["Rust"] },
    svgs: null,
    ...over,
  };
}

const asData = (v: object) => v as unknown as Data;

describe("mergeEcho", () => {
  it("takes the echo when nothing changed while the request was in flight", () => {
    const sent = { full_name: "A" };
    const current = doc({ data: asData(sent) });
    const echo = doc({ data: asData({ full_name: "A" }), score_after: 80, svgs: ["<svg/>"] });
    expect(mergeEcho(current, { data: sent }, echo)).toBe(echo);
  });

  it("keeps data typed mid-request but takes the server score and render", () => {
    const sent = { full_name: "A" };
    const newer = { full_name: "AB" };
    const current = doc({ data: asData(newer) });
    const echo = doc({
      data: asData({ full_name: "A" }), score_after: 80,
      keywords: { matched: ["Python", "Rust"], missing: [] }, svgs: ["<svg/>"], source: "echo-src",
    });
    const merged = mergeEcho(current, { data: sent }, echo);
    expect(merged.data).toBe(current.data);
    expect(merged.score_after).toBe(80);
    expect(merged.keywords).toEqual({ matched: ["Python", "Rust"], missing: [] });
    expect(merged.svgs).toEqual(["<svg/>"]);
    expect(merged.source).toBe("echo-src");
  });

  it("keeps message text typed mid-request", () => {
    const current = doc({ kind: "message", text_content: "hello there" });
    const echo = doc({ kind: "message", text_content: "hello" });
    expect(mergeEcho(current, { text_content: "hello" }, echo).text_content).toBe("hello there");
  });

  it("settings-only updates always take the echo", () => {
    const current = doc({ data: asData({ full_name: "local" }) });
    const echo = doc({ data: asData({ full_name: "server" }) });
    expect(mergeEcho(current, {}, echo)).toBe(echo);
  });

  it("takes the echo when the document is not loaded locally", () => {
    const echo = doc();
    expect(mergeEcho(undefined, { data: {} }, echo)).toBe(echo);
  });
});

describe("withScore", () => {
  it("folds a re-score into the document", () => {
    const next = withScore(doc(), { score_after: 100, keywords: { matched: ["Python", "Rust"], missing: [] } });
    expect(next.score_after).toBe(100);
    expect(next.keywords?.missing).toEqual([]);
    expect(next.score_before).toBe(40);
  });

  it("returns the same document when the response carries no score fields", () => {
    const d = doc();
    expect(withScore(d, {})).toBe(d);
  });

  it("applies explicit nulls and keeps fields the response omits", () => {
    const d = doc();
    const next = withScore(d, { score_after: null });
    expect(next.score_after).toBeNull();
    expect(next.keywords).toBe(d.keywords);
  });
});
