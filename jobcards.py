"""
Job cards from the Google Forms (B2B + Rental).

  Google Sheet (form responses) ──sync_from_google()──▶ form_job_cards (portal DB)
  portal Save ──push_to_excel()──▶ OneDrive "Job Card Data - FleetCo.xlsx" (same instant)

The team's columns (TSM - JOB STATUS, TSM OBSERVATION, RCA, costs ...) are edited only in the
portal; the existing Excel sync (sync_job_cards.py) never touches them, so nothing fights.

Microsoft Graph settings come from st.secrets["graph"] or GRAPH_* env vars:
  tenant_id, client_id, client_secret, user (owner of the OneDrive "Automation Data" folder)

  py jobcards.py sync            Google Sheet + Price Master → DB, recalculate costs, write pending to Excel
  py jobcards.py import-team X   one-time: team columns from the Excel file X into the DB
"""
import datetime as dt, io, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request
import openpyxl
from sqlalchemy import text

def _setting(section, key, env):
    try:
        import streamlit as st
        if section in st.secrets and st.secrets[section].get(key):
            return str(st.secrets[section][key])
    except Exception:
        pass
    return os.getenv(env, "")


# Google Sheet that collects the job card form responses — empty = demo mode (no sync)
GOOGLE_SHEET = _setting("google", "sheet_id", "GOOGLE_SHEET_ID")


def google_enabled():
    return bool(GOOGLE_SHEET)
EXCEL_FILE = "Automation Data/Job Card Data/Job Card Data - FleetCo.xlsx"
RENTAL_CLIENT = "FleetCo Rental Fleet"

# job_type → Google tab, Excel table, job card no column
SOURCES = {
    "B2B":    {"tab": "B2B - Job Card",          "table": "B2B_Job_Card",    "no": "Job card No"},
    "Rental": {"tab": "Rental - Job Card", "table": "Rental_Job_Card", "no": "Job Card No"},
}

# form questions in the sheet's order (JSONB doesn't keep order); new questions go at the end
FORM_ORDER = {
    "B2B": ["Job card No", "Timestamp", "Client/Partner Name", "Site Location", "Store Location", "Service Type",
            "Paid Replaced Spares", "General Service", "Consumed Spares on General Service",
            "Warranty Parts Replaced", "Warranty Part Serial Number", "Image Evidence",
            "Non - Warranty Parts Replaced", "Image Evidence 2", "Chassis Number", "ODO Meter Run",
            "Job Addressed By", "Field Observation", "Job Status", "Job Completion Date",
            "Job Card Closure Delay Reason", "Accidental Vehicle Image Reference", "Accidental Vehicle Documentation"],
    "Rental": ["Job Card No", "Timestamp", "Job Card Purpose", "Chassis Number", "ODO Meter Run", "Service Type",
               "Recovery Taken By", "List Out The Missing Components", "List Out The Damaged Components",
               "Damaged Component Image Evidence", "Offline Veh Replaced Spares", "Offline Vehicle Status",
               "Accidental Vehicle Image Reference", "Accidental Vehicle Documentation",
               "Non - Warranty Parts Replaced", "Non - Warranty Part Serial Number",
               "Non - Warranty Part - Image Evidence", "Warranty Parts Replaced", "Warranty Part Serial Number",
               "Warranty Part - Image Evidence", "Paid - Replaced Spares", "General Service Type",
               "Consumed Spares Lists", "Job Reported by", "Job Status", "Job Completion Date",
               "Pending Reason (If Job Not Yet Completed)"],
}


def form_columns(job_types, present):
    """Column order for showing form answers of these job types (sheet order first)."""
    order = []
    for jt in job_types:
        order += [c for c in FORM_ORDER.get(jt, []) if c not in order]
    return [c for c in order if c in present] + sorted(c for c in present if c not in order)


# portal column → Excel header (the team's columns; formula columns are left to Excel)
TEAM_COLS = {
    "tsm_job_status":       "TSM - JOB STATUS",
    "complaint_category":   "COMPLAINT CATAGEORY",
    "tsm_observation":      "TSM OBSERVATION",
    "repeat_complaints":    "REPEAT COMPLAINTS",       # B2B only
    "action_date":          "ACTION DATE",
    "rca":                  "RCA",
    "spares_cost":          "SPARES COST",
    "labor_cost":           "LABOR COST",
    "warranty_status":      "WARRNTY STATUS",
    "warranty_spares_cost": "WARRANTY SPARES COST",
    "warranty_labor_cost":  "WARRANTY LABOR COST",
}
DATE_COLS = {"action_date"}
MONEY_COLS = {"spares_cost", "labor_cost", "warranty_spares_cost", "warranty_labor_cost"}
EPOCH = dt.datetime(1899, 12, 30)


