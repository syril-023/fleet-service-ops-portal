"""
Inventory — 3 hubs (Central main hub, South Hub, North Hub).

  Hub workbooks (OneDrive "Automation Data/Inventory/Inventory_<Hub>.xlsx")
      ──import_hub()──▶ inv_parts + inv_moves        (one-time / before go-live; re-runnable)
  portal Stock IN / OUT / Transfer ──push_moves()──▶ new row in the hub's INFLOW / OUTFLOW sheet
  portal new part ──push_parts()──▶ new row in every hub's PARTS LIST + LIVE STOCK

The workbooks are plain sheets (no Excel tables). A new row copies the formulas of the row above
(description, unit cost, total, aging, # …) with the row number moved down, and gets the portal's
values in the data columns. Nothing in existing rows is ever changed.

  py inventory.py import CEN|STH|NTH|all     read the local OneDrive copies into the DB
  py inventory.py link                       link stock issues to job cards (same chassis)
"""
import datetime as dt, json, os, re, sys, threading, time, urllib.parse
import openpyxl
from sqlalchemy import text

import jobcards as jc   # Graph helpers + date / money parsing shared with job cards

IST_NOW = "(NOW() AT TIME ZONE 'Asia/Kolkata')"
ONEDRIVE = os.path.join(os.path.expanduser("~"), "OneDrive - FleetCo")

SHEET_IN, SHEET_OUT = "📥 INFLOW", "📤 OUTFLOW"
SHEET_PARTS, SHEET_LIVE = "🔧 PARTS LIST", "📦 LIVE STOCK"

# Excel header (lower case, spaces collapsed) → inv_moves column
IN_COLS = {
    "date received": "move_date", "item code": "part_code", "qty received": "qty", "source": "source",
    "ref no. (po/bill/note)": "ref_no", "unit cost (₹)": "unit_cost", "in-charge (responsible)": "in_charge",
}
OUT_COLS = {
    "date issued": "move_date", "item code": "part_code", "qty issued": "qty", "purpose": "purpose",
    "issued by (in-charge)": "in_charge", "issued for (b2b/rental)": "issued_for",
    "issued for (b2b partner)": "issued_for", "issued to (technician)": "technician",
    "vehicle / chassis no.": "chassis_number", "unit cost (₹)": "unit_cost", "revenue amt": "revenue_amt",
    "remarks": "remarks",
}
# columns the Excel works out itself — a new row keeps the formula of the row above
COMPUTED = {"#", "s.no", "item description", "unit cost (₹)", "total value (₹)", "aging (days)",
            "total received", "total issued", "live stock", "stock value (₹)", "total stock value (₹)",
            "oldest aging (days)", "status", "customer price", "customer price with gst", "revenue"}

# dropdown choices (from the workbooks' own lists + what the team already typed)
SOURCES = ["OEM", "Local Spare Shop", "External Vendor", "Rental Service Removed Parts",
           "Scrap Recovered (Good Condition)", "Branch Return", "Other"]
PURPOSES = ["Vehicle Repair", "Complaint Rectification", "Preventive Maintenance", "Damaged/Scrap",
            "Stock Inventory", "Other"]
TRANSFER_PURPOSE = {"CEN": "Branch Dispatch"}          # the other hubs' lists say "Co-Branch Dispatch"
ISSUED_FOR = ["Rental Service", "QUICKBITE", "UrbanRide", "Partner C", "Partner D", "OEM Production", "Others"]


def hkey(s):
    return re.sub(r"\s+", " ", str(s or "")).strip().lower()


def code_key(s):
    return re.sub(r"\s+", "", str(s or "")).strip().upper()


def chassis_key(s):
    k = code_key(s)
    return None if k in ("", "-", "NA", "N/A", "NIL", "0") else k


def transfer_purpose(hub):
    return TRANSFER_PURPOSE.get(hub, "Co-Branch Dispatch")


# ═══════════════════════════ Excel → DB (import) ═══════════════════════════
def _rows(ws):
    return [list(r) for r in ws.iter_rows(values_only=True)]


