# src/fix_coordinates_geocode_then_centroid.py
# Geocode from Location+Country first; centroid fallback; add Geo_Status.
# Now with: stronger text normalization (quotes/diacritics stripped),
# targeted fixes for {south, north, east, west, near, off, isle, french, new, united, great, democratic, ivory, camilitary},
# operator/military hints, substring/fuzzy NE matching, polygon imputation,
# and final nearest-country centroid fallback for ocean/ambiguous rows. Atomic CSV write.

import os, re, time, json, unicodedata, difflib
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

# ----------------- Config -----------------
INPUT  = "data/processed/cleaned_aircrashes_geo_FINAL.csv"
FINAL  = "data/processed/cleaned_aircrashes_geo_FINAL.csv"
SHAPE  = "ne_50m_admin_0_countries/ne_50m_admin_0_countries.shp"
CACHEF = "data/geocode_cache.csv"

# Allow env overrides
INPUT = os.getenv("GEO_INPUT", INPUT)
FINAL = os.getenv("GEO_FINAL", FINAL)
SHAPE = os.getenv("GEO_SHAPE", SHAPE)

LOG_FILE  = os.getenv("GEO_LOG_FILE",  "reports/geo_fix.log")
LIVE_FILE = os.getenv("GEO_LIVE_FILE", "reports/geo_status_live.txt")
PROGRESS_EVERY = max(1, int(os.getenv("PROGRESS_EVERY", "25")))
# Use a projected CRS for distance/nearest ops (prevents geographic distance warnings)
DIST_CRS = os.getenv("GEO_DIST_CRS", "EPSG:3857")

LEGACY_COLS = ["Geo_Status_1", "Coord_FixedReason", "Geo_Issue"]

# -------------- Country aliases --------------
COUNTRY_ALIASES = {
    # normal aliases (targets set to NE-canonical names)
    "usa": "United States of America", "u.s.a.": "United States of America", "united states": "United States of America",
    "uk": "United Kingdom", "great britain": "United Kingdom",
    "russia": "Russia",
    "south korea": "Republic of Korea", "north korea": "Democratic People's Republic of Korea",
    "ivory coast": "Côte d’Ivoire", "cote d'ivoire": "Côte d’Ivoire", "ivory": "Côte d’Ivoire",
    "dr congo": "Democratic Republic of the Congo", "democratic republic of congo": "Democratic Republic of the Congo",
    "congo": "Republic of the Congo",
    "swaziland": "Eswatini", "burma": "Myanmar", "cape verde": "Cabo Verde",
    "laos": "Lao People's Democratic Republic", "syria": "Syrian Arab Republic",
    "czech republic": "Czechia", "moldova": "Republic of Moldova",
    "macedonia": "North Macedonia",
    "bolivia": "Bolivia (Plurinational State of)", "tanzania": "United Republic of Tanzania",
    "belgian": "Belgium", "french": "France",

    # UK parts
    "england": "United Kingdom", "scotland": "United Kingdom", "wales": "United Kingdom",
    "northern ireland": "United Kingdom", "cheshire": "United Kingdom",
    "isle of man": "Isle of Man",

    # US states / territories + common typos -> USA
    "alaska": "United States of America", "akalaska": "United States of America", "alakska": "United States of America",
    "california": "United States of America", "calilfornia": "United States of America",
    "deleware": "United States of America", "illinois": "United States of America",
    "wyoming": "United States of America", "michigan": "United States of America",
    "wisconson": "United States of America", "norfork": "United States of America",
    "washingon": "United States of America", "texas": "United States of America",
    "puerto rico": "United States of America", "guam": "United States of America",
    "american samoa": "United States of America",

    # Canada
    "quebec": "Canada", "nwt": "Canada", "ellesmere": "Canada",

    # Australia
    "tasmania": "Australia", "new south wales": "Australia", "victoria": "Australia",

    # Spain / Portugal
    "catalonia": "Spain", "canary islands": "Spain", "spain moron": "Spain",
    "azores": "Portugal", "madeira": "Portugal", "terceira": "Portugal",

    # Italy / France islands
    "sicily": "Italy", "sardinia": "Italy", "corsica": "France",

    # China / Indonesia
    "hainan": "China", "yunan": "China",
    "bali": "Indonesia", "java": "Indonesia", "sumatra": "Indonesia", "sulawesi": "Indonesia",
    "lombok": "Indonesia",

    # Caribbean / Pacific
    "trinidad": "Trinidad and Tobago",
    "jamacia": "Jamaica",
    "cook": "Cook Islands",
    "guadaloupe": "France",  # FR overseas region in NE
    "hong kong": "Hong Kong S.A.R.", "hong": "Hong Kong S.A.R.",
    "papua": "Papua New Guinea",
    "micronesia": "Federated States of Micronesia",
    "marshall": "Marshall Islands", "marshall islands": "Marshall Islands",

    # single-word typos
    "morroco": "Morocco",
    "hrvatska": "Croatia",

    # weird embedded tokens
    "brazil loide": "Brazil", "brazil amazonaves": "Brazil", "india pawan": "India",

    # historical / airline artifacts
    "ussr": "Russia", "ussraeroflot": "Russia", "zaire": "Democratic Republic of the Congo",
    "tanganyika": "United Republic of Tanzania",
    "chechnya": "Russia",
    "uarmisrair": "Egypt",
    # let these be blank so Location drives geocoding if they appear alone
    "yugoslavia": "", "czechoslovakia": "",
}

