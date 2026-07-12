import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const onboarding = readFileSync(new URL("../src/routes/onboarding.tsx", import.meta.url), "utf8");
const headscale = readFileSync(new URL("../src/routes/headscale.tsx", import.meta.url), "utf8");
const i18n = readFileSync(new URL("../src/lib/i18n.tsx", import.meta.url), "utf8");

test("onboarding inventory search is debounced and defaults to pending", () => {
  assert.match(onboarding, /useDebounced\(queryText\)/);
  assert.match(onboarding, /useState<\(typeof INVENTORY_FILTERS\)\[number\]>\("pending"\)/);
  assert.match(onboarding, /getStationInventory\(view, query\)/);
  assert.match(onboarding, /Search code, name, city, district, area, address, VPN/);
});

test("publication search reloads the pending view after approval", () => {
  assert.match(onboarding, /getStationApprovalInventory\(filter, query\)/);
  assert.match(onboarding, /setFilter\] = useState<"pending" \| "approved" \| "all">\("pending"\)/);
  assert.match(onboarding, /await load\(\)/);
});

test("headscale search is debounced and combined with filters", () => {
  assert.match(headscale, /const query = useDebounced\(queryText\)/);
  assert.match(headscale, /q: query/);
  assert.match(headscale, /approval_status: filters\.approval/);
  assert.match(headscale, /Search node, VPN, or station/);
});

test("safe backend error detail is preserved for operational pages", () => {
  assert.match(i18n, /if \(detail && !detail\.startsWith\("Request failed"\)\) return detail/);
});
