"""
Fill an empty database with FAKE demo data so the portal can be tried without any company systems.

    py db/seed_demo.py            (after db/schema.sql has been loaded)

Everything here is invented: company "FleetCo", clients "QuickBite" (food delivery, 4 stores),
"UrbanRide" and "Parcel Express", 3 stock hubs, 60 rental scooters, ~180 job cards, tickets and stock.
Demo logins (password for all: demo1234):
    admin            Super Admin — sees everything
    head             Service Head
    store.central    Store in-charge of the Central hub (enters its stock)
    tsm.south        Territory manager (rental fleet + QuickBite)
    tsm.north        Territory manager (UrbanRide + Parcel Express)
    quickbite.hq     Dealer login — QuickBite head office (all stores)
    quickbite.qb101  Dealer login — one QuickBite store
"""
import datetime as dt, json, os, random, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import bcrypt
from sqlalchemy import text
from db_config import get_engine
import jobcards, inventory

rnd = random.Random(42)
TODAY = dt.date.today()
PASSWORD = bcrypt.hashpw(b"demo1234", bcrypt.gensalt()).decode()

USERS = [  # username, full name, role, zone, dealer client, dealer store, stock hub
    ("admin", "Demo Admin", "Super Admin", "Central", None, None, None),
    ("head", "Anita Rao", "Service Head", "Central", None, None, None),
    ("store.central", "Ravi Kumar", "Store Incharge", "Central", None, None, "CEN"),
    ("tsm.south", "Karthik N", "Territory Manager", "South", None, None, None),
    ("tsm.north", "Meena Iyer", "Territory Manager", "North", None, None, "NTH"),
    ("quickbite.hq", "QuickBite Head Office", "Dealer", "South", "QuickBite", None, None),
    ("quickbite.qb101", "QuickBite Lake Road", "Dealer", "South", "QuickBite", "QB101 - Lake Road", None),
]
STORES = ["QB101 - Lake Road", "QB102 - Market Street", "QB103 - Station Road", "QB104 - Hill View"]
TECHS = ["Arjun", "Bala", "Dinesh", "Farhan", "Gopi", "Hari"]
MODELS = ["FleetCo City Pro", "FleetCo Cargo X", "FleetCo Urban Lite"]

# part: (code, customer price, landing cost, labour)
PARTS = {
    "BRAKE PAD SET - FRONT": ("FC-BRK-001", 160, 123, 150), "BRAKE PAD SET - REAR": ("FC-BRK-002", 162, 125, 150),
    "BRAKE CALIPER ASSEMBLY - REAR": ("FC-BRK-010", 811, 624, 250), "DISC PLATE FRONT": ("FC-BRK-020", 640, 492, 200),
    "BRAKE SENSOR LH": ("FC-BRK-030", 100, 77, 100), "THROTTLE ASSEMBLY": ("FC-ELE-001", 980, 754, 200),
    "HEADLAMP ASSEMBLY": ("FC-ELE-010", 1450, 1115, 200), "TAIL LAMP ASSEMBLY": ("FC-ELE-011", 1236, 1030, 150),
    "DC DC CONVERTER": ("FC-ELE-020", 1027, 790, 300), "CONTROLLER 48V 30A": ("FC-ELE-030", 6890, 5300, 500),
    "WIRING HARNESS MAIN": ("FC-ELE-040", 4855, 3734, 800), "CHARGER 58.4V 20A": ("FC-BAT-010", 13926, 12660, 0),
    "BATTERY POWER CABLE ASSEMBLY": ("FC-BAT-020", 5134, 4278, 300), "TYRE 90/90-14": ("FC-WHL-001", 1454, 1118, 250),
    "TUBE 14 INCH": ("FC-WHL-002", 290, 223, 100), "FRONT WHEEL RIM 14 INCH": ("FC-WHL-010", 2502, 2085, 300),
    "BEARING 6201": ("FC-WHL-020", 55, 42, 100), "SIDE STAND ASSEMBLY": ("FC-BDY-001", 420, 323, 100),
    "CENTER STAND ASSEMBLY": ("FC-BDY-002", 518, 432, 150), "MIRROR SET": ("FC-BDY-010", 380, 292, 50),
    "FRONT MUDGUARD": ("FC-BDY-020", 434, 334, 150), "SEAT COVER": ("FC-BDY-030", 390, 300, 50),
}
GENERAL = "GENERAL SERVICE"


def chassis(i):
    return f"FCX24A{i:06d}"


def pick_parts(n):
    return rnd.sample(list(PARTS), n)