def low(s):
    return re.sub(r"\s+", " ", str(s or "")).strip().lower()


def clean(v):
    """Sheet value → plain text (None for blanks)."""
    if v is None:
        return None
    if isinstance(v, dt.datetime):
        return v.isoformat(sep=" ", timespec="seconds")
    if isinstance(v, dt.date):
        return v.isoformat()
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    s = str(v).strip()
    return s or None


def to_date(v):
    if v in (None, "", "-"):
        return None
    if isinstance(v, dt.datetime):
        return v.date()
    if isinstance(v, dt.date):
        return v
    if isinstance(v, (int, float)):                     # Excel serial
        return (EPOCH + dt.timedelta(days=float(v))).date()
    for fmt in ("%d/%m/%y", "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%d-%b-%y", "%d-%b-%Y"):
        try:
            return dt.datetime.strptime(str(v).strip(), fmt).date()
        except ValueError:
            pass
    return None


def to_money(v):
    if v in (None, "", "-"):
        return None
    try:
        return round(float(str(v).replace(",", "").replace("₹", "").strip()), 2)
    except ValueError:
        return None


def to_ts(v):
    if isinstance(v, dt.datetime):
        return v
    try:
        return dt.datetime.fromisoformat(str(v)) if v else None
    except ValueError:
        return None


# ═══════════════════════════ Google Sheet → DB ═══════════════════════════
def fetch_google():
    """{job_type: [ {header: value} ]} straight from the form responses sheet."""
    url = f"https://docs.google.com/spreadsheets/d/{GOOGLE_SHEET}/export?format=xlsx"
    with urllib.request.urlopen(url, timeout=120) as r:
        wb = openpyxl.load_workbook(io.BytesIO(r.read()), read_only=True, data_only=True)
    out = {}
    for jt, src in SOURCES.items():
        rows = wb[src["tab"]].iter_rows(values_only=True)
        head = [str(h).strip() if h is not None else "" for h in next(rows)]
        ki = [low(h) for h in head].index(low(src["no"]))
        out[jt] = [{h: r[i] for i, h in enumerate(head) if h and i < len(r)}
                   for r in rows if r and ki < len(r) and str(r[ki] or "").strip()]
    return out


def _pick(row, *names):
    lk = {low(k): v for k, v in row.items()}
    for n in names:
        v = clean(lk.get(low(n)))
        if v:
            return v
    return None


def parse_row(jt, row):
    """One sheet row → the portal's columns."""
    ts = row.get("Timestamp")
    ts = ts if isinstance(ts, dt.datetime) else to_ts(clean(ts))
    if jt == "B2B":
        client = _pick(row, "Client/Partner Name")
        location = _pick(row, "Site Location", "Store Location")
        tech = _pick(row, "Job Addressed By")
        obs = _pick(row, "Field Observation")
    else:
        client = RENTAL_CLIENT
        purpose = _pick(row, "Job Card Purpose") or ""
        location = purpose.split("-")[-1].strip() if "-" in purpose else "Central Hub"
        tech = _pick(row, "Job Reported by", "Recovery Taken By")
        obs = _pick(row, "List Out The Damaged Components", "Consumed Spares Lists", "Paid - Replaced Spares")
    return {
        "job_type": jt,
        "job_card_no": _pick(row, SOURCES[jt]["no"]),
        "submitted_at": ts,
        "job_open_date": ts.date() if ts else None,
        "client_name": client,
        "client_location": location,
        "service_type": _pick(row, "Service Type"),
        "chassis_number": _pick(row, "Chassis Number"),
        "odo_km": _pick(row, "ODO Meter Run"),
        "technician": tech,
        "field_observation": obs,
        "form_job_status": _pick(row, "Job Status"),
        "completion_date": to_date(row.get("Job Completion Date")),
        "form": json.dumps({k: clean(v) for k, v in row.items()}, ensure_ascii=False),
    }


def map_location(locs, jt, client, location):
    """client_locations row for a job card: rental → the rental row; otherwise same client
    (any case) and, if the client has several rows, the matching location (or its 'all locations' row)."""
    if jt == "Rental":
        return next((l["location_id"] for l in locs if l["is_rental"]), None)
    cands = [l for l in locs if low(l["client_name"]) == low(client) and not l["is_rental"]]
    if len(cands) == 1:
        return cands[0]["location_id"]
    exact = [l for l in cands if l["location"] and low(l["location"]) == low(location)]
    if exact:
        return exact[0]["location_id"]
    allrow = [l for l in cands if not l["location"]]
    return allrow[0]["location_id"] if allrow else None