# tokens that are NOT countries (directions, adjectives, etc.)
NOISE_TOKENS = {
    "near","off","new","democratic","united","south","north","west","east",
    "great","british","french","persian","isle","mount","prov","prov.","province","county","state","region"
}

NE_NAMES, NE_LOWER = [], []

# --------- Hints (operators/military) ----------
OPERATOR_HINTS = {
    "aeroflot": "Russia",
    "air france": "France",
    "royal air force": "United Kingdom", " raf ": "United Kingdom",
    "usaf": "United States of America", "u.s. air force": "United States of America",
    "united airlines": "United States of America",
    "egyptair": "Egypt",
    "air india": "India",
    "air canada": "Canada",
    "aerolineas argentinas": "Argentina", "aerolíneas argentinas": "Argentina",
    "emirates": "United Arab Emirates", "etihad": "United Arab Emirates", " uae ": "United Arab Emirates",
}

# -------------- Helpers --------------
def fold_lower(s: str) -> str:
    """ASCII-fold, drop punctuation/quotes, keep letters+spaces only, collapse spaces."""
    if not isinstance(s, str): return ""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii").lower()
    s = s.replace("'", " ")
    s = re.sub(r"[^a-z]+", " ", s)
    s = re.sub(r"\s{2,}", " ", s).strip()
    return s

def _preclean_country_text(name: str) -> str:
    return fold_lower(name)

def fuzzy_to_ne(name: str) -> str:
    if not name: return ""
    folded = fold_lower(name)
    if not folded or not NE_LOWER: return ""
    match = difflib.get_close_matches(folded, NE_LOWER, n=1, cutoff=0.84)
    if not match: return ""
    idx = NE_LOWER.index(match[0])
    return NE_NAMES[idx]

def normalize_country(name: str) -> str:
    if not isinstance(name, str) or not name.strip(): return ""
    base = _preclean_country_text(name)

    if "ussr" in base:
        return "Russia"

    if base in COUNTRY_ALIASES:
        target = COUNTRY_ALIASES[base]
        canon = fuzzy_to_ne(target)
        return canon or target

    if base in NOISE_TOKENS:
        return ""
    if " " not in base and len(base) <= 4:
        return ""

    cand = fuzzy_to_ne(base)
    if cand: return cand

    # substring fallback: choose longest NE name contained in text
    longest_len, longest_name = 0, ""
    folded = fold_lower(base)
    for ne_name, ne_low in zip(NE_NAMES, NE_LOWER):
        if ne_low and ne_low in folded and len(ne_low) > longest_len:
            longest_len, longest_name = len(ne_low), ne_name
    if longest_name:
        return longest_name

    return name.strip()