def main():
    eng = get_engine()
    with eng.begin() as c:
        if c.execute(text("SELECT COUNT(*) FROM form_job_cards")).scalar():
            sys.exit("This database already has job cards — seed only an empty demo database.")
        c.execute(text("""INSERT INTO stock_hubs (hub, name, excel_file, excel_name, sort_order) VALUES
            ('CEN', 'Central Hub (Main)', 'Automation Data/Inventory/Inventory_Central.xlsx', 'FleetCo Central', 1),
            ('STH', 'South Hub',          'Automation Data/Inventory/Inventory_South.xlsx',   'FleetCo South', 2),
            ('NTH', 'North Hub',          'Automation Data/Inventory/Inventory_North.xlsx',   'FleetCo North', 3)
            ON CONFLICT (hub) DO NOTHING"""))
        uid = {}
        for u, n, r, z, dc, ds, hub in USERS:
            uid[u] = c.execute(text("""INSERT INTO users (username, password_hash, full_name, role, zone,
                                           must_change_password, dealer_client, dealer_store, stock_hub)
                                       VALUES (:u, :p, :n, :r, :z, FALSE, :dc, :ds, :h) RETURNING user_id"""),
                               {"u": u, "p": PASSWORD, "n": n, "r": r, "z": z, "dc": dc, "ds": ds, "h": hub}).scalar()
        locs = {}
        for client, loc, zone, tsm, rental in [("FleetCo Rental Fleet", "Central Hub", "South", "tsm.south", True),
                                               ("QuickBite", None, "South", "tsm.south", False),
                                               ("UrbanRide", None, "North", "tsm.north", False),
                                               ("Parcel Express", None, "North", "tsm.north", False)]:
            locs[client] = c.execute(text("""INSERT INTO client_locations (client_name, location, zone, tsm_user_id, is_rental)
                                             VALUES (:c, :l, :z, :t, :r) RETURNING location_id"""),
                                     {"c": client, "l": loc, "z": zone, "t": uid[tsm], "r": rental}).scalar()
        # rental fleet + technicians (used by the Dashboard / Fleet pages)
        for i in range(1, 61):
            status = rnd.choices(["Active", "Available", "Under Service"], [70, 18, 12])[0]
            c.execute(text("""INSERT INTO rental_fleet (vehicle_number, vehicle_model, chassis_number, fleet_status,
                                  current_odometer_km, monthly_rental_amount, last_service_date, next_service_due_date)
                              VALUES (:v, :m, :ch, :s, :km, :amt, :ls, :nd)"""),
                      {"v": f"FC-EV-{i:03d}", "m": rnd.choice(MODELS), "ch": chassis(i), "s": status,
                       "km": rnd.randint(1500, 26000), "amt": rnd.choice([3200, 3500, 3800]),
                       "ls": TODAY - dt.timedelta(days=rnd.randint(5, 80)),
                       "nd": TODAY + dt.timedelta(days=rnd.randint(-5, 60))})
        for i, t in enumerate(TECHS, 1):
            c.execute(text("""INSERT INTO technicians (tech_code, tech_name, designation, is_active)
                              VALUES (:c, :n, 'Technician', TRUE)"""), {"c": f"T{i:02d}", "n": t})
        # price master (job card costs) — spares + labour per part, plus general service labour
        rows = [("spare", k, k, cp, lc, None) for k, (_, cp, lc, _) in PARTS.items()]
        rows += [("labour", k, k, None, None, lb) for k, (_, _, _, lb) in PARTS.items() if lb]
        rows.append(("labour", GENERAL, GENERAL, None, None, 350))
        jobcards._bulk(c, """INSERT INTO price_master (kind, name_key, name, customer_price, landing_cost, labour_charge)
                             VALUES %s""", rows)
        # QuickBite vehicles: chassis 101-124, 6 per store
        qb = [(chassis(100 + i), STORES[(i - 1) // 6]) for i in range(1, 25)]
        for ch, store in qb:
            c.execute(text("INSERT INTO dealer_vehicles (client_name, chassis_number, store) VALUES ('QuickBite', :c, :s)"),
                      {"c": ch, "s": store})
        ur = [chassis(200 + i) for i in range(1, 16)]
        pe = [chassis(300 + i) for i in range(1, 11)]

        # ── job cards from the "technicians' Google Form" ──
        jobs = []
        n_r = n_b = 0
        for d in range(120, -1, -1):
            day = TODAY - dt.timedelta(days=d)
            for _ in range(rnd.choice([0, 1, 1, 2])):
                n_r += 1
                jobs.append(rental_job(n_r, day))
            if rnd.random() < 0.65:
                n_b += 1
                client = rnd.choices(["QuickBite", "UrbanRide", "Parcel Express"], [60, 25, 15])[0]
                ch, store = rnd.choice(qb) if client == "QuickBite" else (rnd.choice(ur if client == "UrbanRide" else pe), None)
                jobs.append(b2b_job(n_b, day, client, store, ch))
        for j in jobs:
            loc = locs["FleetCo Rental Fleet" if j["job_type"] == "Rental" else j["client_name"]]
            c.execute(text(f"""INSERT INTO form_job_cards (job_type, job_card_no, submitted_at, job_open_date, client_name,
                                   client_location, client_location_id, service_type, chassis_number, odo_km, technician,
                                   field_observation, form_job_status, completion_date, form, tsm_job_status,
                                   complaint_category, tsm_observation, action_date, updated_by, updated_at)
                               VALUES (:job_type, :job_card_no, :ts, :day, :client_name, :client_location, :loc,
                                   :service_type, :chassis, :odo, :tech, :obs, :fstatus, :done, CAST(:form AS jsonb),
                                   :tstatus, :cat, :tobs, :action, :upd, :ts)"""),
                      {**j, "loc": loc, "form": json.dumps(j["form"]), "upd": uid["tsm.south"] if j["tstatus"] else None})

        # ── dealer complaint tickets (QuickBite) ──
        for i in range(14):
            ch, store = rnd.choice(qb)
            raised = dt.datetime.combine(TODAY - dt.timedelta(days=rnd.randint(0, 40)), dt.time(rnd.randint(9, 19), 15))
            c.execute(text("""INSERT INTO dealer_tickets (client_name, store, client_location_id, chassis_number,
                                  complaint_type, description, contact, raised_by, raised_at)
                              VALUES ('QuickBite', :s, :l, :c, :t, :d, :ph, :u, :r)"""),
                      {"s": store, "l": locs["QuickBite"], "c": ch,
                       "t": rnd.choice(["Brakes", "Battery / charging", "Electrical / lights / horn",
                                        "Vehicle not starting / breakdown", "Tyre / puncture"]),
                       "d": rnd.choice(["Brake noise while stopping", "Vehicle not charging fully", "Headlight not working",
                                        "Scooter stops suddenly in traffic", "Rear tyre puncture again"]),
                       "ph": f"98{rnd.randint(10000000, 99999999)}", "u": uid["quickbite.hq"], "r": raised})

        # ── inventory: 3 hubs ──
        jobcards._bulk(c, """INSERT INTO inv_parts (part_code, description, landing_cost, margin, customer_price, gst)
                             VALUES %s""",
                       [(code, name, lc, 0.2, cp, 0.18) for name, (code, cp, lc, _) in PARTS.items()])
        moves = []
        for hub, scale in (("CEN", 1.0), ("STH", 0.35), ("NTH", 0.5)):
            for name, (code, _, lc, _) in PARTS.items():
                got = 0
                for k in range(rnd.randint(1, 3)):
                    q = max(2, int(rnd.randint(5, 40) * scale))
                    got += q
                    moves.append({"hub": hub, "direction": "IN", "move_date": TODAY - dt.timedelta(days=rnd.randint(30, 110)),
                                  "part_code": code, "qty": q, "unit_cost": lc,
                                  "source": rnd.choice(["OEM", "OEM", "Local Spare Shop"]),
                                  "ref_no": f"INV-{rnd.randint(1000, 9999)}", "in_charge": "Ravi Kumar"})
                left = got
                for k in range(rnd.randint(0, 6)):
                    q = min(left, rnd.randint(1, 3))
                    if q <= 0:
                        break
                    left -= q
                    moves.append({"hub": hub, "direction": "OUT", "move_date": TODAY - dt.timedelta(days=rnd.randint(0, 29)),
                                  "part_code": code, "qty": q, "unit_cost": lc, "purpose": "Vehicle Repair",
                                  "issued_for": "Rental Service", "technician": rnd.choice(TECHS),
                                  "chassis_number": chassis(rnd.randint(1, 60)), "in_charge": "Ravi Kumar"})
        cols = ["hub", "direction", "move_date", "part_code", "qty", "unit_cost", "source", "ref_no", "purpose",
                "issued_for", "technician", "chassis_number", "in_charge"]
        jobcards._bulk(c, f"INSERT INTO inv_moves ({', '.join(cols)}, created_by) VALUES %s",
                       [tuple(m.get(k) for k in cols) + (uid["store.central"],) for m in moves])
    jobcards.recompute_costs(eng)
    jobcards.link_tickets(eng)
    inventory.link_jobs(eng)
    with eng.begin() as c:
        c.execute(text("UPDATE form_job_cards SET excel_pending = FALSE"))     # demo: no Excel to write to
        # a few open complaints already being worked on
        c.execute(text("""UPDATE dealer_tickets SET status = 'IN PROGRESS', updated_at = NOW(),
                              customer_remark = 'Technician assigned — visiting the store today'
                          WHERE id IN (SELECT id FROM dealer_tickets WHERE status = 'OPEN' ORDER BY raised_at LIMIT 5)""")
                  )
        n = c.execute(text("SELECT COUNT(*) FROM form_job_cards")).scalar()
        t = c.execute(text("SELECT COUNT(*) FROM dealer_tickets")).scalar()
        m = c.execute(text("SELECT COUNT(*) FROM inv_moves")).scalar()
    print(f"Demo data ready: {len(USERS)} logins (password demo1234), {n} job cards, {t} tickets, {m} stock entries.")


def status_fields(day):
    """Older job cards are closed by the TSM; recent ones may still be open."""
    age = (TODAY - day).days
    closed = age > 6 or rnd.random() < 0.4
    return {"tstatus": "CLOSED" if closed else "OPEN",
            "cat": rnd.choice(["LOW", "MEDIUM", "HIGH"]) if closed else None,
            "tobs": rnd.choice(["Parts replaced, test ride OK", "Adjusted and cleaned, working fine",
                                "Replaced worn part, customer informed"]) if closed else None,
            "action": day + dt.timedelta(days=rnd.randint(0, 3)) if closed else None,
            "fstatus": "Completed" if closed else "Pending",
            "done": day + dt.timedelta(days=rnd.randint(0, 2)) if closed else None}


def rental_job(n, day):
    ts = dt.datetime.combine(day, dt.time(rnd.randint(8, 19), rnd.randint(0, 59)))
    ch = chassis(rnd.randint(1, 60))
    recovery = rnd.random() < 0.08
    stype = "Recovery Vehicle" if recovery else rnd.choice(["General Service", "Breakdown", "Running Repair"])
    parts = pick_parts(rnd.randint(1, 3))
    form = {"Job Card No": f"JC-R-{n:04d}", "Timestamp": ts.isoformat(sep=" "), "Job Card Purpose": "Rental Service - Central Hub",
            "Chassis Number": ch, "ODO Meter Run": str(rnd.randint(1500, 26000)), "Service Type": stype,
            "Job Reported by": rnd.choice(TECHS)}
    if recovery:
        form["List Out The Damaged Components"] = ", ".join(parts)
    elif stype == "General Service":
        form["Consumed Spares Lists"] = ", ".join(parts[:1])
        form["Paid - Replaced Spares"] = GENERAL
    else:
        form["Paid - Replaced Spares"] = ", ".join(parts)
    if rnd.random() < 0.1:
        form["Warranty Parts Replaced"] = rnd.choice(["CONTROLLER 48V 30A", "DC DC CONVERTER", "CHARGER 58.4V 20A"])
    s = status_fields(day)
    form["Job Status"] = s["fstatus"]
    return {"job_type": "Rental", "job_card_no": form["Job Card No"], "ts": ts, "day": day,
            "client_name": "FleetCo Rental Fleet", "client_location": "Central Hub", "service_type": stype,
            "chassis": ch, "odo": form["ODO Meter Run"], "tech": form["Job Reported by"],
            "obs": form.get("List Out The Damaged Components") or form.get("Paid - Replaced Spares"), "form": form, **s}


def b2b_job(n, day, client, store, ch):
    ts = dt.datetime.combine(day, dt.time(rnd.randint(8, 19), rnd.randint(0, 59)))
    stype = rnd.choice(["General Service", "Breakdown", "Complaint"])
    parts = pick_parts(rnd.randint(1, 3))
    obs = rnd.choice(["Brake noise reported by rider", "Vehicle not starting", "Low range after charging",
                      "Periodic service due", "Indicator not working"])
    form = {"Job card No": f"JC-B-{n:04d}", "Timestamp": ts.isoformat(sep=" "), "Client/Partner Name": client,
            "Store Location" if client == "QuickBite" else "Site Location": store or "Main Depot",
            "Service Type": stype, "Chassis Number": ch, "ODO Meter Run": str(rnd.randint(800, 18000)),
            "Job Addressed By": rnd.choice(TECHS), "Field Observation": obs}
    if stype == "General Service":
        form["General Service"] = "Yes"
        form["Paid Replaced Spares"] = GENERAL
        form["Consumed Spares on General Service"] = ", ".join(parts[:1])
    else:
        form["Paid Replaced Spares"] = ", ".join(parts)
    if rnd.random() < 0.12:
        form["Warranty Parts Replaced"] = rnd.choice(["THROTTLE ASSEMBLY", "HEADLAMP ASSEMBLY", "DC DC CONVERTER"])
    s = status_fields(day)
    form["Job Status"] = s["fstatus"]
    return {"job_type": "B2B", "job_card_no": form["Job card No"], "ts": ts, "day": day, "client_name": client,
            "client_location": store or "Main Depot", "service_type": stype, "chassis": ch,
            "odo": form["ODO Meter Run"], "tech": form["Job Addressed By"], "obs": obs, "form": form, **s}


if __name__ == "__main__":
    main()