FORM_COLS = ["submitted_at", "job_open_date", "client_name", "client_location", "service_type",
             "chassis_number", "odo_km", "technician", "field_observation", "form_job_status",
             "completion_date", "form"]


def sync_from_google(engine):
    """Add new job cards and refresh form answers. Never touches the team's columns."""
    if not google_enabled():
        return 0, 0                               # demo mode: job cards come from the demo data
    data = fetch_google()
    with engine.begin() as c:
        locs = [dict(r._mapping) for r in c.execute(text(
            "SELECT location_id, client_name, location, is_rental FROM client_locations"))]   # inactive too: keeps old job cards linked
        have = {(r[0], r[1]): (r[2], r[3]) for r in c.execute(text(
            "SELECT job_type, job_card_no, form, client_location_id FROM form_job_cards"))}
        changed, n = [], 0
        for jt, rows in data.items():
            for row in rows:
                p = parse_row(jt, row)
                if not p["job_card_no"]:
                    continue
                n += 1
                p["loc"] = map_location(locs, jt, p["client_name"], p["client_location"])
                old = have.get((jt, p["job_card_no"]))
                if old is None or old[0] != json.loads(p["form"]) or old[1] != p["loc"]:
                    changed.append(p)     # only new / changed rows go to the DB (fast on Supabase)
        if changed:
            cols = ["job_type", "job_card_no", "loc"] + FORM_COLS
            _bulk(c, f"""
                INSERT INTO form_job_cards (job_type, job_card_no, client_location_id, {", ".join(FORM_COLS)})
                VALUES %s
                ON CONFLICT (job_type, job_card_no) DO UPDATE SET
                    client_location_id = EXCLUDED.client_location_id,
                    {", ".join(f"{k} = EXCLUDED.{k}" for k in FORM_COLS)},
                    synced_at = NOW()
            """, [tuple(p[k] for k in cols) for p in changed],
                template="(" + ", ".join("%s::jsonb" if k == "form" else "%s" for k in cols) + ")")
        added = sum(1 for p in changed if (p["job_type"], p["job_card_no"]) not in have)
        msg = f"{n} job cards read, {added} new, {len(changed) - added} updated"
        c.execute(text("""INSERT INTO sync_state (name, last_run, message) VALUES ('google_jobcards', NOW(), :m)
                          ON CONFLICT (name) DO UPDATE SET last_run = NOW(), message = :m"""), {"m": msg})
    return added, n


def last_sync(engine):
    """(last sync time in IST, seconds since) — both from the DB clock, so server time zones don't matter."""
    with engine.connect() as c:
        r = c.execute(text("""
            SELECT (last_run AT TIME ZONE current_setting('TimeZone')) AT TIME ZONE 'Asia/Kolkata',
                   EXTRACT(EPOCH FROM LOCALTIMESTAMP - last_run)
            FROM sync_state WHERE name = 'google_jobcards'""")).first()
    return (r[0], float(r[1])) if r else (None, None)


# ═══════════════════════════ DB → OneDrive Excel ═══════════════════════════
_tok = {"v": None, "until": 0}


def graph_settings():
    cfg = {}
    try:
        import streamlit as st
        if "graph" in st.secrets:
            cfg = dict(st.secrets["graph"])
    except Exception:
        pass
    for k in ("tenant_id", "client_id", "client_secret", "user"):
        cfg.setdefault(k, os.getenv(f"GRAPH_{k.upper()}"))
    return cfg if all(cfg.get(k) for k in ("tenant_id", "client_id", "client_secret", "user")) else None


def _req(method, url, body=None, headers=None):
    req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            b = r.read()
            return json.loads(b) if b else {}
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Graph {method} → HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:300]}") from None


def _token(cfg):
    if _tok["v"] and time.time() < _tok["until"]:
        return _tok["v"]
    body = urllib.parse.urlencode({"client_id": cfg["client_id"], "client_secret": cfg["client_secret"],
                                   "scope": "https://graph.microsoft.com/.default",
                                   "grant_type": "client_credentials"}).encode()
    j = _req("POST", f"https://login.microsoftonline.com/{cfg['tenant_id']}/oauth2/v2.0/token", body,
             {"Content-Type": "application/x-www-form-urlencoded"})
    _tok.update(v=j["access_token"], until=time.time() + j.get("expires_in", 3600) - 300)
    return _tok["v"]