def _header_index(rows, must):
    for i, r in enumerate(rows[:15]):
        if any(hkey(v) == must for v in r):
            return i
    raise RuntimeError(f"header '{must}' not found")


def read_parts(wb):
    return parts_from_rows(_rows(wb[SHEET_PARTS]))


def parts_from_rows(rows):
    """PARTS LIST cells → {code: part}. First row of a code wins."""
    rows = [list(r) for r in rows]
    hi = _header_index(rows, "part #")
    head = [hkey(h) for h in rows[hi]]
    col = lambda name: head.index(name) if name in head else None
    ci = {k: col(k) for k in ("part #", "description", "hsn", "landing cost", "margin",
                              "customer price", "gst")}
    out = {}
    for r in rows[hi + 1:]:
        code = code_key(r[ci["part #"]])
        if not code or code in out:
            continue
        g = lambda k: r[ci[k]] if ci[k] is not None and ci[k] < len(r) and r[ci[k]] != "" else None
        hsn = g("hsn")
        out[code] = {
            "part_code": code, "description": str(g("description") or code).strip()[:200],
            "hsn": str(int(hsn) if isinstance(hsn, float) and hsn.is_integer() else hsn).strip()[:20] if hsn not in (None, "") else None,
            "landing_cost": jc.to_money(g("landing cost")), "margin": jc.to_money(g("margin")),
            "customer_price": jc.to_money(g("customer price")), "gst": jc.to_money(g("gst")),
        }
    return out


def read_moves(wb, sheet, direction):
    """Every filled row of the INFLOW / OUTFLOW sheet → dicts (with the Excel row number)."""
    rows = _rows(wb[sheet])
    hi = _header_index(rows, "item code")
    head = [hkey(h) for h in rows[hi]]
    cols = IN_COLS if direction == "IN" else OUT_COLS
    idx = {cols[h]: i for i, h in enumerate(head) if h in cols}
    di = head.index("item description") if "item description" in head else None
    out, skipped = [], []
    for n, r in enumerate(rows[hi + 1:], start=hi + 2):          # Excel rows are 1-based
        g = lambda k: r[idx[k]] if k in idx and idx[k] < len(r) else None
        code = code_key(g("part_code"))
        if not code:
            continue
        try:
            qty = int(float(g("qty")))
        except (TypeError, ValueError):
            qty = 0
        if qty <= 0:
            skipped.append((n, code, "no quantity"))
            continue
        m = {"direction": direction, "excel_row": n, "part_code": code, "qty": qty,
             "move_date": jc.to_date(g("move_date")), "unit_cost": jc.to_money(g("unit_cost")),
             "description": str(r[di]).strip() if di is not None and di < len(r) and r[di] else None}
        for k in ("source", "ref_no", "purpose", "in_charge", "issued_for", "technician", "remarks"):
            v = jc.clean(g(k))
            m[k] = None if v in (None, "-") else v[:80 if k != "remarks" else 1000]
        m["chassis_number"] = chassis_key(g("chassis_number"))
        m["revenue_amt"] = jc.to_money(g("revenue_amt"))
        out.append(m)
    return out, skipped


def hub_file(engine, hub, local=True):
    with engine.connect() as c:
        f = c.execute(text("SELECT excel_file FROM stock_hubs WHERE hub = :h"), {"h": hub}).scalar()
    return os.path.join(ONEDRIVE, *f.split("/")) if local else f


