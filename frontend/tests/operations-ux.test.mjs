import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const onboarding = readFileSync(new URL("../src/routes/onboarding.tsx", import.meta.url), "utf8");
const headscale = readFileSync(new URL("../src/routes/headscale.tsx", import.meta.url), "utf8");
const i18n = readFileSync(new URL("../src/lib/i18n.tsx", import.meta.url), "utf8");
const telegram = readFileSync(new URL("../src/routes/telegram.tsx", import.meta.url), "utf8");
const root = readFileSync(new URL("../src/routes/__root.tsx", import.meta.url), "utf8");
const analytics = readFileSync(new URL("../src/routes/analytics.tsx", import.meta.url), "utf8");
const api = readFileSync(new URL("../src/lib/api.ts", import.meta.url), "utf8");
const map = readFileSync(
  new URL("../src/components/StationMap.client.tsx", import.meta.url),
  "utf8",
);

test("onboarding inventory search is debounced and defaults to pending", () => {
  assert.match(onboarding, /useDebounced\(queryText\)/);
  assert.match(onboarding, /useState<\(typeof INVENTORY_FILTERS\)\[number\]>\("pending"\)/);
  assert.match(onboarding, /getStationInventory\(view, query, signal\)/);
  assert.match(onboarding, /Search code, name, city, district, area, address, VPN/);
});

const dashboard = readFileSync(new URL("../src/routes/index.tsx", import.meta.url), "utf8");
const stations = readFileSync(new URL("../src/routes/stations.tsx", import.meta.url), "utf8");
const mapRoute = readFileSync(new URL("../src/routes/map.tsx", import.meta.url), "utf8");
const router = readFileSync(new URL("../src/router.tsx", import.meta.url), "utf8");

test("live routes share React Query, stable keys, and cancellable request signals", () => {
  for (const source of [dashboard, stations, mapRoute, headscale, onboarding]) {
    assert.match(source, /useQuery/);
    assert.match(source, /queryKey:/);
    assert.match(source, /signal/);
  }
  assert.match(router, /staleTime: 15_000/);
  assert.match(router, /refetchOnWindowFocus: false/);
  assert.match(stations, /placeholderData: keepPreviousData/);
  assert.match(headscale, /placeholderData: keepPreviousData/);
});

test("loading, successful empty, error, and retry states are distinct", () => {
  assert.match(stations, /stationsQuery\.data[\s\S]{0,80}\? `\$\{total\}/);
  assert.ok(stations.includes("stationsQuery.isSuccess"));
  assert.ok(stations.includes("!stationsQuery.isPlaceholderData"));
  assert.match(mapRoute, /stationsQuery\.isSuccess && unplaced\.length === 0/);
  assert.ok(headscale.includes("nodesQuery.isSuccess"));
  assert.ok(headscale.includes("!nodesQuery.isPlaceholderData"));
  assert.match(onboarding, /inventoryQuery\.isPending/);
  for (const source of [dashboard, stations, mapRoute, headscale, onboarding]) {
    assert.match(source, /common\.retry/);
  }
});

test("dashboard attention count and recovery explanation remain canonical", () => {
  assert.match(dashboard, /top_problem_stations\.length/);
  assert.match(dashboard, /dashboard\.of/);
  assert.match(dashboard, /dashboard\.attentionSubtext/);
  assert.match(dashboard, /recovery_samples/);
  assert.match(dashboard, /degraded_enter_latency_ms/);
  assert.match(dashboard, /overall_reason_code/);
});

test("onboarding avoids initial duplicate report and inventories are paginated", () => {
  assert.match(onboarding, /enabled: view === "suspected_duplicate"/);
  assert.match(api, /page: true/);
  assert.match(headscale, /limit: PAGE_SIZE/);
  assert.match(headscale, /offset: \(page - 1\) \* PAGE_SIZE/);
});

test("changed loading and attention strings exist in RU, TJ, and EN", () => {
  for (const key of [
    "loading.dashboard",
    "loading.stations",
    "loading.headscale",
    "dashboard.attentionTitle",
    "dashboard.attentionSubtext",
    "dashboard.viewAll",
  ]) {
    assert.equal(i18n.split(`"${key}"`).length - 1, 3, key);
  }
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

test("authenticated presence heartbeat follows visible-tab activity", () => {
  assert.match(root, /document\.visibilityState === "visible"/);
  assert.match(root, /setInterval\(heartbeat, 60_000\)/);
  assert.match(root, /visibilitychange/);
  assert.match(root, /isAuthenticated\(\)/);
});

test("operator activity is admin-only and uses Dushanbe time and required filters", () => {
  assert.match(telegram, /user\?\.role !== "admin"/);
  assert.match(telegram, /Asia\/Dushanbe/);
  assert.match(telegram, /City Skyline activity, not Telegram presence/);
  assert.match(telegram, /startDate/);
  assert.match(telegram, /endDate/);
  assert.match(telegram, /workflow_status/);
  assert.match(telegram, /before_data/);
  assert.match(telegram, /after_data/);
});

test("onboarding shows audited station actor and operator-created filter", () => {
  assert.match(onboarding, /operator_created/);
  assert.match(onboarding, /created_by_username/);
  assert.match(onboarding, /last_updated_by_username/);
});

test("map renders status-specific duration rows without online Offline dash contradiction", () => {
  assert.match(map, /station\.status === "online"/);
  assert.match(map, /Online for:/);
  assert.match(map, /station\.status === "offline"/);
  assert.doesNotMatch(map, /Offline:\s*\{station\.status/);
  assert.match(map, /overall_reason_code/);
});

test("report export downloads a Blob with current filters and prevents double clicks", () => {
  assert.match(api, /response\.blob\(\)/);
  assert.match(api, /Content-Disposition/);
  assert.match(api, /URL\.createObjectURL/);
  assert.match(analytics, /if \(exporting\) return/);
  assert.match(analytics, /disabled=\{loading \|\| exporting !== null\}/);
  assert.match(analytics, /district \? Number\(district\)/);
  assert.match(analytics, /station \? Number\(station\)/);
  assert.match(analytics, /status \|\| undefined/);
});
