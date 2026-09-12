/* Gate tests for the profile page's state rules: which CV opens, when there
   are unsaved changes, and that a sparse stored CV becomes a complete one. */
import { describe, expect, it } from "vitest";
import type { CVData, MasterCVMeta } from "../api";
import { EMPTY_CV, isDirty, normalizeCv, pickInitialCv, sameJson } from "../pages/profileState";

const row = (id: number, is_default = false): MasterCVMeta => ({
  id, name: `CV ${id}`, is_default, data: null, has_raw_text: false, updated_at: null,
});

describe("normalizeCv", () => {
  it("turns missing data into a complete empty CV", () => {
    expect(normalizeCv(null)).toEqual(EMPTY_CV);
    expect(normalizeCv(undefined)).toEqual(EMPTY_CV);
  });

  it("fills absent fields and contact keys without touching present ones", () => {
    const cv = normalizeCv({ full_name: "Alex", contacts: { email: "a@b.fr" } } as unknown as Partial<CVData>);
    expect(cv.full_name).toBe("Alex");
    expect(cv.contacts).toEqual({ ...EMPTY_CV.contacts, email: "a@b.fr" });
    expect(cv.certifications).toEqual([]);
    expect(Object.keys(cv).sort()).toEqual(Object.keys(EMPTY_CV).sort());
  });
});

describe("pickInitialCv", () => {
  it("opens the requested CV, else the default, else the first", () => {
    const rows = [row(1), row(2, true), row(3)];
    expect(pickInitialCv(rows, 3)?.id).toBe(3);
    expect(pickInitialCv(rows, 99)?.id).toBe(2);
    expect(pickInitialCv(rows, null)?.id).toBe(2);
    expect(pickInitialCv([row(4), row(5)], null)?.id).toBe(4);
    expect(pickInitialCv([], 1)).toBeNull();
  });
});

describe("isDirty", () => {
  const saved = {
    name: "Main",
    data: normalizeCv({ full_name: "Alex", skills: [{ category: "Tools", items: ["Docker"] }] }),
  };

  it("is clean for the same content in a different key order", () => {
    const reordered = Object.fromEntries(Object.entries(saved.data).reverse()) as unknown as CVData;
    expect(isDirty({ name: "Main", data: reordered }, saved)).toBe(false);
  });

  it("sees a rename and a nested edit", () => {
    expect(isDirty({ ...saved, name: "Other" }, saved)).toBe(true);
    const edited = { ...saved.data, skills: [{ category: "Tools", items: ["Docker", "Rust"] }] };
    expect(isDirty({ name: "Main", data: edited }, saved)).toBe(true);
  });
});

describe("sameJson", () => {
  it("compares objects structurally and arrays in order", () => {
    expect(sameJson({ a: 1, b: [1, 2] }, { b: [1, 2], a: 1 })).toBe(true);
    expect(sameJson([1, 2], [2, 1])).toBe(false);
    expect(sameJson({ a: undefined }, { b: undefined })).toBe(false);
    expect(sameJson(null, {})).toBe(false);
    expect(sameJson([], {})).toBe(false);
  });
});