def import_hub(engine, hub, path=None):
    """Replace the hub's Excel-imported movements with what the workbook holds now. Rows the portal
    wrote into the Excel itself are not imported twice. Parts are added / refreshed from PARTS LIST."""
    path = path or hub_file(engine, hub)
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    parts = read_parts(wb)
    moves, skipped = [], []
    for sheet, d in ((SHEET_IN, "IN"), (SHEET_OUT, "OUT")):
        m, s = read_moves(wb, sheet, d)
        moves += m
        skipped += [(sheet, *x) for x in s]
    with engine.begin() as c:
        _upsert_parts(c, parts)
        # codes used in the log but missing from the PARTS LIST ("Code Not Found" in the Excel)
        known = {r[0] for r in c.execute(text("SELECT part_code FROM inv_parts"))}
        extra = {}
        for m in moves:
            if m["part_code"] not in known and m["part_code"] not in extra:
                d = m["description"] if m["description"] and "not found" not in m["description"].lower() else m["part_code"]
                extra[m["part_code"]] = (m["part_code"], d[:200], m["unit_cost"])
        if extra:
            jc._bulk(c, "INSERT INTO inv_parts (part_code, description, landing_cost) VALUES %s ON CONFLICT DO NOTHING",
                     list(extra.values()))
        portal_rows = {(r[0], r[1]) for r in c.execute(text(
            "SELECT direction, excel_row FROM inv_moves WHERE hub = :h AND origin = 'portal' AND excel_row IS NOT NULL"),
            {"h": hub})}
        c.execute(text("DELETE FROM inv_moves WHERE hub = :h AND origin = 'excel'"), {"h": hub})
        fresh = [m for m in moves if (m["direction"], m["excel_row"]) not in portal_rows]
        cols = ["direction", "move_date", "part_code", "qty", "unit_cost", "source", "ref_no", "purpose",
                "issued_for", "technician", "chassis_number", "revenue_amt", "remarks", "in_charge", "excel_row"]
        if fresh:
            jc._bulk(c, f"""INSERT INTO inv_moves (hub, origin, {", ".join(cols)}) VALUES %s""",
                     [(hub, "excel", *(m[k] for k in cols)) for m in fresh])
    link_jobs(engine)
    return {"parts": len(parts), "new_codes": len(extra), "in": sum(m["direction"] == "IN" for m in fresh),
            "out": sum(m["direction"] == "OUT" for m in fresh), "skipped": skipped,
            "no_date": sum(1 for m in fresh if not m["move_date"])}


def _upsert_parts(c, parts):
    """Parts from a PARTS LIST: new ones added, names / prices refreshed. Reorder level and the
    active flag are the portal's own. Returns how many rows were added or changed."""
    if not parts:
        return 0
    before = {r[0]: tuple(r[1:]) for r in c.execute(text(
        "SELECT part_code, description, hsn, landing_cost, margin, customer_price, gst FROM inv_parts"))}
    rows = [(p["part_code"], p["description"], p["hsn"], p["landing_cost"], p["margin"], p["customer_price"], p["gst"])
            for p in parts.values()]
    norm = lambda t: tuple(None if v is None else round(float(v), 4) if isinstance(v, (int, float)) or
                           hasattr(v, "as_tuple") else str(v) for v in t)
    changed = [r for r in rows if r[0] not in before or norm(before[r[0]]) != norm(r[1:])]
    if changed:
        jc._bulk(c, """INSERT INTO inv_parts (part_code, description, hsn, landing_cost, margin, customer_price, gst)
                       VALUES %s
                       ON CONFLICT (part_code) DO UPDATE SET description = EXCLUDED.description,
                           hsn = EXCLUDED.hsn, landing_cost = EXCLUDED.landing_cost, margin = EXCLUDED.margin,
                           customer_price = EXCLUDED.customer_price, gst = EXCLUDED.gst, in_excel = TRUE,
                           updated_at = """ + IST_NOW, changed)
    return len(changed)


def refresh_prices(engine):
    """Names and prices from the Central Hub workbook's PARTS LIST (the price list all hubs share).
    On the live portal through Graph; on the office PC from the local OneDrive copy."""
    cfg = jc.graph_settings()
    if cfg:
        path = hub_file(engine, "CEN", local=False)
        p = "/".join(urllib.parse.quote(x) for x in path.split("/"))
        url = (f"https://graph.microsoft.com/v1.0/users/{urllib.parse.quote(cfg['user'])}/drive/root:/{p}:/workbook"
               f"/worksheets('{urllib.parse.quote(SHEET_PARTS)}')/usedRange(valuesOnly=true)?$select=values")
        rows = jc._req("GET", url, headers={"Authorization": f"Bearer {jc._token(cfg)}"})["values"]
    else:
        rows = _rows(openpyxl.load_workbook(hub_file(engine, "CEN"), read_only=True, data_only=True)[SHEET_PARTS])
    parts = parts_from_rows(rows)
    with engine.begin() as c:
        return _upsert_parts(c, parts), len(parts)


