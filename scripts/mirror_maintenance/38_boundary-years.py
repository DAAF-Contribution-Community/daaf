# --- Config ---
# INTENT: For every LIVE endpoint (37 probe status==200), probe the FIRST and LAST year of its
#         years_available (count retrieval only) to verify the catalog's advertised coverage
#         boundaries. A boundary year returning 404 or 0 rows is a catalog-OVERSTATEMENT finding
#         (0 rows may be legitimate for some subgroup endpoints — record, do NOT fail).
# REASONING: The prior audit only boundary-checked IPEDS finance; this generalizes verified year
#            ranges to all live routes, producing the per-route verified coverage the regeneration
#            pass needs. Non-year segment values are sourced from 37's example_url (Portal-valid).
# ASSUMES: 37 wrote 37_live_probe_inventory.parquet with route_template, example_url,
#          years_available, status. DRF `count` is the full filtered total. stdlib urllib only.
import json
import re
import time
import urllib.request
import urllib.error
from pathlib import Path
import polars as pl

PROJECT_DIR = Path("/daaf/research/2026-08-06_FrameworkDev_MirrorV2Update")
OUT_DIR = PROJECT_DIR / "2026-08-07_endpoint-ground-truth"
IN_PARQUET = OUT_DIR / "37_live_probe_inventory.parquet"
OUT_PARQUET = OUT_DIR / "38_boundary_years.parquet"
BASE = "https://educationdata.urban.org"
UA = {"User-Agent": "daaf-endpoint-audit/1.0"}


def http_get_status(url, timeout=60, retries=3):
    last_err = ""
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return resp.status, (data.get("count") if isinstance(data, dict) else None), ""
        except urllib.error.HTTPError as e:
            return e.code, None, f"HTTPError {e.code}"
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last_err = f"{type(e).__name__}: {e}"
            time.sleep(2 ** attempt)
    return None, None, f"CONN_ERROR: {last_err}"


def parse_years(s):
    if s is None:
        return []
    t = (s.replace("&ndash;", "-").replace("&#8211;", "-")
          .replace("–", "-").replace("—", "-").replace("‒", "-").replace("‐", "-"))
    years = set()
    for tok in t.split(","):
        nums = re.findall(r"\d{4}", tok)
        if len(nums) >= 2:
            a, b = int(nums[0]), int(nums[1])
            if a <= b:
                years.update(range(a, b + 1))
        elif len(nums) == 1:
            years.add(int(nums[0]))
    return sorted(years)


def build_probe_url(template, example, year):
    # INTENT: concrete path substituting the given boundary year for {year} and example-segment
    #         values for any other {placeholder} (Portal-valid concretization).
    tparts = template.strip("/").split("/")
    eparts = example.strip("/").split("/") if example else []
    out = []
    for i, seg in enumerate(tparts):
        if seg.startswith("{") and seg.endswith("}"):
            name = seg.strip("{}")
            if name == "year":
                out.append(str(year))
            elif i < len(eparts):
                out.append(eparts[i])
            else:
                out.append(seg)
        else:
            out.append(seg)
    return "/" + "/".join(out) + "/"


# --- Load: live endpoints from 37 ---
inv = pl.read_parquet(IN_PARQUET)
live = inv.filter(pl.col("status") == 200)
print(f"Loaded 37 inventory: {inv.height} rows; live (200): {live.height}")

# --- Probe: first & last year of each live endpoint's years_available ---
records = []
rows = live.iter_rows(named=True)
live_list = list(rows)
for i, r in enumerate(live_list, start=1):
    years = parse_years(r["years_available"])
    if not years:
        print(f"  id={r['endpoint_id']} {r['route_template']}: no parseable years; skip")
        continue
    for boundary, yr in (("first", years[0]), ("last", years[-1])):
        path = build_probe_url(r["route_template"], r["example_url"], yr)
        probed_url = f"{BASE}{path}?limit=1"
        status, count, note = http_get_status(probed_url)
        anomaly = ""
        if status == 404:
            anomaly = "404-OVERSTATEMENT"
        elif status == 200 and (count == 0):
            anomaly = "ZERO-ROWS"
        print(f"[{i}/{len(live_list)}] id={r['endpoint_id']} {r['route_template']} "
              f"{boundary}={yr} -> {status} count={count} {anomaly}")
        records.append({
            "endpoint_id": r["endpoint_id"],
            "section": r["section"],
            "route_template": r["route_template"],
            "years_available": r["years_available"],
            "boundary": boundary,
            "year": yr,
            "probed_url": probed_url,
            "status": status,
            "count": count,
            "anomaly": anomaly,
            "error_note": note,
        })
        time.sleep(1.0)  # polite pacing

# --- Save ---
df = pl.DataFrame(records)
df.write_parquet(OUT_PARQUET)
print(f"\nSaved: {OUT_PARQUET}  shape={df.shape}")

# --- Validate ---
assert df.height > 0, "No boundary probes recorded"
print(f"VALIDATION: rows={df.height} PASS")
print("\n=== BOUNDARY-YEAR ANOMALIES ===")
anom = df.filter(pl.col("anomaly") != "")
if anom.height == 0:
    print("  (none — all boundary years returned 200 with >0 rows)")
for r in anom.iter_rows(named=True):
    print(f"  id={r['endpoint_id']} {r['route_template']} {r['boundary']}={r['year']} "
          f"-> {r['status']} count={r['count']} [{r['anomaly']}]")