def _workbook_url(cfg):
    """Graph path (after /v1.0) of the job card workbook's workbook API."""
    path = "/".join(urllib.parse.quote(p) for p in EXCEL_FILE.split("/"))
    return f"/users/{urllib.parse.quote(cfg['user'])}/drive/root:/{path}:/workbook"


def _col_letter(i):
    s, i = "", i + 1
    while i:
        i, rem = divmod(i - 1, 26)
        s = chr(65 + rem) + s
    return s


def _excel_value(col, v):
    if v is None or (isinstance(v, float) and v != v):
        return ""
    if col in DATE_COLS:
        d = to_date(v)
        return (dt.datetime.combine(d, dt.time()) - EPOCH).days if d else ""
    if col in MONEY_COLS:
        return float(v)
    return str(v)


def push_to_excel(engine, job_id, cache=None):
    """Write one job card's team columns into its Excel row. Returns (ok, message).
    On failure the job card stays excel_pending and is retried by the next sync.
    cache: a dict shared across calls, so a batch reads each Excel table's layout once."""
    with engine.connect() as c:
        job = c.execute(text(f"SELECT job_type, job_card_no, {', '.join(TEAM_COLS)} FROM form_job_cards WHERE id = :i"),
                        {"i": job_id}).mappings().first()
    if not job:
        return False, "job card not found"
    cfg = graph_settings()
    if not cfg:
        return _mark(engine, job_id, False, "Excel connection not set up (graph secrets missing)")
    try:
        H = {"Authorization": f"Bearer {_token(cfg)}"}
        wb = _workbook_url(cfg)
        g = "https://graph.microsoft.com/v1.0"
        t = f"{wb}/tables('{SOURCES[job['job_type']]['table']}')"
        cache = {} if cache is None else cache
        if job["job_type"] not in cache:
            hdr = _req("GET", f"{g}{t}/headerRowRange?$select=values,address", headers=H)
            head = [low(h) for h in hdr["values"][0]]
            no_col = head.index(low(SOURCES[job["job_type"]]["no"]))
            nos = _req("GET", f"{g}{t}/columns/itemAt(index={no_col})/dataBodyRange?$select=values", headers=H)["values"]
            # the table's formula columns ([#This Row] formulas are the same on every row)
            r0 = _req("GET", f"{g}{t}/rows/itemAt(index=0)/range?$select=formulas,numberFormat", headers=H)
            cache[job["job_type"]] = (hdr["address"], head, nos, r0["formulas"][0], r0["numberFormat"][0])
        address, head, nos, row0, fmt0 = cache[job["job_type"]]
        sheet, first, top = re.match(r"^(.*)!\$?([A-Z]+)\$?(\d+)", address).groups()
        x0 = sum((ord(ch) - 64) * 26 ** i for i, ch in enumerate(reversed(first))) - 1
        idx = next((i for i, v in enumerate(nos) if str(v[0]).strip() == job["job_card_no"]), None)
        if idx is None:
            return _mark(engine, job_id, False, "not in Excel yet (the Excel sync adds it within 30 min) — will retry")
        row = int(top) + 1 + idx
        ws = f"{wb}/worksheets('{urllib.parse.quote(sheet.strip(chr(39)))}')"
        # the team's columns sit side by side → ONE range update for the whole row; the formula
        # columns in between (Total Revenue, Total Warranty Cost) get their own formula back
        cols = {head.index(low(eh)): col for col, eh in TEAM_COLS.items() if low(eh) in head}
        lo, hi = min(cols), max(cols)
        between = [i for i in range(lo, hi + 1) if i not in cols]
        if any(not str(row0[i]).startswith("=") for i in between):
            raise RuntimeError("unexpected column between the team columns — Excel layout changed")

        def cell(i):
            if i not in cols:
                return row0[i]
            v = _excel_value(cols[i], job[cols[i]])
            return "'" + v if isinstance(v, str) and v[:1] in "=+-@" and v else v    # text never becomes a formula
        formulas = [cell(i) for i in range(lo, hi + 1)]
        fmts = ["dd-mm-yyyy" if i in cols and cols[i] in DATE_COLS and job[cols[i]] else fmt0[i]
                for i in range(lo, hi + 1)]
        addr = f"{_col_letter(x0 + lo)}{row}:{_col_letter(x0 + hi)}{row}"
        body = json.dumps({"formulas": [formulas], "numberFormat": [fmts]}).encode()
        hdrs = dict(H, **{"Content-Type": "application/json"}, **cache.get("session", {}))
        for attempt in range(3):                     # Excel online sometimes answers "busy" — try again
            try:
                _req("PATCH", f"{g}{ws}/range(address='{addr}')", body, hdrs)
                break
            except RuntimeError as e:
                if attempt == 2 or not re.search(r"HTTP (409|429|5\d\d)", str(e)):
                    raise
                time.sleep(2 * (attempt + 1))
        return _mark(engine, job_id, True, f"Excel row {row} updated")
    except Exception as e:
        return _mark(engine, job_id, False, str(e)[:300])