# ═══════════════════════════ stock issues ↔ job cards ═══════════════════════════
def link_jobs(engine):
    """A part issued to a chassis belongs to that vehicle's job card opened 7 days before … 3 days after
    the issue (nearest one). Only unlinked issues are touched. Returns how many were linked."""
    with engine.begin() as c:
        return c.execute(text("""
            WITH m AS (
                SELECT DISTINCT ON (s.id) s.id AS sid, f.id AS fid
                FROM inv_moves s
                JOIN form_job_cards f
                  ON UPPER(REPLACE(f.chassis_number, ' ', '')) = s.chassis_number
                 AND f.job_open_date BETWEEN s.move_date - 7 AND s.move_date + 3
                WHERE s.direction = 'OUT' AND s.job_card_id IS NULL AND s.chassis_number IS NOT NULL
                ORDER BY s.id, ABS(f.job_open_date - s.move_date), f.job_open_date)
            UPDATE inv_moves s SET job_card_id = m.fid FROM m WHERE s.id = m.sid""")).rowcount


# ═══════════════════════════ portal → Excel ═══════════════════════════
_locks = {}
_locks_guard = threading.Lock()


def _hub_lock(hub):
    with _locks_guard:
        return _locks.setdefault(hub, threading.Lock())


def shift_formula(f, src_row, dst_row):
    """'=VLOOKUP(C78,…)' on row 78 → the same formula for row 79. Absolute rows ($C$5) stay."""
    if not isinstance(f, str) or not f.startswith("="):
        return f
    return re.sub(r"(?<![A-Za-z0-9_$])(\$?[A-Z]{1,3})" + str(src_row) + r"(?![0-9])",
                  lambda m: f"{m.group(1)}{dst_row}", f)


def excel_serial(d):
    return (dt.datetime.combine(d, dt.time()) - jc.EPOCH).days


def build_row(head, template, src_row, dst_row, values):
    """The cells of a new sheet row: our values in the data columns, the row above's formulas
    (moved down) in the Excel's own columns, '#' / S.No continued."""
    out = []
    for i, h in enumerate(head):
        t = template[i] if i < len(template) else ""
        is_formula = isinstance(t, str) and t.startswith("=")
        if h in values and not (h in COMPUTED and is_formula):
            v = values[h]
            if isinstance(v, dt.date):
                v = excel_serial(v)
            elif isinstance(v, str) and v[:1] in "=+-@":
                v = "'" + v                                     # text never becomes a formula
            out.append("" if v is None else v)
        elif is_formula:
            out.append(shift_formula(t, src_row, dst_row))
        elif h in ("#", "s.no") and isinstance(t, (int, float)):
            out.append(int(t) + 1)
        else:
            out.append("")
    return out