def clean_location(loc: str) -> str:
    if not isinstance(loc, str): return ""
    s = loc.strip()
    s = re.sub(r"^\s*(near|off)\s+", "", s, flags=re.I)
    s = re.sub(r"\b\d+(\.\d+)?\s*(nm|km|mi)\b.*$", "", s, flags=re.I)
    s = re.sub(r"\(.*?\)", "", s)
    s = re.sub(r"[\r\n\t]+", " ", s)
    s = re.sub(r"\s{2,}", " ", s)
    return s.strip(" -,")

def build_query(place: str, country: str) -> str:
    parts = [place.strip(), country.strip()]
    parts = [p for p in parts if p]
    seen = set(); out = []
    for p in parts:
        k = p.lower()
        if k and k not in seen:
            seen.add(k); out.append(p)
    return ", ".join(out)

def load_cache(path):
    if os.path.exists(path):
        try:
            df = pd.read_csv(path)
            if {"query","lat","lon"} <= set(df.columns):
                return {q: (float(lat), float(lon)) for q,lat,lon in df[["query","lat","lon"]].itertuples(index=False, name=None)}
        except Exception:
            pass
    return {}

def save_cache(cache_dict, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    rows = [{"query": q, "lat": lat, "lon": lon} for q,(lat,lon) in cache_dict.items()]
    pd.DataFrame(rows).to_csv(path, index=False)

def ensure_dirs_for(path: str):
    d = os.path.dirname(path)
    if d: os.makedirs(d, exist_ok=True)

def log(msg: str):
    msg = str(msg)
    print(msg, flush=True)
    try:
        ensure_dirs_for(LOG_FILE)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception:
        pass

def write_live_snapshot(**counts):
    ensure_dirs_for(LIVE_FILE)
    snapshot = {"ts": int(time.time()), **counts}
    try:
        with open(LIVE_FILE, "w", encoding="utf-8") as f:
            f.write(json.dumps(snapshot, ensure_ascii=False, indent=2))
    except Exception:
        pass

def safe_write_csv(df, path, attempts=3, sleep_s=1.0):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    for i in range(attempts):
        tmp = f"{path}.tmp.{os.getpid()}.{int(time.time())}.{i}"
        try:
            df.to_csv(tmp, index=False)
            try:
                os.replace(tmp, path)
                return True
            except PermissionError:
                try: os.remove(tmp)
                except Exception: pass
                time.sleep(sleep_s)
        except PermissionError:
            time.sleep(sleep_s)
    alt = re.sub(r"\.csv$", "", path) + f"__RUN_{time.strftime('%Y%m%d_%H%M%S')}.csv"
    df.to_csv(alt, index=False)
    log(f"WARNING: Could not overwrite {path}. Wrote fallback file -> {alt}")
    return False

# ------------ Text-based country inference ------------
def guess_country_from_text(text: str) -> str:
    if not isinstance(text, str) or not text.strip(): return ""
    s = fold_lower(text)
    tokens = [t for t in re.split(r"[^a-z]+", s) if t]
    for n in (3, 2, 1):
        for i in range(len(tokens)-n+1):
            phrase = " ".join(tokens[i:i+n])
            if phrase in NOISE_TOKENS or len(phrase) < 3:
                continue
            cand = fuzzy_to_ne(phrase)
            if cand: return cand
    return ""

def country_from_operator(op: str) -> str:
    s = " " + fold_lower(op) + " "
    for k, v in OPERATOR_HINTS.items():
        if k in s: return fuzzy_to_ne(v) or v
    if re.search(r"(air\s*force|army|military)", s):
        cand = guess_country_from_text(op)
        if cand: return cand
    return ""

def extract_after_token(text: str, token: str) -> str:
    if not isinstance(text, str): return ""
    s = " " + fold_lower(text) + " "
    m = re.search(rf"\b{token}\s+([a-z][a-z\s\-\.'’]+)", s)
    if not m: return ""
    phrase = m.group(1)
    phrase = re.split(r"[;,/]| coast| sea| ocean| gulf| bay| strait| channel", phrase)[0]
    return phrase.strip()

def resolve_directional_like(row) -> str:
    raw = fold_lower(str(row.get("Country/Region", "")))
    texts_join = " ".join([fold_lower(str(row.get(c, ""))) for c in
                           ("Location","Operator","Summary","Route","From","To","Airport") if c in row])

    if raw == "ivory": return "Côte d’Ivoire"
    if raw == "french":
        if "polynesia" in texts_join: return "French Polynesia"
        if "guiana" in texts_join: return "French Guiana"
        return "France"
    if raw == "isle":
        loc = fold_lower(str(row.get("Location","")))
        if "isle of man" in loc or " isle of man" in texts_join: return "Isle of Man"
        if "wight" in texts_join: return "United Kingdom"
        if "jersey" in texts_join: return "Jersey"
        if "guernsey" in texts_join: return "Guernsey"
        return "United Kingdom"
    if raw == "great":
        if "britain" in texts_join: return "United Kingdom"
        return "United Kingdom"

    if raw in {"off","near"}:
        ph = extract_after_token(str(row.get("Location","")), raw)
        if ph:
            cand = guess_country_from_text(ph) or fuzzy_to_ne(ph)
            if cand: return cand

    if raw == "south":
        if "africa" in texts_join: return "South Africa"
        if "sudan"  in texts_join: return "South Sudan"
        if "korea"  in texts_join: return "Republic of Korea"
    if raw == "north":
        if "korea" in texts_join: return "Democratic People's Republic of Korea"
        if "macedonia" in texts_join: return "North Macedonia"
    if raw == "east":
        if "timor" in texts_join: return "Timor-Leste"
        if "sahara" in texts_join: return "Western Sahara"
    if raw == "west":
        if "sahara" in texts_join: return "Western Sahara"
    if raw == "new":
        if "zealand" in texts_join: return "New Zealand"
        if "guinea"  in texts_join: return "Papua New Guinea"
        if "caledonia" in texts_join: return "New Caledonia"
    if raw == "democratic":
        if "congo" in texts_join or "zaire" in texts_join: return "Democratic Republic of the Congo"

    if raw == "united":
        if any(k in texts_join for k in ("arab emirates"," uae ","dubai","abu dhabi")):
            return "United Arab Emirates"
        if any(k in texts_join for k in ("kingdom","britain"," raf ")):
            return "United Kingdom"
        if any(k in texts_join for k in ("states"," u s "," usaf ")):
            return "United States of America"

    if raw == "camilitary" or " military" in texts_join or " air force" in texts_join:
        cand = guess_country_from_text(texts_join) or country_from_operator(row.get("Operator",""))
        if cand: return cand

    cand = country_from_operator(row.get("Operator",""))
    if cand: return cand
    cand = guess_country_from_text(texts_join)
    if cand: return cand
    return ""

# -------------- Main --------------
def main():
    start = time.time()
    ensure_dirs_for(LOG_FILE)
    try: os.remove(LOG_FILE)
    except FileNotFoundError: pass
    log("== Geo fix run started ==")

    if (not os.path.exists(INPUT)) or os.path.getsize(INPUT) == 0:
        log(f"ERROR: INPUT file '{INPUT}' is missing or empty. Set GEO_INPUT to a valid CSV and re-run.")
        return

    # 0) Read data
    df = pd.read_csv(INPUT, low_memory=False)
    df.drop(columns=[c for c in LEGACY_COLS if c in df.columns], inplace=True, errors="ignore")
    for c in ["Latitude","Longitude"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    log(f"Loaded {len(df):,} rows from {INPUT}")

    # 1) Countries + inside-point fallback
    countries = gpd.read_file(SHAPE)[["ADMIN","geometry"]].rename(columns={"ADMIN":"NE_Country"})
    if countries.crs is None or countries.crs.to_string().upper() != "EPSG:4326":
        countries = countries.set_crs("EPSG:4326", allow_override=True)
    countries["geometry"] = countries["geometry"].buffer(0)
    countries["rep_pt"] = countries.representative_point()
    # projected copy for distance/nearest ops
    countries_proj = countries.to_crs(DIST_CRS)

    # NE names
    global NE_NAMES, NE_LOWER
    NE_NAMES = countries["NE_Country"].dropna().astype(str).tolist()
    NE_LOWER = [fold_lower(x) for x in NE_NAMES]
    NE_SET_LOWER = set(NE_LOWER)

    rep = countries[["NE_Country", "rep_pt"]].copy()
    rep["rep_lat"] = rep["rep_pt"].y
    rep["rep_lon"] = rep["rep_pt"].x
    fallback_map = rep.set_index(rep["NE_Country"].apply(fold_lower))[["rep_lat","rep_lon"]].to_dict("index")
    log(f"Loaded {len(countries):,} country polygons")

    # 2) Points
    gdf = gpd.GeoDataFrame(
        df.copy(),
        geometry=gpd.points_from_xy(df["Longitude"], df["Latitude"]),
        crs="EPSG:4326"
    )

    # 3) Initial spatial check
    joined = gpd.sjoin(
        gdf, countries[["NE_Country","geometry"]],
        how="left", predicate="intersects", rsuffix="_r"
    )

    # 4) Geocoder + cache (+ offline probe)
    geolocator = Nominatim(user_agent="air-crashes-geo-cleaning")
    geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1.0, max_retries=1, swallow_exceptions=True)
    cache = load_cache(CACHEF)
    try:
        _probe = geocode("Montreal, Canada", addressdetails=False, timeout=3)
    except Exception:
        _probe = None
    if _probe is None:
        geocode = None
        log("Note: Geocoder unavailable; running in OFFLINE mode (OK + CENTROID only).")
    else:
        log("Geocoder reachable; running in ONLINE mode (GEOCODED where needed).")

    # Helper for OK check (folded compare)
    def in_declared_country(row) -> bool:
        declared = fold_lower(str(row.get("NE_Declared","")))
        hit      = fold_lower(str(row.get("NE_Country","")))
        return bool(declared) and bool(hit) and (declared == hit)

    # 5) Status setup + normalization/imputation/guess
    joined["Coord_Status"] = None

    # normalize declared
    joined["NE_Declared"] = joined["Country/Region"].apply(normalize_country)

    # EARLY: if still blank, try to infer from several free-text columns
    extra_cols = [c for c in ("Location","Operator","Summary","Route","From","To","Airport") if c in joined.columns]
    if extra_cols:
        empty_decl = joined["NE_Declared"].fillna("") == ""
        if empty_decl.any():
            for col in extra_cols:
                guessed = joined.loc[empty_decl, col].apply(guess_country_from_text)
                mask = empty_decl & guessed.ne("")
                joined.loc[mask, "NE_Declared"] = guessed[mask]
                empty_decl = joined["NE_Declared"].fillna("") == ""
                if not empty_decl.any(): break

    # Resolve directional/vague tokens explicitly
    DIRECTIONAL_TOKENS = {"south","north","east","west","near","off","new","isle","french","united","great","democratic","ivory","camilitary"}
    dir_mask = joined["Country/Region"].astype(str).apply(fold_lower).isin(DIRECTIONAL_TOKENS)
    if dir_mask.any():
        resolved = joined.loc[dir_mask].apply(resolve_directional_like, axis=1).fillna("")
        upd = resolved.ne("")
        if upd.any():
            joined.loc[dir_mask & upd, "NE_Declared"] = resolved[upd]

    # If declared not valid NE but point lies in a NE country, impute it
    valid_decl = joined["NE_Declared"].fillna("").apply(fold_lower).isin(NE_SET_LOWER)
    impute_mask = ~valid_decl & joined["NE_Country"].notna()
    joined.loc[impute_mask, "NE_Declared"] = joined.loc[impute_mask, "NE_Country"]

    # compute OK
    ok_mask = joined.apply(in_declared_country, axis=1).astype(bool)
    joined.loc[ok_mask, "Coord_Status"] = "OK"
    ok_count = int(ok_mask.sum())
    total = len(joined)
    log(f"OK (already inside declared country): {ok_count:,} / {total:,}")

    # rows to fix
    to_fix = ~ok_mask
    if "Location" in joined.columns:
        queries = joined.loc[to_fix].apply(
            lambda r: build_query(clean_location(str(r.get("Location",""))), str(r.get("NE_Declared",""))),
            axis=1
        )
    else:
        queries = joined.loc[to_fix, "NE_Declared"].fillna("")

    lats = joined["Latitude"].copy()
    lons = joined["Longitude"].copy()

    # live counters
    attempted = 0
    geocoded_count = 0

    # 6) Geocoding loop (if online)
    if geocode is not None:
        total_to_fix = int(to_fix.sum())
        log(f"To geocode: {total_to_fix:,} rows")
        for idx, q in queries.items():
            if joined.at[idx, "Coord_Status"] == "OK":
                continue
            qnorm = (q or "").strip()
            if not qnorm:
                continue

            attempted += 1
            lat = lon = None

            if qnorm in cache:
                lat, lon = cache[qnorm]
            else:
                loc = geocode(qnorm, addressdetails=True, timeout=10)
                if loc is not None:
                    lat, lon = loc.latitude, loc.longitude
                    cache[qnorm] = (lat, lon)
                    try:
                        country_from_geo = (loc.raw.get("address", {}) or {}).get("country")
                        if country_from_geo:
                            joined.at[idx, "NE_Declared"] = normalize_country(country_from_geo)
                    except Exception:
                        pass

            if lat is not None and lon is not None:
                lats.at[idx], lons.at[idx] = lat, lon
                joined.at[idx, "Coord_Status"] = "GEOCODED"
                geocoded_count += 1

            if attempted % PROGRESS_EVERY == 0 or attempted == total_to_fix:
                pending = total_to_fix - attempted
                write_live_snapshot(
                    ok=ok_count, geocoded=geocoded_count, centroid=0, no_country=0,
                    pending=pending, attempted=attempted, total=total
                )
                log(f"[Geocode] {attempted:,}/{total_to_fix:,} attempted | GEOCODED so far: {geocoded_count:,} | pending: {pending:,}")

    # 7) Fallbacks (centroid / nearest-country / or final NO_COUNTRY_MATCH)
    still = joined["Coord_Status"].isna()
    for idx in joined.index[still]:
        # 7a) try NE_Declared → NE canonical → centroid
        declared = str(joined.at[idx, "NE_Declared"])
        declared_ne = fuzzy_to_ne(declared) or declared
        key = fold_lower(declared_ne)
        info = fallback_map.get(key)

        # 7b) if no luck, try raw Country/Region normalized right now
        if not info:
            raw = normalize_country(str(joined.at[idx, "Country/Region"]))
            raw_ne = fuzzy_to_ne(raw) or raw
            key2 = fold_lower(raw_ne)
            info = fallback_map.get(key2)

        # 7c) last-resort: infer from any free text and centroid
        if not info:
            guess = ""
            for col in [c for c in ("Location","Operator","Summary","Route","From","To","Airport") if c in joined.columns]:
                if not guess:
                    # for "near/off" try extraction first
                    for tok in ("near","off"):
                        ph = extract_after_token(str(joined.at[idx, "Location"]), tok)
                        if ph:
                            guess = guess_country_from_text(ph) or fuzzy_to_ne(ph) or ""
                            if guess: break
                    if not guess:
                        guess = guess_country_from_text(str(joined.at[idx, col])) or country_from_operator(str(joined.at[idx, "Operator"]))
            if guess:
                joined.at[idx, "NE_Declared"] = guess
                info = fallback_map.get(fold_lower(guess))

        # 7d) still nothing? if we have lat/lon, snap to nearest country polygon (projected CRS)
        if not info:
            lat = lats.at[idx]; lon = lons.at[idx]
            if pd.notna(lat) and pd.notna(lon):
                pt = Point(float(lon), float(lat))
                pt_proj = gpd.GeoSeries([pt], crs="EPSG:4326").to_crs(DIST_CRS).iloc[0]
                dists = countries_proj.geometry.distance(pt_proj)
                if dists.notna().any():
                    j = int(dists.idxmin())
                    cand_country = str(countries.at[j, "NE_Country"])
                    joined.at[idx, "NE_Declared"] = cand_country
                    key3 = fold_lower(cand_country)
                    info = fallback_map.get(key3)

        if info:
            lats.at[idx] = info["rep_lat"]; lons.at[idx] = info["rep_lon"]
            joined.at[idx, "Coord_Status"] = "CENTROID"
        else:
            joined.at[idx, "Coord_Status"] = "NO_COUNTRY_MATCH"

    # 8) Write back and safety snap
    joined["Latitude"]  = lats
    joined["Longitude"] = lons
    joined["geometry"]  = gpd.points_from_xy(joined["Longitude"], joined["Latitude"], crs="EPSG:4326")

    chk = gpd.sjoin(
        joined[["NE_Declared","Coord_Status","geometry"]],
        countries[["NE_Country","geometry"]],
        how="left", predicate="intersects", rsuffix="_r"
    )
    bad = chk[(chk["NE_Country"].notna()) &
              (fold_lower(chk["NE_Declared"].astype(str)) != fold_lower(chk["NE_Country"].astype(str)))].index

    adjusted = 0
    for idx in bad:
        dec_ne = fuzzy_to_ne(str(joined.at[idx, "NE_Declared"])) or str(joined.at[idx, "NE_Declared"])
        info = fallback_map.get(fold_lower(dec_ne))
        if info:
            joined.at[idx, "Latitude"]  = info["rep_lat"]
            joined.at[idx, "Longitude"] = info["rep_lon"]
            if joined.at[idx, "Coord_Status"] == "GEOCODED":
                joined.at[idx, "Coord_Status"] = "GEOCODED_ADJUSTED"
            else:
                joined.at[idx, "Coord_Status"] = "ADJUSTED"
            adjusted += 1

    # 9) Save cache and final CSV
    save_cache(cache, CACHEF)

    out = joined.drop(columns=[c for c in joined.columns if c.startswith("index_") or c in ["geometry","NE_Country","rep_pt"]], errors="ignore")
    out.drop(columns=[c for c in LEGACY_COLS if c in out.columns], inplace=True, errors="ignore")
    if "Geo_Status" in out.columns:
        out.drop(columns=["Geo_Status"], inplace=True, errors="ignore")
    out["Geo_Status"] = out.pop("Coord_Status")

    os.makedirs(os.path.dirname(FINAL), exist_ok=True)
    safe_write_csv(out, FINAL)

    # final counts + live snapshot
    counts = out["Geo_Status"].value_counts(dropna=False)
    ok_final         = int(counts.get("OK", 0))
    geocoded_final   = int(counts.get("GEOCODED", 0) + counts.get("GEOCODED_ADJUSTED", 0))
    centroid_final   = int(counts.get("CENTROID", 0) + counts.get("ADJUSTED", 0))
    no_country_final = int(counts.get("NO_COUNTRY_MATCH", 0))
    write_live_snapshot(
        ok=ok_final, geocoded=geocoded_final, centroid=centroid_final,
        no_country=no_country_final, pending=0, attempted=attempted, total=total
    )

    log("Summary (Geo_Status):")
    log(counts.to_string())
    if adjusted:
        log(f"Adjusted to inside-country points: {adjusted:,}")
    log(f"Wrote -> {FINAL}")
    log(f"Cache file -> {CACHEF}")
    elapsed = time.time() - start
    log(f"Done in {elapsed:,.1f}s")

if __name__ == "__main__":
    main()