def _mark(engine, job_id, ok, msg):
    with engine.begin() as c:
        c.execute(text("UPDATE form_job_cards SET excel_pending = :p, excel_error = :e WHERE id = :i"),
                  {"p": not ok, "e": None if ok else msg, "i": job_id})
    return ok, msg


def push_pending(engine):
    with engine.connect() as c:
        ids = [r[0] for r in c.execute(text("SELECT id FROM form_job_cards WHERE excel_pending ORDER BY id"))]
    cfg = graph_settings()
    if not ids or not cfg:
        return []                                 # nothing queued / no Excel connection here (local PC)
    cache = {}
    g = f"https://graph.microsoft.com/v1.0{_workbook_url(cfg)}"
    H = {"Authorization": f"Bearer {_token(cfg)}", "Content-Type": "application/json"}
    if len(ids) > 3:                              # many rows: one workbook session is faster and steadier
        try:
            sid = _req("POST", f"{g}/createSession", json.dumps({"persistChanges": True}).encode(), H)["id"]
            cache["session"] = {"workbook-session-id": sid}
        except Exception:
            pass
    try:
        return [(i, *push_to_excel(engine, i, cache)) for i in ids]
    finally:
        if "session" in cache:
            try:
                _req("POST", f"{g}/closeSession", b"{}", dict(H, **cache["session"]))
            except Exception:
                pass


def sync_all(engine):
    """Google Form → DB, Price Master → DB, recalculate costs, then write queued changes to Excel."""
    added, n = sync_from_google(engine)
    try:
        sync_prices(engine)
    except Exception as e:                        # keep the last good prices
        print(f"Price Master sync failed: {e}")
    recompute_costs(engine)
    link_tickets(engine)
    return added, n, push_pending(engine)


# ═══════════════════════════ dealer tickets ═══════════════════════════
IST_NOW = "(NOW() AT TIME ZONE 'Asia/Kolkata')"      # form timestamps are IST — tickets use the same clock
CLOSED_SQL = "UPPER(TRIM(COALESCE({}, ''))) IN ('CLOSED', 'RESOLVED', 'COMPLETED')"


def link_tickets(engine):
    """Tickets ↔ technicians' job cards:
    1. the job card's 'Ticket No' answer (if the form has that question) links it to that ticket;
    2. otherwise a new job card for the same client + chassis links to that vehicle's oldest open ticket;
    3. a ticket whose job card the TSM has closed becomes RESOLVED.
    Returns (linked, resolved)."""
    free = "NOT EXISTS (SELECT 1 FROM dealer_tickets x WHERE x.job_card_id = f.id)"
    open_t = "t.job_card_id IS NULL AND t.status <> 'RESOLVED'"
    set_link = f"""job_card_id = m.fid, link_method = m.how, updated_at = {IST_NOW},
                   status = CASE WHEN t.status = 'OPEN' THEN 'IN PROGRESS' ELSE t.status END"""
    ticket_answer = "COALESCE(f.form->>'Ticket No', f.form->>'Ticket No.', f.form->>'Ticket Number')"
    with engine.begin() as c:
        linked = c.execute(text(f"""
            WITH m AS (SELECT DISTINCT ON (f.id) t.id AS tid, f.id AS fid, 'form' AS how
                       FROM dealer_tickets t
                       JOIN form_job_cards f ON f.job_type = 'B2B'
                        AND CASE WHEN {ticket_answer} ~* '^\\s*(TK)?[-\\s#]*[0-9]{{1,6}}\\s*$'   -- cast only real ticket numbers
                                 THEN REGEXP_REPLACE({ticket_answer}, '[^0-9]', '', 'g')::bigint END
                            = SUBSTRING(t.ticket_no FROM 4)::bigint
                       WHERE {open_t} AND {free}
                       ORDER BY f.id, t.id)
            UPDATE dealer_tickets t SET {set_link} FROM m WHERE t.id = m.tid""")).rowcount
        linked += c.execute(text(f"""
            WITH c1 AS (SELECT DISTINCT ON (t.id) t.id AS tid, f.id AS fid
                        FROM dealer_tickets t
                        JOIN form_job_cards f ON f.job_type = 'B2B'
                         AND LOWER(f.client_name) = LOWER(t.client_name)
                         AND UPPER(REPLACE(f.chassis_number, ' ', '')) = UPPER(REPLACE(t.chassis_number, ' ', ''))
                         AND f.submitted_at >= t.raised_at - INTERVAL '1 day'
                        WHERE {open_t} AND COALESCE(t.chassis_number, '') <> '' AND {free}
                        ORDER BY t.id, f.submitted_at),
                 m AS (SELECT DISTINCT ON (fid) tid, fid, 'chassis' AS how FROM c1 ORDER BY fid, tid)
            UPDATE dealer_tickets t SET {set_link} FROM m WHERE t.id = m.tid""")).rowcount
        resolved = c.execute(text(f"""
            UPDATE dealer_tickets t
            SET status = 'RESOLVED', resolved_at = {IST_NOW}, resolved_by = f.updated_by, updated_at = {IST_NOW},
                customer_remark = COALESCE(NULLIF(TRIM(t.customer_remark), ''), 'Resolved (job card ' || f.job_card_no || ')')
            FROM form_job_cards f
            WHERE t.job_card_id = f.id AND t.status <> 'RESOLVED' AND {CLOSED_SQL.format('f.tsm_job_status')}""")).rowcount
    return linked, resolved