class Sheet:
    """One worksheet of a hub workbook through Microsoft Graph."""

    def __init__(self, cfg, path, name, header_must, key_header):
        self.H = {"Authorization": f"Bearer {jc._token(cfg)}"}
        p = "/".join(urllib.parse.quote(x) for x in path.split("/"))
        self.base = (f"https://graph.microsoft.com/v1.0/users/{urllib.parse.quote(cfg['user'])}"
                     f"/drive/root:/{p}:/workbook/worksheets('{urllib.parse.quote(name)}')")
        top = jc._req("GET", f"{self.base}/range(address='A1:AD15')?$select=values", headers=self.H)["values"]
        self.hrow = next(i for i, r in enumerate(top) if any(hkey(v) == header_must for v in r)) + 1
        self.head = [hkey(v) for v in top[self.hrow - 1]]
        while self.head and not self.head[-1]:
            self.head.pop()
        self.kcol = jc._col_letter(self.head.index(key_header))

    def last_row(self):
        vals = jc._req("GET", f"{self.base}/range(address='{self.kcol}1:{self.kcol}6000')?$select=values",
                       headers=self.H)["values"]
        filled = [i + 1 for i, v in enumerate(vals) if i + 1 > self.hrow and str(v[0]).strip()]
        return filled[-1] if filled else self.hrow

    def append(self, values):
        """Write one new row after the last filled one; returns its row number."""
        last = self.last_row()
        end = jc._col_letter(len(self.head) - 1)
        if last > self.hrow:
            t = jc._req("GET", f"{self.base}/range(address='A{last}:{end}{last}')?$select=formulas,numberFormat",
                        headers=self.H)
            template, fmts = t["formulas"][0], t["numberFormat"][0]
        else:                                                  # empty sheet: no row to copy
            template, fmts = [""] * len(self.head), ["General"] * len(self.head)
        row = last + 1
        cells = build_row(self.head, template, last, row, values)
        fmts = [("dd-mm-yyyy" if isinstance(values.get(h), dt.date) else fmts[i]) for i, h in enumerate(self.head)]
        body = json.dumps({"formulas": [cells], "numberFormat": [fmts]}).encode()
        hdrs = dict(self.H, **{"Content-Type": "application/json"})
        for attempt in range(3):                          # Excel online sometimes answers "busy"
            try:
                jc._req("PATCH", f"{self.base}/range(address='A{row}:{end}{row}')", body, hdrs)
                return row
            except RuntimeError as e:
                if attempt == 2 or not re.search(r"HTTP (409|423|429|5\d\d)", str(e)):
                    raise
                time.sleep(2 * (attempt + 1))


def move_values(m, hub):
    """inv_moves row → {excel header: value} for the hub's INFLOW / OUTFLOW sheet."""
    common = {"item code": m["part_code"], "unit cost (₹)": float(m["unit_cost"] or 0),
              "total value (₹)": float(m["unit_cost"] or 0) * m["qty"]}
    if m["direction"] == "IN":
        return {**common, "date received": m["move_date"], "qty received": m["qty"], "source": m["source"],
                "ref no. (po/bill/note)": m["ref_no"], "in-charge (responsible)": m["in_charge"]}
    return {**common, "date issued": m["move_date"], "qty issued": m["qty"], "purpose": m["purpose"],
            "issued by (in-charge)": m["in_charge"], "issued for (b2b/rental)": m["issued_for"],
            "issued for (b2b partner)": m["issued_for"], "issued to (technician)": m["technician"],
            "vehicle / chassis no.": m["chassis_number"] or "-",
            "revenue amt": float(m["revenue_amt"]) if m["revenue_amt"] is not None else None,
            "remarks": m["remarks"]}


def push_moves(engine, ids=None):
    """Append portal stock entries to their hub's Excel. ids=None → everything still pending.
    Returns [(id, ok, message)]. Failures stay pending and are retried by the next push."""
    with engine.connect() as c:
        q = "SELECT m.*, h.excel_file FROM inv_moves m JOIN stock_hubs h USING (hub) WHERE m.excel_pending"
        rows = [dict(r._mapping) for r in c.execute(text(q + (" AND m.id = ANY(:ids)" if ids else "") + " ORDER BY m.id"),
                                                    {"ids": list(ids or [])})]
    if not rows:
        return []
    cfg = jc.graph_settings()
    if not cfg:
        return [(r["id"], False, "Excel connection not set up here (only on the live portal)") for r in rows]
    results, sheets = [], {}
    for r in rows:
        key = (r["hub"], r["direction"])
        try:
            with _hub_lock(r["hub"]):
                if key not in sheets:
                    sheets[key] = Sheet(cfg, r["excel_file"], SHEET_IN if r["direction"] == "IN" else SHEET_OUT,
                                        "item code", "item code")
                row = sheets[key].append(move_values(r, r["hub"]))
            _mark(engine, r["id"], True, None, row)
            results.append((r["id"], True, f"Excel row {row}"))
        except Exception as e:
            _mark(engine, r["id"], False, str(e)[:300])
            results.append((r["id"], False, str(e)[:300]))
    return results


