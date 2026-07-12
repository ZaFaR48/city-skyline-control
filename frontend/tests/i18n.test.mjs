import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const i18n = readFileSync(new URL("../src/lib/i18n.tsx", import.meta.url), "utf8");
const types = readFileSync(new URL("../src/lib/types.ts", import.meta.url), "utf8");
const onboarding = readFileSync(new URL("../src/routes/onboarding.tsx", import.meta.url), "utf8");
const activation = readFileSync(new URL("../src/routes/activate.tsx", import.meta.url), "utf8");

test("Russian is the default and RU/TJ/EN are persisted", () => {
  assert.match(i18n, /DEFAULT_LANGUAGE: Language = "ru"/);
  assert.match(i18n, /\["ru", "tj", "en"\]/);
  assert.match(i18n, /localStorage\.setItem\(LANGUAGE_STORAGE_KEY, next\)/);
});

test("activation success renders the exact backend username", () => {
  assert.match(activation, /result\.username/);
  assert.match(activation, /navigator\.clipboard\.writeText\(result\.username\)/);
});

test("internal role and district values remain canonical", () => {
  assert.match(types, /"admin" \| "operator" \| "viewer"/);
  for (const district of ["Ismoili Somoni", "Shohmansur", "Sino", "Firdavsi"]) {
    assert.ok(onboarding.includes(`"${district}"`));
  }
});

test("operator presence and activity labels have Russian and Tajik translations", () => {
  for (const label of [
    "Operator Activity",
    "Application presence",
    "Recently active",
    "All workflow states",
    "From (Dushanbe)",
    "City Skyline activity, not Telegram presence",
  ]) {
    assert.ok(i18n.includes(`"${label}"`));
  }
});
