/* Gate test: every language ships the same keys — a missing translation is
   a build-time failure, not a runtime English fallback surprise. */
import { describe, expect, it } from "vitest";
import { dict, LANGS } from "../i18n";
import { copy } from "../pages/Landing";

describe("i18n dictionary parity", () => {
  const base = Object.keys(dict.en).sort();
  for (const lang of LANGS) {
    it(`dict.${lang} has exactly the en keys`, () => {
      expect(Object.keys(dict[lang]).sort()).toEqual(base);
    });
    it(`dict.${lang} has no empty values`, () => {
      for (const [k, v] of Object.entries(dict[lang])) {
        expect(v, `${lang}.${k}`).toBeTruthy();
      }
    });
  }
});

describe("Landing copy parity", () => {
  const base = Object.keys(copy.en).sort();
  for (const lang of LANGS) {
    it(`copy.${lang} has exactly the en keys`, () => {
      expect(Object.keys(copy[lang]).sort()).toEqual(base);
    });
    it(`copy.${lang} arrays match en lengths`, () => {
      for (const key of ["scan", "how", "howModes", "features", "faq", "marquee"] as const) {
        expect(copy[lang][key].length, `${lang}.${key}`).toBe(copy.en[key].length);
      }
    });
  }
});