def _mark(engine, mid, ok, err, row=None):
    with engine.begin() as c:
        c.execute(text("""UPDATE inv_moves SET excel_pending = :p, excel_error = :e,
                          excel_row = COALESCE(:r, excel_row) WHERE id = :i"""),
                  {"p": not ok, "e": err, "r": row, "i": mid})


def push_parts(engine):
    """Parts added in the portal → every hub's PARTS LIST and LIVE STOCK sheets."""
    with engine.connect() as c:
        parts = [dict(r._mapping) for r in c.execute(text("SELECT * FROM inv_parts WHERE NOT in_excel ORDER BY part_code"))]
        hubs = [dict(r._mapping) for r in c.execute(text("SELECT hub, excel_file FROM stock_hubs WHERE is_active ORDER BY sort_order"))]
    cfg = jc.graph_settings()
    if not parts or not cfg:
        return []
    out = []
    for p in parts:
        try:
            for h in hubs:
                with _hub_lock(h["hub"]):
                    pl = Sheet(cfg, h["excel_file"], SHEET_PARTS, "part #", "part #")
                    price = float(p["customer_price"] or 0)
                    pl.append({"part #": p["part_code"], "description": p["description"], "hsn": p["hsn"],
                               "landing cost": float(p["landing_cost"] or 0),
                               "margin": float(p["margin"]) if p["margin"] is not None else None,
                               "customer price": price, "gst": float(p["gst"]) if p["gst"] is not None else None,
                               "customer price with gst": round(price * (1 + float(p["gst"] or 0)), 2),
                               "revenue": round(price - float(p["landing_cost"] or 0), 2)})
                    ls = Sheet(cfg, h["excel_file"], SHEET_LIVE, "item code", "item code")
                    ls.append({"item code": p["part_code"], "item description": p["description"]})
            with engine.begin() as c:
                c.execute(text("UPDATE inv_parts SET in_excel = TRUE WHERE part_code = :p"), {"p": p["part_code"]})
            out.append((p["part_code"], True, "added to every hub's Excel"))
        except Exception as e:
            out.append((p["part_code"], False, str(e)[:300]))
    return out


# ═══════════════════════════ stock levels ═══════════════════════════
STOCK_SQL = """
    SELECT p.part_code, p.description, p.landing_cost, p.customer_price, p.reorder_level, p.is_active,
           h.hub,
           COALESCE(SUM(m.qty) FILTER (WHERE m.direction = 'IN'), 0)  AS received,
           COALESCE(SUM(m.qty) FILTER (WHERE m.direction = 'OUT'), 0) AS issued,
           MIN(m.move_date) FILTER (WHERE m.direction = 'IN')         AS first_in
    FROM inv_parts p
    CROSS JOIN stock_hubs h
    LEFT JOIN inv_moves m ON m.part_code = p.part_code AND m.hub = h.hub
    WHERE h.is_active {hub_filter}
    GROUP BY p.part_code, h.hub
"""


def hub_stock(engine, hub, codes):
    """{part_code: live stock at the hub} for these parts (for checking an issue)."""
    with engine.connect() as c:
        return {r[0]: int(r[1]) for r in c.execute(text("""
            SELECT part_code, COALESCE(SUM(CASE direction WHEN 'IN' THEN qty ELSE -qty END), 0)
            FROM inv_moves WHERE hub = :h AND part_code = ANY(:c) GROUP BY part_code"""),
            {"h": hub, "c": list(codes)})}


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from db_config import get_engine
    eng = get_engine()
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "import":
        which = sys.argv[2].upper() if len(sys.argv) > 2 else "ALL"
        for hub in (["CEN", "STH", "NTH"] if which == "ALL" else [which]):
            r = import_hub(eng, hub)
            print(f"{hub}: {r['parts']} parts in list, {r['new_codes']} codes only in the log, "
                  f"{r['in']} IN rows, {r['out']} OUT rows, {r['no_date']} without a date, {len(r['skipped'])} skipped")
            for s in r["skipped"]:
                print("   skipped", s)
    elif cmd == "link":
        print("linked", link_jobs(eng))
    else:
        sys.exit(__doc__)