# ── ticket photos live in OneDrive (the free database stays small) ──
UPLOAD_DIR = "FleetCo Portal Uploads/Dealer Tickets"


def _drive_item(cfg, path):
    p = "/".join(urllib.parse.quote(x) for x in path.split("/"))
    return f"https://graph.microsoft.com/v1.0/users/{urllib.parse.quote(cfg['user'])}/drive/root:/{p}:/content"


def upload_photo(name, data, content_type="image/jpeg"):
    """Save a ticket photo (< 4 MB) in OneDrive; returns its path."""
    cfg = graph_settings()
    if not cfg:
        raise RuntimeError("OneDrive connection not set up (graph secrets missing)")
    path = f"{UPLOAD_DIR}/{name}"
    _req("PUT", _drive_item(cfg, path), data, {"Authorization": f"Bearer {_token(cfg)}", "Content-Type": content_type})
    return path


def download_photo(path):
    cfg = graph_settings()
    if not cfg or not path:
        return None
    req = urllib.request.Request(_drive_item(cfg, path), headers={"Authorization": f"Bearer {_token(cfg)}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


# ═══════════════════════════ automatic costs ═══════════════════════════
# Same rules as the Excel / Daily Report (checked against all existing job cards):
#   SPARES COST  = parts in the paid / consumed / non-warranty columns at CUSTOMER PRICE (B2B, invoiced)
#                  or at BM LANDING COST (Rental — not invoiced, shows the value used on the fleet; user 31-Oct-2026)
#   LABOR COST   = labour charge of each of those parts
#   Rental "Recovery Vehicle": SPARES COST = damaged + missing components at BM LANDING COST (the loss)
#   WARRANTY SPARES / LABOR = "Warranty Parts Replaced" at CUSTOMER PRICE + labour per part
PRICE_SHEET = "Price Master"
LOCAL_EXCEL = os.path.join(os.path.expanduser("~"), "OneDrive - FleetCo", *EXCEL_FILE.split("/"))
REVENUE_PARTS = {
    "B2B":    ["Paid Replaced Spares", "Consumed Spares on General Service", "Non - Warranty Parts Replaced"],
    "Rental": ["Paid - Replaced Spares", "Consumed Spares Lists", "Non - Warranty Parts Replaced"],
}
RECOVERY_PARTS = ["List Out The Damaged Components", "List Out The Missing Components"]
WARRANTY_PARTS = ["Warranty Parts Replaced"]
NOT_A_PART = {"NIL", "NIL.", "NA", "N/A", "NONE", "-", "0"}
COST_COLS = ["spares_cost", "labor_cost", "warranty_spares_cost", "warranty_labor_cost"]


def pkey(s):
    return re.sub(r"\s+", " ", str(s or "")).strip().upper()


def split_parts(*cells):
    """Items are comma separated; '/' only separates next to a space (keeps 'W/H ASSEMBLY' whole)."""
    return [pkey(x) for c in cells for x in re.split(r",|\s/\s*|\s*/\s", str(c or ""))
            if pkey(x) and pkey(x) not in NOT_A_PART]


def _price_rows_from_values(values):
    """Price Master sheet cells → [(kind, key, name, customer, landing, labour)] (first row of a name wins)."""
    out, seen = [], set()
    for r in values[2:]:                       # row 1 'SPARES COSTS / LABOUR COSTS', row 2 headers
        r = list(r) + [None] * 6
        if r[0] not in (None, "") and ("spare", pkey(r[0])) not in seen:
            seen.add(("spare", pkey(r[0])))
            out.append(("spare", pkey(r[0]), str(r[0]).strip(), to_money(r[1]), to_money(r[2]), None))
        if r[4] not in (None, "") and ("labour", pkey(r[4])) not in seen:
            seen.add(("labour", pkey(r[4])))
            out.append(("labour", pkey(r[4]), str(r[4]).strip(), None, None, to_money(r[5])))
    return out


def sync_prices(engine):
    """Copy the Price Master sheet into price_master (OneDrive via Graph, or the local OneDrive file)."""
    cfg = graph_settings()
    if cfg:
        H = {"Authorization": f"Bearer {_token(cfg)}"}
        ws = f"{_workbook_url(cfg)}/worksheets('{urllib.parse.quote(PRICE_SHEET)}')"
        values = _req("GET", f"https://graph.microsoft.com/v1.0{ws}/usedRange(valuesOnly=true)?$select=values",
                      headers=H)["values"]
    elif os.path.exists(LOCAL_EXCEL):
        wb = openpyxl.load_workbook(LOCAL_EXCEL, read_only=True, data_only=True)
        values = list(wb[PRICE_SHEET].iter_rows(values_only=True, max_row=3000))
    else:
        return 0
    rows = _price_rows_from_values(values)
    if not rows:
        return 0
    with engine.begin() as c:
        have = {(r[0], r[1], r[2], _f(r[3]), _f(r[4]), _f(r[5])) for r in c.execute(text(
            "SELECT kind, name_key, name, customer_price, landing_cost, labour_charge FROM price_master"))}
        if have == {(k, key, n, _f(cp), _f(lc), _f(lb)) for k, key, n, cp, lc, lb in rows}:
            return 0                              # prices unchanged — nothing to write
        c.execute(text("DELETE FROM price_master"))
        _bulk(c, "INSERT INTO price_master (kind, name_key, name, customer_price, landing_cost, labour_charge) VALUES %s",
              rows)
    return len(rows)


def _f(v):
    return None if v is None else round(float(v), 2)


def _bulk(conn, sql, rows, template=None):
    """Many rows in one round trip (the DB is far from the app server — one INSERT per row is slow)."""
    from psycopg2.extras import execute_values
    with conn.connection.driver_connection.cursor() as cur:
        execute_values(cur, sql, rows, template=template, page_size=1000)


def load_prices(engine):
    with engine.connect() as c:
        rows = c.execute(text("SELECT kind, name_key, customer_price, landing_cost, labour_charge FROM price_master")).all()
    spares = {r[1]: (float(r[2] or 0), float(r[3] or 0)) for r in rows if r[0] == "spare"}
    labour = {r[1]: float(r[4] or 0) for r in rows if r[0] == "labour"}
    return spares, labour


def compute_costs(job_type, service_type, form, prices):
    """Form answers → the 4 cost columns + parts the Price Master doesn't know."""
    spares, labour = prices
    f = {low(k): v for k, v in (form or {}).items()}
    cell = lambda names: [f.get(low(n)) for n in names]
    unpriced = []

    def total(parts, price_index):
        s = l = 0.0
        for p in parts:
            if p not in spares and p not in labour:
                unpriced.append(p)
            s += spares.get(p, (0, 0))[price_index]
            l += labour.get(p, 0)
        return round(s, 2), round(l, 2)

    out = dict.fromkeys(COST_COLS)
    if job_type == "Rental" and low(service_type) == "recovery vehicle":
        out["spares_cost"], _ = total(split_parts(*cell(RECOVERY_PARTS)), 1)        # loss at landing cost
    else:
        parts = split_parts(*cell(REVENUE_PARTS[job_type]))
        if parts:
            # rental is not invoiced: spares are valued at what they cost FleetCo (landing cost)
            out["spares_cost"], out["labor_cost"] = total(parts, 1 if job_type == "Rental" else 0)
    wparts = split_parts(*cell(WARRANTY_PARTS))
    if wparts:
        out["warranty_spares_cost"], out["warranty_labor_cost"] = total(wparts, 0)
    out["unpriced_parts"] = ", ".join(sorted(set(unpriced))) or None
    return out


def cost_lines(job_type, service_type, form, prices):
    """Part-by-part breakdown for the job card screen: [(group, part, spare ₹, labour ₹, priced?)]."""
    spares, labour = prices
    f = {low(k): v for k, v in (form or {}).items()}
    cell = lambda names: [f.get(low(n)) for n in names]
    if job_type == "Rental" and low(service_type) == "recovery vehicle":
        groups = [("Recovery loss (landing cost)", RECOVERY_PARTS, 1, False)]
    elif job_type == "Rental":
        groups = [("Value used (landing cost)", REVENUE_PARTS[job_type], 1, True)]
    else:
        groups = [("Revenue", REVENUE_PARTS[job_type], 0, True)]
    groups.append(("Warranty", WARRANTY_PARTS, 0, True))
    out = []
    for name, cols, idx, with_labour in groups:
        for p in split_parts(*cell(cols)):
            out.append((name, p, spares.get(p, (0, 0))[idx], labour.get(p, 0) if with_labour else 0,
                        p in spares or p in labour))
    return out


def recompute_costs(engine, prices=None):
    """Recalculate every job card's costs; changed ones are saved and queued for Excel. Returns their ids."""
    prices = prices or load_prices(engine)
    if not prices[0] and not prices[1]:
        return []
    changed = []
    with engine.begin() as c:
        for r in c.execute(text(f"""SELECT id, job_type, service_type, form, unpriced_parts, {", ".join(COST_COLS)}
                                    FROM form_job_cards""")).mappings():
            new = compute_costs(r["job_type"], r["service_type"], r["form"], prices)
            # Excel kept unrounded values (e.g. 1437.745) — a paisa of rounding is not a change
            money_changed = any((r[k] is None) != (new[k] is None) or
                                (r[k] is not None and abs(float(r[k]) - new[k]) >= 0.05) for k in COST_COLS)
            if money_changed or r["unpriced_parts"] != new["unpriced_parts"]:
                if not money_changed:
                    new.update({k: r[k] for k in COST_COLS})
                changed.append(dict(new, id=r["id"], pend=money_changed))
        if changed:
            _bulk(c, f"""UPDATE form_job_cards f SET {", ".join(f"{k} = v.{k}" for k in COST_COLS)},
                             unpriced_parts = v.unpriced_parts, excel_pending = f.excel_pending OR v.pend
                         FROM (VALUES %s) AS v(id, {", ".join(COST_COLS)}, unpriced_parts, pend)
                         WHERE f.id = v.id""",
                  [(ch["id"], *(ch[k] for k in COST_COLS), ch["unpriced_parts"], ch["pend"]) for ch in changed],
                  template="(%s::int, %s::numeric, %s::numeric, %s::numeric, %s::numeric, %s::text, %s::boolean)")
    return [ch["id"] for ch in changed if ch["pend"]]


# ═══════════════════════════ one-time import ═══════════════════════════
def import_team_from_excel(engine, path):
    """Copy the team's columns from the Excel file into the DB (only for job cards whose
    team columns are still empty in the DB — never overwrites portal edits)."""
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    sheets = {"B2B": "B2B - Job Card", "Rental": "Rental - Job Card"}
    n = 0
    with engine.begin() as c:
        for jt, sname in sheets.items():
            rows = [r for r in wb[sname].iter_rows(values_only=True, max_row=5000) if any(v not in (None, "") for v in r)]
            hi = next(i for i, r in enumerate(rows) if any(low(v) == low(SOURCES[jt]["no"]) for v in r))
            head = [low(h) for h in rows[hi]]
            ki = head.index(low(SOURCES[jt]["no"]))
            for r in rows[hi + 1:]:
                no = clean(r[ki])
                if not no:
                    continue
                vals = {}
                for col, eh in TEAM_COLS.items():
                    if low(eh) in head:
                        v = r[head.index(low(eh))]
                        vals[col] = to_date(v) if col in DATE_COLS else to_money(v) if col in MONEY_COLS else clean(v)
                    else:
                        vals[col] = None
                vals = {k: (None if v == "-" else v) for k, v in vals.items()}
                res = c.execute(text(f"""
                    UPDATE form_job_cards SET {", ".join(f"{k} = :{k}" for k in TEAM_COLS)}
                    WHERE job_type = :jt AND job_card_no = :no
                      AND updated_by IS NULL AND {" AND ".join(f"{k} IS NULL" for k in TEAM_COLS)}
                """), {**vals, "jt": jt, "no": no})
                n += res.rowcount
    return n


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from db_config import get_engine
    eng = get_engine()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "sync"
    if cmd == "sync":
        added, n, pushed = sync_all(eng)
        print(f"Google → DB: {n} job cards read, {added} new")
        for i, ok, msg in pushed:
            print(f"  Excel retry job {i}: {'OK' if ok else 'still pending'} — {msg}")
    elif cmd == "import-team":
        print(f"team columns imported for {import_team_from_excel(eng, sys.argv[2])} job cards")
    else:
        sys.exit(__doc__)
