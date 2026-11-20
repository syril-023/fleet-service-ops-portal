import streamlit as st
import psycopg2
import pandas as pd
import base64
import html
import re
import threading
import jobcards
import inventory
from sqlalchemy import text as sqltext
from db_config import DB_CONFIG, get_engine

# ─── PAGE CONFIG ─────────────────────────────────────────────────────
st.set_page_config(
    page_title="Fleet Service Ops Portal",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─── LOAD IMAGES ─────────────────────────────────────────────────────
def img_to_b64(path):
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except:
        return None

only_logo_b64 = img_to_b64("assets/FleetComotorspvtlimited_only_logo.jpeg")
full_logo_b64  = img_to_b64("assets/fleetcomotorspvtlimited_logo.jpg")

LOGO_ONLY = (f'<img src="data:image/jpeg;base64,{only_logo_b64}" style="height:48px;">'
             if only_logo_b64 else "⚡")
LOGO_FULL = (f'<img src="data:image/jpeg;base64,{full_logo_b64}" style="height:30px;">'
             if full_logo_b64 else "<b style='color:white;'>⚡ FLEETCO</b>")
LOGO_SIDEBAR = (f'<img src="data:image/jpeg;base64,{only_logo_b64}" style="height:38px;">'
                if only_logo_b64 else "⚡")

NAVY  = "#1B3A6B"
GREEN = "#2E7D32"
WHITE = "#FFFFFF"
LIGHT = "#F0F4FF"

# ─── GLOBAL CSS ──────────────────────────────────────────────────────
st.markdown(f"""
<style>
    .block-container {{ padding-top: 0rem !important; }}
    header[data-testid="stHeader"] {{ height: 0px !important; background: transparent !important; }}
    #MainMenu {{ visibility: hidden; }}
    footer {{ visibility: hidden; }}
    .stApp {{ background-color: {LIGHT}; }}

    /* Sidebar */
    [data-testid="stSidebar"] {{
        background: linear-gradient(180deg, {NAVY} 0%, #0A1628 100%);
        border-right: 3px solid {GREEN};
    }}
    [data-testid="stSidebar"] * {{ color: {WHITE} !important; }}
    [data-testid="stSidebar"] .stButton > button {{
        background: rgba(255,255,255,0.08) !important;
        color: {WHITE} !important;
        border: 1px solid rgba(255,255,255,0.15) !important;
        border-radius: 8px !important;
        text-align: left !important;
        padding: 10px 16px !important;
        font-size: 14px !important;
        margin-bottom: 4px !important;
    }}
    [data-testid="stSidebar"] .stButton > button:hover {{
        background: rgba(46,125,50,0.4) !important;
        border-color: {GREEN} !important;
    }}

    /* KPI cards */
    [data-testid="metric-container"] {{
        background: {WHITE};
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 16px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    }}

    /* Main buttons (inside dashboard etc.) */
    div[data-testid="stMainBlockContainer"] .stButton > button {{
        background: {NAVY} !important;
        color: {WHITE} !important;
        border-radius: 8px !important;
        border: none !important;
        font-weight: 500 !important;
    }}
    div[data-testid="stMainBlockContainer"] .stButton > button:hover {{
        background: {GREEN} !important;
    }}

    h1, h2, h3 {{ color: {NAVY}; }}

    .stTabs [data-baseweb="tab"][aria-selected="true"] {{
        background: {NAVY};
        color: white;
        border-radius: 8px;
    }}
</style>
""", unsafe_allow_html=True)

# ─── DB HELPERS ──────────────────────────────────────────────────────
def run_query(query, params=None):
    # SQLAlchemy with text() wrapper — no pandas warnings!
    # SECURITY: never put user input inside the SQL string —
    # use :name placeholders and pass values in params={"name": value}
    try:
        from sqlalchemy import text
        engine = get_engine()
        with engine.connect() as conn:
            result = pd.read_sql_query(text(query), conn, params=params or {})
        return result
    except Exception as e:
        st.error(f"Query error: {e}")
        return pd.DataFrame()

def show_table(data, height=600):
    """
    LESSON: st.dataframe uses Canvas — CSS can't style it properly.
    Solution: Convert DataFrame to HTML table manually.
    This gives us 100% control over colors, fonts, padding!
    """
    if data is None or data.empty:
        st.markdown("""
        <div style="background:#F8FAFF; border:1px solid #E2E8F0;
                    border-radius:8px; padding:30px; text-align:center;">
            <p style="color:#94A3B8; margin:0;">No data available</p>
        </div>
        """, unsafe_allow_html=True)
        return
    st.markdown(table_html(data, height), unsafe_allow_html=True)


def table_html(data, height=600, info_ids=None):
    """The portal's table as HTML. info_ids (one per row) adds a clickable ⓘ column on the right."""
    # Build HTML table manually — 100% style control!
    # Header row — Navy background, White text, STICKY position
    headers = "".join([
        f'<th style="background:#1B3A6B; color:white; font-weight:600; '
        f'font-size:13px; padding:10px 14px; text-align:left; '
        f'border-bottom:2px solid #0F2347; white-space:nowrap; '
        f'position:sticky; top:0; z-index:10;">{col}</th>'
        for col in data.columns
    ])
    if info_ids is not None:   # ⓘ column stays visible on the right while scrolling sideways
        headers += ('<th style="background:#1B3A6B; color:white; font-size:13px; padding:10px 12px; '
                    'text-align:center; border-bottom:2px solid #0F2347; position:sticky; top:0; right:0; '
                    'z-index:11;">ⓘ</th>')

    # Data rows — alternating White and Light Sky Blue
    rows_html = ""
    for i, (_, row) in enumerate(data.iterrows()):
        # Even rows = White, Odd rows = Light Sky Blue
        bg = "#FFFFFF" if i % 2 == 0 else "#DBEAFE"
        cells = ""
        for val in row:
            # Format numbers cleanly — no trailing zeros!
            if val is None or (isinstance(val, float) and pd.isna(val)):
                display = ""   # empty cell (pandas 3 gives NaN for missing text)
            elif isinstance(val, float):
                # If it's a whole number like 5500.0, show as 5500
                display = str(int(val)) if val == int(val) else f"{val:.2f}"
            else:
                # escape so text like "<b>" typed into a form shows as text, not HTML
                display = html.escape(str(val)) if val is not None else ""
            cells += (
                f'<td style="background:{bg}; color:#1A1A1A; '
                f'font-size:13px; padding:8px 14px; '
                f'border-bottom:1px solid #E2E8F0;">{display}</td>'
            )
        if info_ids is not None:
            cells += (f'<td style="background:{bg}; padding:6px 12px; text-align:center; '
                      f'border-bottom:1px solid #E2E8F0; position:sticky; right:0; '
                      f'box-shadow:-2px 0 4px rgba(15,35,71,0.08);">'
                      f'<a href="#" data-jc="{int(info_ids[i])}" title="Open / update this job card" '
                      f'style="color:#1B3A6B; font-size:18px; font-weight:700; text-decoration:none; '
                      f'cursor:pointer;">ⓘ</a></td>')
        rows_html += f"<tr>{cells}</tr>"

    # Complete table HTML
    # LESSON: overflow-y:auto on tbody with fixed height = only rows scroll
    # thead stays fixed (sticky) — header never moves!
    # overflow-x:auto = horizontal scroll if too many columns
    table_html = f"""
    <div style="border-radius:10px; border:1px solid #E2E8F0;
                margin-top:8px; overflow:hidden;">
        <div style="overflow-x:auto; overflow-y:auto;
                    max-height:{height}px;">
            <table style="width:100%; border-collapse:collapse;
                          font-family:Arial,sans-serif; min-width:600px;">
                <thead>
                    <tr style="position:sticky; top:0; z-index:10;">
                        {headers}
                    </tr>
                </thead>
                <tbody>{rows_html}</tbody>
            </table>
        </div>
    </div>
    """
    return table_html


def info_table_component():
    """The portal table + clickable ⓘ: a small inline component that tells Python which row was clicked
    (a plain link would reload the page and log the user out)."""
    js = """
    export default function(component) {
        const { data, setTriggerValue, parentElement } = component;
        let box = parentElement.querySelector('.jc-box');
        if (!box) { box = document.createElement('div'); box.className = 'jc-box'; parentElement.appendChild(box); }
        box.innerHTML = data;
        box.querySelectorAll('a[data-jc]').forEach((a) => {
            a.onclick = (e) => { e.preventDefault(); setTriggerValue('open', a.getAttribute('data-jc')); };
        });
    }
    """
    return st.components.v2.component("fleetco_info_table", js=js)


def show_info_table(data, ids, key, height=600):
    """Show the table with an ⓘ per row; returns the clicked row's id (once per click) or None."""
    html_str = table_html(data, height, info_ids=list(ids))
    res = info_table_component()(key=key, data=html_str, on_open_change=lambda: None)
    return int(res.open) if res and getattr(res, "open", None) else None


def download_excel(data, filename="FleetCo_Export"):
    """
    Adds a Download as Excel button below any table.
    Uses pandas to_excel() → BytesIO → st.download_button
    """
    import io
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        data.to_excel(writer, index=False, sheet_name='Data')
    buffer.seek(0)
    st.download_button(
        label="📥 Download as Excel",
        data=buffer,
        file_name=f"{filename}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key=f"dl_{filename}_{len(data)}"
    )

def run_insert(query, params):
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute(query, params)
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        st.error(f"Insert error: {e}")
        return False

def check_password(password, password_hash):
    # bcrypt compare — returns False for empty/placeholder hashes
    import bcrypt
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except (ValueError, AttributeError):
        return False

def hash_password(password):
    import bcrypt
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()

def temp_password():
    import secrets
    return secrets.token_urlsafe(9)

# ─── ROLES & PAGE ACCESS ─────────────────────────────────────────────
# "edit" = view + add/change · "view" = read only · missing = page hidden
ROLES = ["Super Admin", "Service Head", "Area Service Manager",
         "Store Incharge", "Territory Manager", "Dealer"]
ZONES = ["Central", "South", "South West", "North"]

NAV_PAGES = [
    ("🏠", "Overview"), ("➕", "Raise Complaint"), ("🛵", "My Vehicles"),   # dealer pages
    ("📊", "Dashboard"), ("🛵", "Fleet"),
    ("📦", "Parts Master"), ("📥", "Stock IN"),
    ("📤", "Stock OUT"),   ("🔧", "Job Cards"),
    ("🎫", "Tickets"),     ("🧾", "Service History"),
    ("📈", "Reports"),
    ("👥", "Users"),
]
DEALER_ONLY = {"Overview", "Raise Complaint", "My Vehicles", "Service History"}

_ALL_EDIT = {p: "edit" for _, p in NAV_PAGES if p != "Users" and p not in DEALER_ONLY}
ROLE_ACCESS = {
    "Super Admin":          {**_ALL_EDIT, "Users": "edit"},
    "Service Head":         _ALL_EDIT,
    "Area Service Manager": _ALL_EDIT,
    "Store Incharge":       _ALL_EDIT,
    # TSM: own clients' job cards + dealer tickets, parts & stock read only
    # (a TSM who keeps a hub's stock — users.stock_hub — enters that hub's stock).
    # Dashboard / Reports per zone come later (point 3). Fleet only if they
    # own the rental fleet — added at login.
    "Territory Manager": {
        "Job Cards": "edit", "Tickets": "edit", "Parts Master": "view", "Stock IN": "view",
        "Stock OUT": "view",
    },
    # Dealer (customer login, e.g. QuickBite): ONLY their own client's tickets and job cards
    "Dealer": {
        "Overview": "view", "Raise Complaint": "edit", "My Vehicles": "view", "Tickets": "view",
        "Service History": "view",
    },
}

def page_access(page):
    if page == "Change Password":
        return "edit"   # everyone can change their own password
    access = dict(ROLE_ACCESS.get(st.session_state.role, {}))
    if st.session_state.get("has_rental"):
        access.setdefault("Fleet", "view")
    if st.session_state.get("stock_hub") and st.session_state.role != "Dealer" and page in ("Stock IN", "Stock OUT"):
        return "edit"   # the hub's store person enters its stock, whatever their role
    return access.get(page)

def can_edit(page):
    return page_access(page) == "edit"

def is_tsm():
    return st.session_state.role == "Territory Manager"

def is_dealer():
    return st.session_state.role == "Dealer"

def allowed_pages():
    return [(i, p) for i, p in NAV_PAGES if page_access(p)]

# ─── SESSION STATE ────────────────────────────────────────────────────
for k, v in {
    "logged_in": False, "username": "", "full_name": "",
    "role": "", "user_id": None, "zone": "", "has_rental": False,
    "dealer_client": "", "dealer_store": "", "stock_hub": "",
    "must_change_password": False, "page": "Dashboard"
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ════════════════════════════════════════════════════════════════════
# LOGIN PAGE
# ════════════════════════════════════════════════════════════════════
def show_login():
    st.markdown(f"""
    <style>
    /* Full page dark gradient */
    .stApp {{
        background: linear-gradient(135deg, #0F1E3D 0%, #1B3A6B 50%, #0D5C2E 100%) !important;
    }}
    /* Vertically center the card */
    .main .block-container {{
        min-height: 100vh !important;
        display: flex !important;
        flex-direction: column !important;
        justify-content: center !important;
        padding-top: 0 !important;
        padding-bottom: 0 !important;
    }}
    /* ── LOGIN INPUT BOXES ──
       LESSON: We set these here specifically for login page
       because the global CSS above uses different colors for dashboard
       White background with dark text = clearly readable! */
    .stTextInput > div > div > input {{
        background: rgba(255,255,255,0.95) !important;  /* Almost white bg */
        color: #1A1A1A !important;                       /* Dark text */
        border: 2px solid rgba(255,255,255,0.3) !important;
        border-radius: 10px !important;
        padding: 12px 16px !important;
        font-size: 14px !important;
    }}
    .stTextInput > div > div > input:focus {{
        border: 2px solid {GREEN} !important;
        box-shadow: 0 0 0 3px rgba(46,125,50,0.25) !important;
    }}
    .stTextInput > div > div > input::placeholder {{
        color: #888888 !important;    /* Grey placeholder — visible! */
    }}
    /* Remove input labels */
    .stTextInput > label {{ display: none !important; }}

    /* ── SIGN IN BUTTON ──
       Green by default, Navy on hover */
    .stButton > button {{
        background: {GREEN} !important;
        color: white !important;
        font-size: 15px !important;
        padding: 12px 24px !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
        border: none !important;
        letter-spacing: 0.3px !important;
        transition: all 0.2s ease !important;
        margin-top: 6px !important;
    }}
    .stButton > button:hover {{
        background: {NAVY} !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 6px 20px rgba(0,0,0,0.3) !important;
    }}
    </style>
    """, unsafe_allow_html=True)

    # Vertical spacing
    st.markdown("<br>", unsafe_allow_html=True)

    # [2, 1.4, 2] = wider sides → compact centered card
    _, col, _ = st.columns([2, 1.4, 2])

    with col:

        # ── TOP COMPANY BAR (NO white box, text centered) ──────────
        # CHANGE: Removed logo white box
        # CHANGE: Text now centered
        st.markdown(f"""
        <div style="
            background: rgba(255,255,255,0.07);
            border: 1px solid rgba(255,255,255,0.12);
            border-radius: 12px;
            padding: 14px 20px;
            text-align: center;
            margin-bottom: 16px;
            backdrop-filter: blur(10px);
        ">
            <div style="color:white; font-size:15px; font-weight:600; letter-spacing:0.3px;">
                FleetCo Mobility Pvt Ltd
            </div>
            <div style="color:rgba(255,255,255,0.6); font-size:12px; margin-top:4px;">
                📍 Central Hub
            </div>
        </div>
        """, unsafe_allow_html=True)

        # ── CARD HEADER ─────────────────────────────────────────────
        st.markdown(f"""
        <div style="
            background: linear-gradient(160deg, rgba(27,58,107,0.95), rgba(15,35,71,0.98));
            border-radius: 20px 20px 0 0;
            padding: 36px 28px 28px;
            text-align: center;
            border-bottom: 3px solid {GREEN};
            border-left: 1px solid rgba(255,255,255,0.08);
            border-right: 1px solid rgba(255,255,255,0.08);
            border-top: 1px solid rgba(255,255,255,0.08);
        ">
            <!-- Only Logo (B symbol) in white rounded box -->
            <div style="
                background: white;
                border-radius: 14px;
                padding: 14px 18px;
                display: inline-block;
                margin-bottom: 18px;
                box-shadow: 0 4px 16px rgba(0,0,0,0.3);
            ">
                {LOGO_ONLY}
            </div>
            <h2 style="
                color: white; margin: 0 0 10px 0;
                font-size: 20px; font-weight: 600;
            ">Fleet Service Operations</h2>
            <p style="
                color: rgba(255,255,255,0.65);
                margin: 0; font-size: 12px; letter-spacing: 0.5px;
            ">⚙️ Bizops &nbsp;|&nbsp; 📦 Inventory &nbsp;|&nbsp; 📊 Reports — Portal 💻</p>
        </div>
        """, unsafe_allow_html=True)

        # ── CARD BODY (same dark gradient — NO white strip!) ────────
        # CHANGE: Removed "Sign in to your account" text entirely
        # CHANGE: No white background — blends with card
        st.markdown(f"""
        <div style="
            background: linear-gradient(160deg, rgba(15,35,71,0.97), rgba(10,22,40,0.98));
            padding: 24px 8px 8px;
            border-left: 1px solid rgba(255,255,255,0.08);
            border-right: 1px solid rgba(255,255,255,0.08);
        ">
        </div>
        """, unsafe_allow_html=True)

        # ── INPUT FIELDS ─────────────────────────────────────────────
        # LESSON: These st. commands must be OUTSIDE HTML blocks
        # They render as white boxes with dark text (set in CSS above)
        username = st.text_input("u",
            placeholder="👤  Username",
            label_visibility="collapsed",
            key="li_user")

        password = st.text_input("p",
            placeholder="🔒  Password",
            type="password",
            label_visibility="collapsed",
            key="li_pass")

        login_btn = st.button("Sign In →",
            width='stretch',
            key="li_btn")

        # ── CARD FOOTER (dark — NO white box!) ──────────────────────
        # CHANGE: Removed white background → now dark gradient = seamless!
        st.markdown(f"""
        <div style="
            background: linear-gradient(160deg, rgba(10,22,40,0.98), rgba(8,18,35,0.99));
            padding: 16px 24px;
            text-align: center;
            border-radius: 0 0 20px 20px;
            border: 1px solid rgba(255,255,255,0.06);
            border-top: 1px solid rgba(255,255,255,0.08);
            margin-top: 8px;
        ">
            <p style="color: rgba(255,255,255,0.30); font-size: 11px; margin: 0;">
                🔒 FleetCo Mobility Pvt Ltd · Central Hub · Authorised Users Only
            </p>
        </div>
        """, unsafe_allow_html=True)

        # Version tag
        st.markdown("""
        <div style="text-align:center; margin-top: 14px;">
            <span style="
                color: rgba(255,255,255,0.25); font-size: 11px;
                background: rgba(255,255,255,0.05);
                padding: 4px 14px; border-radius: 999px;
                border: 1px solid rgba(255,255,255,0.08);
            ">Service Bizops Portal v1.0 · 2026</span>
        </div>
        """, unsafe_allow_html=True)

        # ── LOGIN LOGIC ──────────────────────────────────────────────
        if login_btn:
            if username and password:
                with st.spinner("Verifying..."):
                    try:
                        conn = psycopg2.connect(**DB_CONFIG)
                        cur = conn.cursor()
                        # Username is case-insensitive: "admin" = "Admin"
                        cur.execute(
                            """SELECT user_id, full_name, role, password_hash, username,
                                      COALESCE(zone,''), COALESCE(must_change_password,FALSE),
                                      EXISTS (SELECT 1 FROM client_locations c
                                              WHERE c.tsm_user_id = users.user_id
                                                AND c.is_rental AND c.is_active),
                                      COALESCE(dealer_client,''), COALESCE(dealer_store,''),
                                      CEIL(EXTRACT(EPOCH FROM locked_until - NOW()) / 60),
                                      COALESCE(stock_hub,'')
                               FROM users WHERE LOWER(username)=LOWER(%s) AND is_active=TRUE""",
                            (username.strip(),)
                        )
                        user = cur.fetchone()
                        locked_min = user[10] if user and user[10] and user[10] > 0 else None
                        blocked = None
                        if locked_min:
                            # 5 wrong passwords → locked for 15 minutes (stops password guessing)
                            blocked = f"🔒 Too many wrong passwords. Try again in {int(locked_min)} minute(s)."
                            user = None
                        # Check password against bcrypt hash in DB
                        elif user and not check_password(password, user[3]):
                            cur.execute("""UPDATE users SET
                                               failed_logins = CASE WHEN failed_logins + 1 >= 5 THEN 0 ELSE failed_logins + 1 END,
                                               locked_until  = CASE WHEN failed_logins + 1 >= 5
                                                                    THEN NOW() + INTERVAL '15 minutes' END
                                           WHERE user_id=%s""", (user[0],))
                            conn.commit()
                            user = None
                        if user:
                            cur.execute("""UPDATE users SET last_login=NOW(), failed_logins=0, locked_until=NULL
                                           WHERE user_id=%s""", (user[0],))
                            conn.commit()
                        conn.close()
                        if user and user[2] == "Dealer" and not user[8]:
                            blocked, user = "❌ This dealer login has no client set. Please contact FleetCo.", None
                        if blocked:
                            st.error(blocked)
                        elif user:
                            st.session_state.logged_in  = True
                            st.session_state.username   = user[4]
                            st.session_state.full_name  = user[1]
                            st.session_state.role       = user[2]
                            st.session_state.user_id    = user[0]
                            st.session_state.zone       = user[5]
                            st.session_state.must_change_password = user[6]
                            st.session_state.has_rental = user[7]
                            st.session_state.dealer_client = user[8]
                            st.session_state.dealer_store  = user[9]
                            st.session_state.stock_hub     = user[11]
                            # land on the first page this role can open
                            st.session_state.page = allowed_pages()[0][1]
                            st.rerun()
                        else:
                            st.error("❌ Invalid username or password. Please try again.")
                    except Exception as e:
                        st.error(f"Connection error: {e}")
            else:
                st.warning("⚠️ Please enter both username and password.")

    st.markdown("<br>", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════
# TOP NAVBAR (after login)
# ════════════════════════════════════════════════════════════════════
def show_topbar():
    st.markdown(f"""
    <div style="
        background: linear-gradient(90deg, {NAVY} 0%, #0A1628 100%);
        padding: 10px 28px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        border-bottom: 3px solid {GREEN};
        margin: -1rem -4rem 1.5rem -4rem;
    ">
        <div style="display:flex; align-items:center; gap:14px;">
            <div style="background:white; border-radius:8px; padding:5px 12px;">
                {LOGO_FULL}
            </div>
            <div>
                <div style="color:white; font-size:15px; font-weight:600;">
                    FleetCo Mobility Pvt Ltd
                </div>
                <div style="color:rgba(255,255,255,0.55); font-size:11px; margin-top:2px;">
                    ⚙️ Service Bizops Portal &nbsp;·&nbsp; 📍 Central Hub
                </div>
            </div>
        </div>
        <div style="text-align:right;">
            <div style="color:white; font-size:13px; font-weight:500;">
                👤 {st.session_state.full_name}
            </div>
            <div style="color:rgba(255,255,255,0.55); font-size:11px; margin-top:2px;">
                🏷️ {html.escape(user_scope_label())}
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def user_scope_label():
    """'Dealer · QuickBite · All stores' for dealers, the role for the FleetCo team."""
    if is_dealer():
        return f"Dealer · {st.session_state.dealer_client} · {st.session_state.dealer_store or 'All stores'}"
    return st.session_state.role

# ════════════════════════════════════════════════════════════════════
# SIDEBAR
# ════════════════════════════════════════════════════════════════════
def show_sidebar():
    with st.sidebar:
        st.markdown(f"""
        <div style="background:white; border-radius:12px; padding:10px 14px;
                    margin-bottom:14px; text-align:center;">
            {LOGO_SIDEBAR}
        </div>
        """, unsafe_allow_html=True)

        st.markdown(f"""
        <div style="background:rgba(46,125,50,0.2); border:1px solid rgba(46,125,50,0.5);
                    border-radius:10px; padding:10px 14px; margin-bottom:14px;">
            <div style="font-size:13px; font-weight:600;">👤 {st.session_state.full_name}</div>
            <div style="font-size:11px; opacity:0.8; margin-top:3px;">🏷️ {st.session_state.role}</div>
            <div style="font-size:11px; opacity:0.8; margin-top:3px;">{sidebar_scope()}</div>
        </div>
        """, unsafe_allow_html=True)
        new_tickets = open_ticket_count() if page_access("Tickets") == "edit" else 0

        st.markdown("""
        <div style="color:rgba(255,255,255,0.35); font-size:10px;
                    letter-spacing:1.5px; margin-bottom:8px; padding-left:4px;">
            NAVIGATION
        </div>""", unsafe_allow_html=True)

        # Only pages this role is allowed to open
        for icon, page in allowed_pages():
            label = f"{icon}  {page}" + ("  👁" if page_access(page) == "view" and not is_dealer() else "")
            if page == "Tickets" and new_tickets:
                label += f"  🔴 {new_tickets} new"
            if st.button(label, width='stretch', key=f"nav_{page}"):
                st.session_state.page = page
                st.rerun()

        st.markdown("---")
        if st.button("🔑  Change Password", width='stretch', key="nav_pw"):
            st.session_state.page = "Change Password"
            st.rerun()
        if st.button("🚪  Logout", width='stretch', key="logout"):
            # wipe everything (carts, filters…) so the next person starts clean
            st.session_state.clear()
            st.rerun()

        st.markdown("""
        <div style="text-align:center; color:rgba(255,255,255,0.2);
                    font-size:10px; margin-top:20px;">
            Fleet Service Ops v1.0
        </div>""", unsafe_allow_html=True)

def sidebar_scope():
    if is_dealer():
        return f"🏪 {html.escape(st.session_state.dealer_client)} · {html.escape(st.session_state.dealer_store or 'All stores')}"
    return f"📍 {st.session_state.zone or '—'} Zone"


def open_ticket_count():
    """Tickets nobody has picked up yet (OPEN) — a TSM counts only their own clients'."""
    r = run_query(f"""SELECT COUNT(*) AS n FROM dealer_tickets t
                      WHERE t.status = 'OPEN' {"AND " + TSM_TICKET_SCOPE if is_tsm() else ""}""",
                  {"uid": st.session_state.user_id})
    return int(r["n"].iloc[0]) if not r.empty else 0

# ════════════════════════════════════════════════════════════════════
# DASHBOARD
# ════════════════════════════════════════════════════════════════════
def show_dashboard():
    # ── Session state for selected KPI ──
    # WHY: Tracks which KPI card user clicked
    #      So we know which table to show below
    if "selected_kpi" not in st.session_state:
        st.session_state.selected_kpi = "fleet_total"

    # Page Title
    st.markdown("""
    <div style="margin-bottom:8px;">
        <h2 style="color:#1B3A6B; font-size:24px; font-weight:700; margin:0;">
            📊 Dashboard
        </h2>
        <p style="color:#64748B; font-size:13px; margin:4px 0 0 0;">
            Live Central Hub Fleet & Service Overview — Click any KPI card to explore data
        </p>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("---")

    # ── Get all data ──
    fleet = run_query("SELECT fleet_status, COUNT(*) as cnt FROM rental_fleet GROUP BY fleet_status")
    def gc(s):
        if fleet.empty: return 0
        r = fleet[fleet["fleet_status"]==s]["cnt"]
        return int(r.values[0]) if len(r) > 0 else 0

    total   = int(fleet["cnt"].sum()) if not fleet.empty else 0
    active  = gc("Active")
    service = gc("Under Service")
    avail   = gc("Available")

    pending = run_query("SELECT COUNT(*) as c FROM form_job_cards")
    techs   = run_query("SELECT COUNT(*) as c FROM technicians WHERE is_active=TRUE")
    rev     = run_query("SELECT COALESCE(SUM(COALESCE(spares_cost,0) + COALESCE(labor_cost,0)),0) as r FROM form_job_cards WHERE job_type = 'B2B'")      # B2B is invoiced; rental is internal
    low     = run_query(f"SELECT COUNT(*) AS c FROM ({LOW_STOCK_SQL}) x")

    pend_val = int(pending["c"].iloc[0]) if not pending.empty else 0
    tech_val = int(techs["c"].iloc[0])   if not techs.empty else 0
    low_val  = int(low["c"].iloc[0])     if not low.empty else 0
    rev_val  = f"\u20b9{int(rev['r'].iloc[0]):,}" if not rev.empty else "\u20b90"

    # ════════════════════════════════════════════
    # KPI CARDS — Row 1: Fleet Status
    # ════════════════════════════════════════════
    st.markdown("""
    <p style="color:#1B3A6B; font-size:14px; font-weight:600; margin-bottom:8px;">
        🛵 Fleet Status
    </p>""", unsafe_allow_html=True)

    # LESSON: We use st.button inside each column to make cards clickable
    # When button clicked → st.session_state.selected_kpi changes
    # → Page reruns → Different table shows below
    c1, c2, c3, c4 = st.columns(4)

    # Helper: is this card currently selected?
    def is_selected(kpi_id):
        return st.session_state.selected_kpi == kpi_id

    # CSS: Style the KPI buttons to LOOK like cards
    # Each button is the entire card — no separate HTML needed!
    st.markdown("""
    <style>
    /* Make KPI buttons look like cards - no plain button appearance */
    div[data-testid="stHorizontalBlock"] .stButton > button {
        background: white !important;
        color: #1A1A1A !important;
        border-radius: 12px !important;
        border: 1px solid #E2E8F0 !important;
        padding: 18px 16px !important;
        height: auto !important;
        min-height: 110px !important;
        text-align: center !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06) !important;
        font-size: 15px !important;
        font-weight: 700 !important;
        white-space: pre-line !important;
        line-height: 2.0 !important;
        transition: all 0.2s !important;
        width: 100% !important;
    }
    div[data-testid="stHorizontalBlock"] .stButton > button:hover {
        box-shadow: 0 6px 20px rgba(0,0,0,0.12) !important;
        transform: translateY(-3px) !important;
        border-color: #1B3A6B !important;
        background: #FAFCFF !important;
    }
    div[data-testid="stHorizontalBlock"] .stButton > button:focus {
        outline: none !important;
        box-shadow: 0 6px 20px rgba(0,0,0,0.12) !important;
    }
    </style>
    """, unsafe_allow_html=True)

    for col, (kpi_id, icon, value, label, color) in zip(
        [c1, c2, c3, c4],
        [
            ("fleet_total",   "🛵", total,   "Total Fleet",     "#1B3A6B"),
            ("fleet_active",  "✅", active,  "Active / Rented", "#2E7D32"),
            ("fleet_service", "🔧", service, "Under Service",   "#E87722"),
            ("fleet_rfd",     "🚀", avail,   "RFD",             "#0EA5E9"),
        ]
    ):
        selected = is_selected(kpi_id)
        brd = f"2px solid {color}" if selected else "1px solid #E2E8F0"
        shd = f"0 4px 16px {color}33" if selected else "0 2px 8px rgba(0,0,0,0.06)"
        with col:
            # Colored top bar
            st.markdown(f"""
            <div style="height:5px; background:{color};
                        border-radius:6px 6px 0 0;
                        opacity:{'1' if selected else '0.3'};
                        margin-bottom:0;"></div>
            """, unsafe_allow_html=True)
            btn_label = f"{icon}\n{value}\n{label}"
            if st.button(btn_label, key=f"btn_{kpi_id}", width='stretch'):
                st.session_state.selected_kpi = kpi_id
                st.rerun()


    # ════════════════════════════════════════════
    # KPI CARDS — Row 2: Operations
    # ════════════════════════════════════════════
    st.markdown("""
    <p style="color:#1B3A6B; font-size:14px; font-weight:600; margin-bottom:8px;">
        ⚙️ Operations
    </p>""", unsafe_allow_html=True)

    c5, c6, c7, c8 = st.columns(4)
    c5, c6, c7, c8 = st.columns(4)
    for col, (kpi_id, icon, value, label, color) in zip(
        [c5, c6, c7, c8],
        [
            ("ops_jobs",    "📋", pend_val, "Total Job Cards", "#EF4444"),
            ("ops_techs",   "👷", tech_val, "Technicians",     "#8B5CF6"),
            ("ops_low",     "⚠️",  low_val, "Low Stock Parts", "#F59E0B"),
            ("ops_revenue", "💰", rev_val,  "Total Billed",    "#10B981"),
        ]
    ):
        selected = is_selected(kpi_id)
        with col:
            st.markdown(f"""
            <div style="height:5px; background:{color};
                        border-radius:6px 6px 0 0;
                        opacity:{'1' if selected else '0.3'};
                        margin-bottom:0;"></div>
            """, unsafe_allow_html=True)
            btn_label = f"{icon}\n{value}\n{label}"
            if st.button(btn_label, key=f"btn_{kpi_id}", width='stretch'):
                st.session_state.selected_kpi = kpi_id
                st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # ════════════════════════════════════════════
    # DYNAMIC TABLE — changes based on selected KPI
    # LESSON: if/elif chain checks selected_kpi
    #         and shows the right table
    # ════════════════════════════════════════════
    kpi = st.session_state.selected_kpi

    # Table header labels
    table_titles = {
        "fleet_total":   ("🛵", "#1B3A6B", "All Fleet Vehicles"),
        "fleet_active":  ("✅", "#2E7D32", "Active / Currently Rented Vehicles"),
        "fleet_service": ("🔧", "#E87722", "Vehicles Under Service"),
        "fleet_rfd":     ("🚀", "#0EA5E9", "Ready for Deployment (RFD) Vehicles"),
        "ops_jobs":      ("📋", "#EF4444", "All Job Cards"),
        "ops_techs":     ("👷", "#8B5CF6", "Technician Details"),
        "ops_low":       ("⚠️", "#F59E0B", "Low Stock Parts Alert"),
        "ops_revenue":   ("💰", "#10B981", "Billing Summary"),
    }

    icon, color, title = table_titles.get(kpi, ("📊", "#1B3A6B", "Overview"))

    # Table title bar
    st.markdown(f"""
    <div style="background:white; border-radius:12px 12px 0 0;
                padding:14px 20px; border-bottom:3px solid {color};
                border:1px solid #E2E8F0; margin-bottom:0;">
        <span style="color:{color}; font-size:16px; font-weight:600;">
            {icon} {title}
        </span>
    </div>
    """, unsafe_allow_html=True)

    # ── TABLE CONTENT — based on selected KPI ──

    if kpi == "fleet_total":
        data = run_query("""
            SELECT vehicle_number "Vehicle No", vehicle_model "Model",
                   fleet_status "Status", current_odometer_km "Odometer(km)",
                   monthly_rental_amount "Rental ₹",
                   last_service_date::text "Last Service",
                   next_service_due_date::text "Next Service Due"
            FROM rental_fleet
            ORDER BY vehicle_number LIMIT 100
        """)

    elif kpi == "fleet_active":
        data = run_query("""
            SELECT vehicle_number "Vehicle No", vehicle_model "Model",
                   current_renter_name "Renter Name",
                   current_renter_phone "Phone",
                   monthly_rental_amount "Monthly Rental ₹",
                   rental_start_date::text "Rental Start",
                   current_odometer_km "Odometer(km)"
            FROM rental_fleet
            WHERE fleet_status = 'Active'
            ORDER BY vehicle_number LIMIT 100
        """)

    elif kpi == "fleet_service":
        data = run_query("""
            SELECT f.vehicle_number "Vehicle No", f.vehicle_model "Model",
                   j.job_card_no "Job Card", j.complaint "Complaint",
                   j.complaint_category "Category", j.job_status "Status",
                   t.tech_name "Technician", j.job_date::text "Date"
            FROM rental_fleet f
            LEFT JOIN job_cards j ON f.vehicle_id = j.vehicle_id
                AND j.job_status NOT IN ('Completed','Delivered','Cancelled')
            LEFT JOIN technicians t ON j.technician_id = t.tech_id
            WHERE f.fleet_status = 'Under Service'
            ORDER BY f.vehicle_number
        """)

    elif kpi == "fleet_rfd":
        data = run_query("""
            SELECT vehicle_number "Vehicle No", vehicle_model "Model",
                   battery_type "Battery",
                   current_odometer_km "Odometer(km)",
                   monthly_rental_amount "Rental Rate ₹",
                   last_service_date::text "Last Service"
            FROM rental_fleet
            WHERE fleet_status = 'Available'
            ORDER BY vehicle_number
        """)

    elif kpi == "ops_jobs":
        # Job cards with SEARCH BOX
        # LESSON: st.text_input for search, then filter the query
        search = st.text_input(
            "🔍",
            placeholder="Search by Job Card No or Vehicle Number...",
            label_visibility="collapsed",
            key="job_search"
        )
        where = ""
        if search:
            where = """WHERE j.job_card_no ILIKE :s OR j.chassis_number ILIKE :s
                        OR j.client_name ILIKE :s OR j.complaint_category ILIKE :s"""

        data = run_query(f"""
            SELECT j.job_card_no "Job Card No", j.job_type "Type", j.client_name "Client",
                   j.chassis_number "Chassis", j.field_observation "Complaint",
                   j.service_type "Service Type", COALESCE(j.tsm_job_status, 'OPEN') "Status",
                   j.technician "Technician", j.job_open_date::text "Date"
            FROM form_job_cards j
            {where}
            ORDER BY j.submitted_at DESC
        """, {"s": f"%{search}%"})
        st.markdown(f"<p style='color:#64748B; font-size:12px; margin:4px 0;'>Showing {len(data)} job cards</p>",
                   unsafe_allow_html=True)

    elif kpi == "ops_techs":
        data = run_query("""
            SELECT t.tech_code "Code",
                   t.tech_name "Name",
                   t.phone "Mobile",
                   'Central Hub' AS "Location",
                   t.designation "Designation",
                   t.specialization "Specialization",
                   t.monthly_salary "Salary ₹",
                   COUNT(j.job_card_id) "Total Jobs",
                   COUNT(CASE WHEN j.job_status IN ('Completed','Delivered') THEN 1 END) "Completed",
                   COUNT(CASE WHEN j.job_status NOT IN ('Completed','Delivered','Cancelled') THEN 1 END) "Pending"
            FROM technicians t
            LEFT JOIN job_cards j ON t.tech_id = j.technician_id
            WHERE t.is_active = TRUE
            GROUP BY t.tech_id
            ORDER BY t.tech_code
        """)

    elif kpi == "ops_low":
        data = run_query(f"""
            SELECT h.name "Hub", x.part_code "Part Code", x.description "Part",
                   x.landing_cost "Landing ₹", x.reorder_level "Low at or below", x.stock "Stock",
                   CASE WHEN x.stock < 0 THEN '⚠️ NEGATIVE' WHEN x.stock = 0 THEN '🔴 NO STOCK'
                        ELSE '🟡 LOW STOCK' END AS "Alert"
            FROM ({LOW_STOCK_SQL}) x JOIN stock_hubs h USING (hub)
            ORDER BY h.sort_order, x.stock, x.description
        """)

    elif kpi == "ops_revenue":
        data = run_query("""
            SELECT j.job_card_no "Job Card", j.client_name "Client", j.chassis_number "Chassis",
                   j.job_open_date::text "Date",
                   COALESCE(j.spares_cost,0) "Spares ₹", COALESCE(j.labor_cost,0) "Labour ₹",
                   COALESCE(j.spares_cost,0) + COALESCE(j.labor_cost,0) "Total Billing ₹"
            FROM form_job_cards j
            WHERE j.job_type = 'B2B'
            ORDER BY j.submitted_at DESC
        """)
    else:
        data = pd.DataFrame()

    # ── RENDER TABLE with custom styling ──
    if not data.empty:
        show_table(data, height=550)
    else:
        st.markdown(f"""
        <div style="background:#F8FAFF; border:1px solid #E2E8F0; border-radius:0 0 12px 12px;
                    padding:40px; text-align:center;">
            <p style="color:#94A3B8; font-size:14px; margin:0;">No data available</p>
        </div>
        """, unsafe_allow_html=True)

    # Tip text
    st.markdown(f"""
    <p style="color:#94A3B8; font-size:11px; text-align:right; margin-top:6px;">
        💡 Click any KPI card above to change the data view
    </p>
    """, unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════
# FLEET
# ════════════════════════════════════════════════════════════════════
def show_fleet():
    st.markdown("## 🛵 Fleet Management")
    st.markdown("All rental vehicles — live status and details")
    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    with c1: sf   = st.selectbox("Status", ["All","Active","Available","Under Service","Inactive"])
    with c2: mf   = st.selectbox("Model",  ["All","FleetCo City Pro","FleetCo Cargo X","FleetCo Urban Lite"])
    with c3: srch = st.text_input("🔍 Search Vehicle No.")

    q = """SELECT vehicle_number "Vehicle No", vehicle_model "Model",
                  fleet_status "Status", current_odometer_km "Odometer(km)",
                  monthly_rental_amount "Rental ₹",
                  last_service_date::text "Last Service",
                  next_service_due_date::text "Next Due"
           FROM rental_fleet WHERE 1=1"""
    if sf   != "All": q += " AND fleet_status = :sf"
    if mf   != "All": q += " AND vehicle_model = :mf"
    if srch:          q += " AND vehicle_number ILIKE :srch"
    q += " ORDER BY vehicle_number LIMIT 100"

    data = run_query(q, {"sf": sf, "mf": mf, "srch": f"%{srch}%"})
    st.markdown(f"**Showing {len(data)} vehicles**")
    if not data.empty:
        show_table(data)
    else:
        st.info("No vehicles found")

# ════════════════════════════════════════════════════════════════════
# JOB CARDS
# ════════════════════════════════════════════════════════════════════
def show_jobs():
    st.markdown("## 🔧 Job Cards")
    if is_tsm():
        st.markdown(f"Job cards of your clients — **{st.session_state.zone} Zone**")
    else:
        st.markdown("B2B and Rental job cards from the technicians' Google Forms")

    # ── keep in step with the Google Form (auto every 10 min, or on demand) ──
    eng = get_engine()
    last, age = jobcards.last_sync(eng)
    bg = background_sync()
    s1, s2 = st.columns([4, 1])
    if not jobcards.google_enabled():
        s1.caption("🧪 Demo mode — sample job cards (Google Form sync is off: no sheet_id in secrets)")
    elif s2.button("🔄 Sync now", width='stretch', key="jc_sync", disabled=bg["lock"].locked()):
        with st.spinner("Fetching new job cards from the Google Form…"):
            try:
                with bg["lock"]:
                    added, _, _ = jobcards.sync_all(eng)
                st.toast(f"✅ {added} new job card(s) from the form" if added else "✅ Up to date")
            except Exception as e:
                st.warning(f"⚠️ Google Form sync failed: {e}")
        last, age = jobcards.last_sync(eng)
    elif last is None or age > 600:
        start_background_sync(eng)               # page opens at once; new job cards show on the next refresh
    note = " · 🔄 checking the form for new job cards…" if bg["lock"].locked() else ""
    if jobcards.google_enabled():
        s1.caption((f"Last synced from the Google Form: {pd.Timestamp(last):%d-%b %I:%M %p} IST" if last
                    else "Not synced yet") + note)
    if bg.get("error"):
        st.warning(f"⚠️ Last automatic sync failed: {bg['error']}")
    st.markdown("---")

    # TSM sees only job cards of the clients mapped to them; job cards of an inactive
    # client (e.g. a contract that ended) are hidden — unmapped ones stay visible to managers
    scope = "WHERE COALESCE(cl.is_active, TRUE)" + (" AND cl.tsm_user_id = :uid" if is_tsm() else "")
    jobs = run_query(f"""
        SELECT f.id, f.job_type, f.job_card_no, f.job_open_date, f.client_name, f.client_location,
               f.client_location_id, cl.zone, u.username AS tsm, f.service_type, f.chassis_number,
               f.odo_km, f.technician, f.field_observation, f.form_job_status, f.completion_date,
               f.form, f.tsm_job_status, f.complaint_category, f.tsm_observation, f.repeat_complaints,
               f.action_date, f.rca, f.spares_cost, f.labor_cost, f.warranty_status,
               f.warranty_spares_cost, f.warranty_labor_cost, f.excel_pending, f.excel_error, f.unpriced_parts
        FROM form_job_cards f
        LEFT JOIN client_locations cl ON cl.location_id = f.client_location_id
        LEFT JOIN users u ON u.user_id = cl.tsm_user_id
        {scope}
        ORDER BY f.submitted_at DESC
    """, {"uid": st.session_state.user_id})
    if jobs.empty:
        st.info("No job cards for your clients yet.")
        return
    text_cols = ["job_type", "job_card_no", "client_name", "client_location", "zone", "tsm", "service_type",
                 "chassis_number", "odo_km", "technician", "field_observation", "form_job_status",
                 "tsm_job_status", "complaint_category", "tsm_observation", "repeat_complaints", "rca",
                 "warranty_status", "excel_error", "unpriced_parts"]
    jobs[text_cols] = jobs[text_cols].astype(object).where(jobs[text_cols].notna(), "")   # pandas 3: NaN → ""
    jobs["closed"] = jobs["tsm_job_status"].map(is_job_closed)

    if not is_tsm():
        unmapped = jobs[jobs["client_location_id"].isna()]
        if not unmapped.empty:
            names = (unmapped["client_name"].fillna("?") + " – " + unmapped["client_location"].fillna("all")
                     ).value_counts()
            st.warning("⚠️ **{} job cards have no TSM** — add these in 👥 Users → Clients & Zones: {}".format(
                len(unmapped), ", ".join(f"{k} ({v})" for k, v in names.items())))
        pend = jobs[jobs["excel_pending"]]
        if not pend.empty:
            w1, w2 = st.columns([4, 1])
            err = next((e for e in pend["excel_error"] if e), "they are written on the next sync")
            w1.warning(f"⏳ {len(pend)} job card update(s) not yet in Excel — {err}")
            if w2.button("Retry Excel", width='stretch', key="jc_retry"):
                with st.spinner("Writing to Excel…"):
                    jobcards.push_pending(eng)
                st.rerun()

    # one tab per job card type the user has (a TSM without rental sees only B2B)
    types = [t for t in ("Rental", "B2B") if (jobs["job_type"] == t).any()]
    icons = {"Rental": "🛵 Rental Job Cards", "B2B": "🏢 B2B Job Cards"}
    show_save_message()
    tabs = st.tabs([icons[t] for t in types])
    for t, tab in zip(types, tabs):
        with tab:
            show_job_list(jobs[jobs["job_type"] == t], t)


@st.cache_resource
def background_sync():
    """Shared by every session of this server: one sync at a time."""
    return {"lock": threading.Lock(), "error": None}


def start_background_sync(eng):
    bg = background_sync()
    if bg["lock"].locked():
        return

    def run():
        if not bg["lock"].acquire(blocking=False):
            return
        try:
            jobcards.sync_all(eng)
            bg["error"] = None
        except Exception as e:
            bg["error"] = str(e)[:200]
        finally:
            bg["lock"].release()
    threading.Thread(target=run, daemon=True).start()


def is_job_closed(s):
    """Same rule as the daily report: resolved / closed / completed … but not 'not / pending'."""
    s = str(s or "").lower()
    return bool(re.search(r"resolv|clos|complet|done|deliver", s)) and not re.search(r"not|pending|waiting", s)


def show_job_list(jobs, jt):
    """One job card type (Rental or B2B); widget keys carry the type so both tabs work side by side.
    Click ⓘ on a row to open that job card and update it."""
    k = f"_{jt}"
    if jt == "B2B":
        f1, f2, f3 = st.columns([1, 1.4, 2])
        clients = sorted(c for c in jobs["client_name"].unique() if c)
        client = f2.selectbox("Client", ["All"] + clients, key="jl_client" + k)
    else:
        f1, f3 = st.columns([1, 3.4])
        client = "All"
    status = f1.selectbox("TSM status", ["Open", "Closed", "All"], key="jl_status" + k)
    search = f3.text_input("🔍 Job card / chassis / technician", key="jl_search" + k).strip().lower()

    v = jobs
    if client != "All":
        v = v[v["client_name"] == client]
    if search:
        hay = (v["job_card_no"] + " " + v["chassis_number"] + " " + v["technician"]).str.lower()
        v = v[hay.str.contains(search, regex=False)]

    money = lambda s: pd.to_numeric(s, errors="coerce").fillna(0)
    recovery = v["service_type"].str.lower() == "recovery vehicle"
    # counters cover open + closed; the table then follows the status filter
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Job cards", len(v))
    m2.metric("Open", int((~v["closed"]).sum()))
    m3.metric("Closed", int(v["closed"].sum()))
    if jt == "Rental":
        used = money(v.loc[~recovery, "spares_cost"]).sum() + money(v.loc[~recovery, "labor_cost"]).sum()
        m4.metric("Fleet value used", f"₹{used:,.0f}", help="Spares at BM landing cost + labour (not invoiced)")
    else:
        m4.metric("Revenue (spares + labour)", f"₹{money(v['spares_cost']).sum() + money(v['labor_cost']).sum():,.0f}")

    if jt == "Rental":
        t_list, t_veh, t_tech = st.tabs(["📋 Job cards", "🛵 Value by vehicle", "🧑‍🔧 Value by technician"])
        with t_veh:
            show_rental_value(v, "chassis_number", "Vehicle (chassis)")
        with t_tech:
            show_rental_value(v, "technician", "Technician")
    else:
        t_list = st.container()

    with t_list:
        if status != "All":
            v = v[v["closed"] == (status == "Closed")]
        if v.empty:
            st.info("No job cards match these filters.")
            return
        all_cols = st.toggle("📄 Show every form column", key="jl_allcols" + k,
                             help="All answers exactly as in the Google Form / Excel sheet")
        out = job_list_columns(v, jt, all_cols)
        st.caption("Click **ⓘ** (last column) to open a job card and update it.")
        clicked = show_info_table(out, v["id"], key="jl_tbl" + k)
        if clicked is not None:
            edit_job_dialog(v[v["id"] == clicked].iloc[0])
        download_excel(out, f"{jt}_Job_Cards")


def job_list_columns(v, jt, all_cols):
    forms = [f if isinstance(f, dict) else {} for f in v["form"]]
    if all_cols:
        # every form answer + the team's columns, like the Excel sheet
        out = pd.DataFrame(forms, index=v.index).dropna(axis=1, how="all")
        out = out[jobcards.form_columns([jt], set(out.columns))]
        return out.assign(**{
            "TSM": v["tsm"], "TSM - Job Status": v["tsm_job_status"], "Complaint Category": v["complaint_category"],
            "TSM Observation": v["tsm_observation"], "RCA": v["rca"],
            "Action Date": pd.to_datetime(v["action_date"]).dt.strftime("%d-%b-%y"),
            "Spares ₹": v["spares_cost"], "Labour ₹": v["labor_cost"],
            "Warranty Spares ₹": v["warranty_spares_cost"], "Warranty Labour ₹": v["warranty_labor_cost"]})

    def answers(names):
        return [", ".join(str(f[n]) for n in names if f.get(n)) for f in forms]
    out = pd.DataFrame({
        "Job Card": v["job_card_no"],
        "Open Date": pd.to_datetime(v["job_open_date"]).dt.strftime("%d-%b-%y"),
        "Client": v["client_name"], "Location": v["client_location"], "TSM": v["tsm"],
        "Service Type": v["service_type"],
        "General Service": answers(["General Service", "General Service Type"]),
        "Chassis": v["chassis_number"], "KM": v["odo_km"], "Technician": v["technician"],
        "Field Observation": v["field_observation"],
        "Spares Replaced / Consumed": answers(["Paid Replaced Spares", "Paid - Replaced Spares",
                                               "Consumed Spares on General Service", "Consumed Spares Lists",
                                               "Non - Warranty Parts Replaced"]),
        "Warranty Parts": answers(["Warranty Parts Replaced"]),
        "Damaged / Missing (Recovery)": answers(["List Out The Damaged Components",
                                                 "List Out The Missing Components"]),
        "Form Status": v["form_job_status"],
        "TSM Status": v["tsm_job_status"], "Category": v["complaint_category"],
        "TSM Observation": v["tsm_observation"],
        "Action Date": pd.to_datetime(v["action_date"]).dt.strftime("%d-%b-%y"),
        ("Spares ₹ (landing)" if jt == "Rental" else "Spares ₹"): pd.to_numeric(v["spares_cost"], errors="coerce"),
        "Labour ₹": pd.to_numeric(v["labor_cost"], errors="coerce"),
        "Warranty ₹": pd.to_numeric(v["warranty_spares_cost"], errors="coerce") +
                      pd.to_numeric(v["warranty_labor_cost"], errors="coerce"),
    }, index=v.index)
    if jt == "Rental":
        out = out.drop(columns=["Client", "Location", "TSM"])          # always FleetCo Rental Fleet
    keep = [c for c in out.columns
            if out[c].astype(str).str.strip().replace({"nan": "", "None": "", "NaT": ""}).ne("").any()
            or c in ("TSM Status", "TSM Observation")]                   # hide columns empty for this filter
    return out[keep]


def show_rental_value(v, by, label):
    """What the rental fleet consumed (not invoiced): spares at landing cost + labour, per vehicle / technician."""
    if v.empty:
        st.info("No job cards match these filters.")
        return
    money = lambda s: pd.to_numeric(s, errors="coerce").fillna(0)
    rec = v["service_type"].str.lower() == "recovery vehicle"
    d = pd.DataFrame({
        label: v[by].replace("", "—"),
        "spares": money(v["spares_cost"]).where(~rec, 0),
        "labour": money(v["labor_cost"]).where(~rec, 0),
        "loss": money(v["spares_cost"]).where(rec, 0),
        "date": pd.to_datetime(v["job_open_date"]),
    })
    g = d.groupby(label).agg(**{
        "Job cards": ("spares", "size"), "Spares ₹ (landing)": ("spares", "sum"), "Labour ₹": ("labour", "sum"),
        "Recovery loss ₹": ("loss", "sum"), "Last job card": ("date", "max")}).reset_index()
    g["Total value ₹"] = g["Spares ₹ (landing)"] + g["Labour ₹"]
    g = g.sort_values("Total value ₹", ascending=False)
    g["Last job card"] = g["Last job card"].dt.strftime("%d-%b-%y")
    g = g[[label, "Job cards", "Spares ₹ (landing)", "Labour ₹", "Total value ₹", "Recovery loss ₹", "Last job card"]]
    if not g["Recovery loss ₹"].any():
        g = g.drop(columns="Recovery loss ₹")
    st.caption("Rental is not invoiced — this is the value of spares (BM landing cost) and labour used. "
               "Recovery loss is shown separately.")
    show_table(g.round(2), height=480)
    download_excel(g, f"Rental_Value_by_{by}")


TSM_STATUSES = ["OPEN", "CLOSED"]
CATEGORIES = ["", "LOW", "MEDIUM", "HIGH"]


@st.dialog("📝 Job card — TSM update", width="large")
def edit_job_dialog(job):
    show_job_editor(job)


def show_save_message():
    if "ju_msg" in st.session_state:
        xl_ok, no, msg = st.session_state.pop("ju_msg")
        if xl_ok:
            st.success(f"✅ {no} saved in the portal and Excel ({msg})")
        else:
            st.warning(f"⏳ {no} saved in the portal — Excel not updated yet: {msg}")


def show_job_editor(job):
    """TSM status / observation (+ optional fields) → saved in the portal and written to Excel at once.
    A TSM only ever gets their own clients' job cards here."""
    jid = int(job.id)
    form = job.form if isinstance(job.form, dict) else {}
    order = jobcards.form_columns([job.job_type], set(form))
    details = [(c, form[c]) for c in order
               if form.get(c) and c.lower() not in ("timestamp", "job card no", "chassis number")]
    rows = "".join(
        f"<tr><td style='color:#64748B;padding:2px 12px 2px 0;vertical-align:top;white-space:nowrap'>{html.escape(c)}</td>"
        f"<td style='padding:2px 0'>{link_or_text(val)}</td></tr>" for c, val in details)
    st.markdown(f"""
    <div style="background:#EFF6FF; border:1px solid #BFDBFE; border-radius:10px; padding:12px 16px; margin:0 0 14px;">
        <b style="color:#1B3A6B;">{html.escape(job.job_type)} · {html.escape(job.job_card_no)}</b> &nbsp;·&nbsp;
        {html.escape(job.chassis_number or "")} &nbsp;·&nbsp; TSM: {html.escape(job.tsm or "not mapped")}
        <table style="font-size:13px; margin-top:8px;">{rows}</table>
    </div>""", unsafe_allow_html=True)
    tk = run_query("""SELECT ticket_no, store, complaint_type, description, status, customer_remark
                      FROM dealer_tickets WHERE job_card_id = :i""", {"i": jid})
    if not tk.empty:
        r = tk.iloc[0]
        st.info(f"🎫 **Dealer complaint {r.ticket_no}** ({STATUS_BADGE.get(r.status, r.status)}) · {r.store} · "
                f"{r.complaint_type}: {r.description}\n\nClosing this job card resolves the ticket — "
                "the dealer sees it in their portal.")

    k = f"_{jid}"
    cur_status = (job.tsm_job_status or "").strip()
    st_opts = TSM_STATUSES + ([cur_status] if cur_status and cur_status.upper() not in TSM_STATUSES else [])
    # ── the TSM fills only these two ──
    status = st.selectbox("TSM - Job Status", st_opts,
                          index=st_opts.index(cur_status.upper() if cur_status.upper() in TSM_STATUSES else cur_status)
                          if cur_status else 0, key="ju_status" + k)
    obs = st.text_area("TSM Observation", value=job.tsm_observation or "", height=90, key="ju_obs" + k)

    with st.expander("More fields (optional) — category, action date, RCA"):
        c1, c2 = st.columns(2)
        cat_now = (job.complaint_category or "").strip().upper()
        cat_opts = CATEGORIES + ([cat_now] if cat_now not in CATEGORIES else [])
        category = c1.selectbox("Complaint Category", cat_opts, index=cat_opts.index(cat_now), key="ju_cat" + k)
        action = c2.date_input("Action Date (auto = today when closed)",
                               value=pd.to_datetime(job.action_date).date() if pd.notna(job.action_date) else None,
                               format="DD-MM-YYYY", key="ju_action" + k)
        r1, r2, r3 = st.columns(3)
        rca = r1.text_input("RCA (root cause)", value=job.rca or "", key="ju_rca" + k)
        repeat = r2.text_input("Repeat Complaints", value=job.repeat_complaints or "", key="ju_rep" + k,
                               disabled=job.job_type != "B2B")
        w_status = r3.text_input("Warranty Status", value=job.warranty_status or "", key="ju_ws" + k)

    show_job_costs(job)
    show_job_stock(jid)

    if st.button("💾 Save (portal + Excel)", width='stretch', type="primary", key="ju_save" + k):
        closing = is_job_closed(status)
        if closing and not obs.strip():
            st.warning("⚠️ Please write the TSM observation before closing the job card.")
            return
        if closing and action is None:
            action = pd.Timestamp.now().date()
        # the tsm clause stops a TSM updating another zone's job card
        ok = run_insert("""
            UPDATE form_job_cards
            SET tsm_job_status=%s, complaint_category=%s, tsm_observation=%s, repeat_complaints=%s,
                action_date=%s, rca=%s, warranty_status=%s,
                updated_by=%s, updated_at=NOW(), excel_pending=TRUE
            WHERE id=%s
              AND (NOT %s OR client_location_id IN
                   (SELECT location_id FROM client_locations WHERE tsm_user_id = %s))
        """, (status or None, category or None, obs.strip() or None, repeat.strip() or None,
              action, rca.strip() or None, w_status.strip() or None,
              st.session_state.user_id, jid, is_tsm(), st.session_state.user_id))
        if not ok:
            return
        audit("UPDATE", "form_job_cards", jid, f"{job.job_type} {job.job_card_no}: TSM status → {status}")
        with st.spinner("Writing to Excel…"):
            xl_ok, msg = jobcards.push_to_excel(get_engine(), jid)
        try:
            jobcards.link_tickets(get_engine())     # closed job card → its dealer ticket is resolved
        except Exception:
            pass
        st.session_state.ju_msg = (xl_ok, job.job_card_no, msg)
        st.rerun()                                   # closes the window, list shows the new values


def show_job_costs(job):
    """Costs are calculated from the parts in the form + the Price Master — read-only here."""
    form = job.form if isinstance(job.form, dict) else {}
    lines = jobcards.cost_lines(job.job_type, job.service_type, form, jobcards.load_prices(get_engine()))
    num = lambda v: float(v) if pd.notna(v) else 0.0
    recovery = job.job_type == "Rental" and job.service_type.lower() == "recovery vehicle"
    st.markdown("**💰 Costs — calculated automatically from the parts in the form (Price Master)**")
    m = st.columns(4)
    m[0].metric("Recovery loss ₹" if recovery else "Spares ₹ (landing)" if job.job_type == "Rental" else "Spares ₹",
                f"{num(job.spares_cost):,.2f}")
    m[1].metric("Labour ₹", f"{num(job.labor_cost):,.2f}")
    m[2].metric("Warranty Spares ₹", f"{num(job.warranty_spares_cost):,.2f}")
    m[3].metric("Warranty Labour ₹", f"{num(job.warranty_labor_cost):,.2f}")
    if lines:
        show_table(pd.DataFrame([{"For": g, "Part": p, "Spare ₹": round(s, 2), "Labour ₹": round(l, 2),
                                  "Price Master": "✅" if ok else "₹0 (not in list)"}
                                 for g, p, s, l, ok in lines]), height=min(60 + 38 * len(lines), 320))
    else:
        st.caption("No chargeable parts in this job card.")


def link_or_text(v):
    """Form answers: Google Drive links become clickable."""
    parts = []
    for p in str(v).split(", "):
        if p.startswith("http"):
            parts.append(f"<a href='{html.escape(p)}' target='_blank'>📎 photo/file</a>")
        else:
            parts.append(html.escape(p))
    return ", ".join(parts)


def audit(action, table, record_id, description):
    """Write one line to audit_log (who did what, when)."""
    run_insert("""INSERT INTO audit_log (user_id, action, table_name, record_id, description)
                  VALUES (%s,%s,%s,%s,%s)""",
               (st.session_state.user_id, action, table, record_id, description))

# ════════════════════════════════════════════════════════════════════
# DEALER PORTAL (customer logins, e.g. QuickBite) + TICKETS
# ════════════════════════════════════════════════════════════════════
# SECURITY: everything a dealer sees goes through dealer_where() — their client
# (and store) come from the database at login, never from the page.
TICKET_STATUSES = ["OPEN", "IN PROGRESS", "RESOLVED"]
COMPLAINT_TYPES = ["Vehicle not starting / breakdown", "Battery / charging", "Brakes", "Tyre / puncture",
                   "Electrical / lights / horn", "Motor / controller / pickup", "Body / accident damage",
                   "General service due", "Other"]
TSM_TICKET_SCOPE = "t.client_location_id IN (SELECT location_id FROM client_locations WHERE tsm_user_id = :uid)"
STATUS_BADGE = {"OPEN": "🔴 Open", "IN PROGRESS": "🟠 In progress", "RESOLVED": "🟢 Resolved"}
IST_NOW = jobcards.IST_NOW


def _norm(expr):
    """Compare store names ignoring case and extra spaces."""
    return f"LOWER(REGEXP_REPLACE(TRIM({expr}), '\\s+', ' ', 'g'))"


def dealer_where(alias, store_col, own_vehicles=False):
    """SQL condition + params keeping a dealer inside their own client (and store).
    own_vehicles: a store also sees job cards of the vehicles assigned to it, whatever store the technician wrote."""
    sql = f"LOWER({alias}.client_name) = LOWER(:d_client)"
    params = {"d_client": st.session_state.dealer_client}
    if st.session_state.dealer_store:
        same_store = f"{_norm(f'{alias}.{store_col}')} = {_norm(':d_store')}"
        if own_vehicles:
            same_store = f"""({same_store} OR UPPER(REPLACE({alias}.chassis_number, ' ', '')) IN
                (SELECT v.chassis_number FROM dealer_vehicles v WHERE v.is_active
                   AND LOWER(v.client_name) = LOWER(:d_client) AND {_norm('v.store')} = {_norm(':d_store')}))"""
        sql += f" AND {same_store}"
        params["d_store"] = st.session_state.dealer_store
    return sql, params


def store_vehicles(client, store=None):
    """Active vehicles assigned to a client's store (all stores if store is None): DataFrame chassis_number, store."""
    sql = """SELECT chassis_number, COALESCE(store, '') AS store FROM dealer_vehicles
             WHERE is_active AND LOWER(client_name) = LOWER(:c)"""
    if store:
        sql += f" AND {_norm('store')} = {_norm(':s')}"
    return run_query(sql + " ORDER BY chassis_number", {"c": client, "s": store})


def now_ist():
    return pd.Timestamp.now(tz="Asia/Kolkata").tz_localize(None)


def money_col(s):
    return pd.to_numeric(s, errors="coerce").fillna(0)


def fmt_date(s):
    return pd.to_datetime(s).dt.strftime("%d-%b-%y").fillna("")


def client_stores(client):
    """Store / location names of a client: from its job cards + its vehicle list (a new store has no job cards yet)."""
    r = run_query("""SELECT REGEXP_REPLACE(TRIM(client_location), '\\s+', ' ', 'g') AS s
                     FROM form_job_cards
                     WHERE job_type = 'B2B' AND LOWER(client_name) = LOWER(:c) AND COALESCE(client_location, '') <> ''
                     UNION
                     SELECT REGEXP_REPLACE(TRIM(store), '\\s+', ' ', 'g') FROM dealer_vehicles
                     WHERE LOWER(client_name) = LOWER(:c) AND COALESCE(store, '') <> ''
                     ORDER BY 1""", {"c": client})
    return r["s"].tolist() if not r.empty else []


# ── data the dealer may see ──
def dealer_job_cards():
    """The dealer's B2B job cards with customer-facing columns only (customer price — never landing cost)."""
    w, p = dealer_where("f", "client_location", own_vehicles=True)
    jobs = run_query(f"""
        SELECT f.id, f.job_card_no, f.job_open_date, f.submitted_at, f.client_location AS store, f.chassis_number,
               f.odo_km, f.service_type, f.technician, f.form_job_status, f.tsm_job_status, f.completion_date,
               f.action_date, f.spares_cost, f.labor_cost, f.form, t.ticket_no, t.customer_remark
        FROM form_job_cards f
        LEFT JOIN dealer_tickets t ON t.job_card_id = f.id
        WHERE f.job_type = 'B2B' AND {w}
        ORDER BY f.submitted_at DESC""", p)
    if jobs.empty:
        return jobs
    txt = ["job_card_no", "store", "chassis_number", "odo_km", "service_type", "technician", "form_job_status",
           "tsm_job_status", "ticket_no", "customer_remark"]
    jobs[txt] = jobs[txt].astype(object).where(jobs[txt].notna(), "")
    jobs["closed"] = jobs["tsm_job_status"].map(is_job_closed)
    jobs["status"] = jobs["closed"].map({True: "✅ Completed", False: "🔧 Open"})
    jobs["closed_on"] = pd.to_datetime(jobs["action_date"]).fillna(pd.to_datetime(jobs["completion_date"]))
    jobs["spares"] = money_col(jobs["spares_cost"])
    jobs["labour"] = money_col(jobs["labor_cost"])
    jobs["total"] = jobs["spares"] + jobs["labour"]
    jobs["date"] = pd.to_datetime(jobs["job_open_date"])
    return jobs


def dealer_tickets_df(ticket_id=None):
    """Tickets the current user may see: dealer → own client/store, TSM → own clients, others → all.
    internal_note is only selected for the FleetCo team."""
    params = {"uid": st.session_state.user_id}
    if is_dealer():
        where, p = dealer_where("t", "store")
        params.update(p)
    elif is_tsm():
        where = TSM_TICKET_SCOPE
    else:
        where = "TRUE"
    if ticket_id is not None:
        where += " AND t.id = :tid"
        params["tid"] = int(ticket_id)
    note = "NULL" if is_dealer() else "t.internal_note"
    df = run_query(f"""
        SELECT t.id, t.ticket_no, t.client_name, t.store, t.chassis_number, t.complaint_type, t.description,
               t.contact, t.photo_path, t.status, t.job_card_id, t.link_method, t.customer_remark,
               {note} AS internal_note, t.raised_at, t.resolved_at, t.updated_at,
               ru.full_name AS raised_by, f.job_card_no, f.tsm_job_status, tu.full_name AS tsm
        FROM dealer_tickets t
        LEFT JOIN users ru ON ru.user_id = t.raised_by
        LEFT JOIN form_job_cards f ON f.id = t.job_card_id
        LEFT JOIN client_locations cl ON cl.location_id = t.client_location_id
        LEFT JOIN users tu ON tu.user_id = cl.tsm_user_id
        WHERE {where}
        ORDER BY t.raised_at DESC""", params)
    if not df.empty:
        txt = ["store", "chassis_number", "complaint_type", "description", "contact", "photo_path",
               "customer_remark", "internal_note", "raised_by", "job_card_no", "tsm", "link_method"]
        df[txt] = df[txt].astype(object).where(df[txt].notna(), "")
        end = pd.to_datetime(df["resolved_at"]).fillna(now_ist())
        df["days"] = ((end - pd.to_datetime(df["raised_at"])).dt.total_seconds() / 86400).round(1)
    return df


@st.cache_data(ttl=3600, show_spinner=False)
def ticket_photo(path):
    try:
        return jobcards.download_photo(path)
    except Exception:
        return None


# ── 🏠 Overview (dealer dashboard) ──
def show_overview():
    import plotly.express as px
    client = st.session_state.dealer_client
    st.markdown(f"## 🏠 {html.escape(client)} — Service Overview")
    st.markdown(f"{html.escape(st.session_state.dealer_store or 'All stores')} · vehicles serviced by FleetCo")

    jobs, tickets = dealer_job_cards(), dealer_tickets_df()
    now = now_ist()
    month0 = now.normalize().replace(day=1)
    open_t = tickets[tickets["status"] != "RESOLVED"] if not tickets.empty else tickets
    done90 = tickets[(tickets["status"] == "RESOLVED") &
                     (pd.to_datetime(tickets["resolved_at"]) >= now - pd.Timedelta(days=90))] if not tickets.empty else tickets
    jm = jobs[jobs["date"] >= month0] if not jobs.empty else jobs

    k = st.columns(5)
    k[0].metric("Open complaints", len(open_t))
    k[1].metric("Resolved this month", 0 if tickets.empty else
                int(((tickets["status"] == "RESOLVED") & (pd.to_datetime(tickets["resolved_at"]) >= month0)).sum()))
    k[2].metric("Avg. resolution", f"{done90['days'].mean():.1f} days" if not done90.empty else "—",
                help="Complaints resolved in the last 90 days")
    k[3].metric("Job cards this month", len(jm))
    k[4].metric("Service cost this month", f"₹{jm['total'].sum():,.0f}" if not jm.empty else "₹0",
                help="Spares + labour (customer price)")

    if not open_t.empty:
        st.markdown("#### 🔴 Open complaints")
        show_table(pd.DataFrame({
            "Ticket": open_t["ticket_no"], "Raised": pd.to_datetime(open_t["raised_at"]).dt.strftime("%d-%b %I:%M %p"),
            "Store": open_t["store"], "Vehicle": open_t["chassis_number"], "Complaint": open_t["complaint_type"],
            "Status": open_t["status"].map(STATUS_BADGE), "Job card": open_t["job_card_no"],
            "Days open": open_t["days"]}), height=260)

    if jobs.empty:
        st.info("No service history yet.")
        return
    c1, c2 = st.columns(2)
    last12 = jobs[jobs["date"] >= month0 - pd.DateOffset(months=11)]
    monthly = (last12.assign(Month=last12["date"].dt.to_period("M").dt.to_timestamp())
               .groupby("Month").agg(job_cards=("id", "size"), cost=("total", "sum")).reset_index())
    with c1:
        fig = px.bar(monthly, x="Month", y="job_cards", title="Job cards per month",
                     labels={"job_cards": "Job cards", "Month": ""}, color_discrete_sequence=[NAVY])
        fig.update_layout(height=320, margin=dict(l=10, r=10, t=50, b=10), xaxis_tickformat="%b %y")
        st.plotly_chart(fig, width='stretch')
    with c2:
        fig = px.bar(monthly, x="Month", y="cost", title="Service cost per month (₹)",
                     labels={"cost": "₹", "Month": ""}, color_discrete_sequence=[GREEN])
        fig.update_layout(height=320, margin=dict(l=10, r=10, t=50, b=10), xaxis_tickformat="%b %y")
        st.plotly_chart(fig, width='stretch')

    c3, c4 = st.columns(2)
    with c3:
        if st.session_state.dealer_store:
            by = jobs.assign(k=jobs["service_type"].replace("", "Other")).groupby("k").size()
            title = "Job cards by service type"
        else:
            by = jobs.groupby(jobs["store"].replace("", "—")).size()
            title = "Job cards by store"
        by = by.sort_values().tail(15).rename("n").reset_index()
        fig = px.bar(by, x="n", y=by.columns[0], orientation="h", title=title,
                     labels={"n": "Job cards", by.columns[0]: ""}, color_discrete_sequence=[NAVY])
        fig.update_layout(height=380, margin=dict(l=10, r=10, t=50, b=10))
        st.plotly_chart(fig, width='stretch')
    with c4:
        st.markdown("**🔁 Vehicles with repeat visits (last 90 days)**")
        r90 = jobs[jobs["date"] >= now - pd.Timedelta(days=90)]
        rep = (r90[r90["chassis_number"] != ""].groupby("chassis_number")
               .agg(Visits=("id", "size"), Store=("store", "last"), Last=("date", "max"), Cost=("total", "sum"))
               .reset_index().query("Visits >= 2").sort_values("Visits", ascending=False))
        if rep.empty:
            st.caption("No vehicle came in more than once in the last 90 days. 👍")
        else:
            rep["Last"] = rep["Last"].dt.strftime("%d-%b-%y")
            rep = rep.rename(columns={"chassis_number": "Vehicle", "Last": "Last visit", "Cost": "Cost ₹"})
            show_table(rep.round(0), height=330)


# ── ➕ Raise Complaint ──
def show_raise_complaint():
    st.markdown("## ➕ Raise a Complaint")
    st.markdown("Tell us what is wrong — the FleetCo service team gets it at once and updates you here.")
    st.markdown("---")
    done = st.session_state.pop("rc_done", None)
    if done:
        tno, others, photo_err = done
        st.success(f"✅ Complaint **{tno}** raised — the FleetCo service team has it. Follow it in 🎫 Tickets.")
        if others:
            st.info(f"ℹ️ This vehicle also has open complaint(s): {others}")
        if photo_err:
            st.warning(f"⚠️ The photo could not be saved ({photo_err}). The complaint itself is saved.")

    client = st.session_state.dealer_client
    n = st.session_state.setdefault("rc_n", 0)
    if st.session_state.dealer_store:
        store = st.session_state.dealer_store
    else:
        # head office: the store first (outside the form, so the vehicle list follows it)
        store = st.selectbox("Store *", client_stores(client), index=None, placeholder="Choose the store",
                             key=f"rc_store_{n}")
    # the store's own vehicles; until vehicles are assigned to a store, its service history + typing
    own = store_vehicles(client, store)["chassis_number"].tolist() if store else []
    if own:
        chassis_list, free = own, False
    else:
        hist = run_query(f"""SELECT DISTINCT UPPER(REPLACE(chassis_number, ' ', '')) AS c FROM form_job_cards
                             WHERE job_type = 'B2B' AND LOWER(client_name) = LOWER(:c) AND COALESCE(chassis_number, '') <> ''
                               AND {_norm('client_location')} = {_norm(':s')} ORDER BY 1""", {"c": client, "s": store or ""})
        chassis_list, free = (hist["c"].tolist() if not hist.empty else []), True

    # the form keeps what was typed if something is missing; a new key clears it after a successful submit
    with st.form(f"rc_form_{n}"):
        c1, c2 = st.columns(2)
        c1.text_input("Store", value=store or "— choose the store above —", disabled=True, key=f"rc_store_fixed_{n}")
        chassis = c2.selectbox("Vehicle chassis number *", chassis_list, index=None,
                               placeholder=(f"Choose one of your {len(own)} vehicles" if own
                                            else "Choose or type the chassis number"),
                               accept_new_options=free, key=f"rc_chassis_{n}_{store}")
        c3, c4 = st.columns(2)
        ctype = c3.selectbox("Complaint type *", COMPLAINT_TYPES, index=None, placeholder="Choose", key=f"rc_type_{n}")
        contact = c4.text_input("Contact person & phone at the store", max_chars=100, key=f"rc_contact_{n}")
        desc = st.text_area("Describe the problem *", height=110, max_chars=1500, key=f"rc_desc_{n}")
        photo = st.file_uploader("Photo (optional, max 10 MB)", type=["jpg", "jpeg", "png"], key=f"rc_photo_{n}")
        sent = st.form_submit_button("📨 Raise complaint", width='stretch')
    if own:
        st.caption(f"🛵 Showing the {len(own)} vehicles assigned to this store. "
                   "A vehicle missing? Call the FleetCo service team to add it.")

    if not sent:
        return
    chassis = (chassis or "").strip().upper()
    missing = [name for name, val in (("store", store), ("chassis number", chassis), ("complaint type", ctype),
                                      ("description", desc.strip())) if not val]
    if missing:
        st.warning(f"⚠️ Please fill: {', '.join(missing)}.")
        return
    if photo is not None and photo.size > 10 * 1024 * 1024:
        st.warning("⚠️ The photo is larger than 10 MB — please choose a smaller one.")
        return
    dup = run_query("""SELECT ticket_no FROM dealer_tickets
                       WHERE LOWER(client_name) = LOWER(:c) AND status <> 'RESOLVED'
                         AND UPPER(REPLACE(chassis_number, ' ', '')) = UPPER(REPLACE(:ch, ' ', ''))""",
                    {"c": client, "ch": chassis})

    from sqlalchemy import text
    eng = get_engine()
    with eng.begin() as c:
        locs = [dict(r._mapping) for r in c.execute(text(
            "SELECT location_id, client_name, location, is_rental FROM client_locations WHERE is_active"))]
        row = c.execute(text("""
            INSERT INTO dealer_tickets (client_name, store, client_location_id, chassis_number, complaint_type,
                                        description, contact, raised_by)
            VALUES (:client, :store, :loc, :ch, :ct, :d, :contact, :uid)
            RETURNING id, ticket_no"""), {
            "client": client, "store": store.strip(), "loc": jobcards.map_location(locs, "B2B", client, store),
            "ch": chassis, "ct": ctype, "d": desc.strip(), "contact": contact.strip() or None,
            "uid": st.session_state.user_id}).first()
    tid, tno = row
    audit("CREATE", "dealer_tickets", tid, f"{tno} raised by {st.session_state.username}: {ctype} · {chassis}")

    photo_err = None
    if photo is not None:
        try:
            path = jobcards.upload_photo(f"{tno}.jpg", shrink_photo(photo.getvalue()))
            run_insert("UPDATE dealer_tickets SET photo_path=%s WHERE id=%s", (path, tid))
        except Exception as e:
            photo_err = str(e)[:150]
    try:
        jobcards.link_tickets(eng)          # the technician may already have filled the job card
    except Exception:
        pass
    st.session_state.rc_done = (tno, ", ".join(dup["ticket_no"]) if not dup.empty else "", photo_err)
    st.session_state.rc_n = n + 1                   # fresh, empty form
    st.rerun()


def show_my_vehicles():
    """The vehicles assigned to the dealer's store(s): open complaints, last service, visits and cost per vehicle."""
    st.markdown("## 🛵 My Vehicles")
    st.markdown("The vehicles FleetCo has assigned to " +
                (f"**{html.escape(st.session_state.dealer_store)}**" if st.session_state.dealer_store else "your stores"))
    st.markdown("---")
    veh = store_vehicles(st.session_state.dealer_client, st.session_state.dealer_store or None)
    if veh.empty:
        st.info("No vehicles are assigned to your store yet. Please ask the FleetCo service team.")
        return
    veh["store"] = veh["store"].replace("", "— not assigned —")
    jobs, tickets = dealer_job_cards(), dealer_tickets_df()
    now = now_ist()
    key = lambda s: s.astype(str).str.replace(" ", "").str.upper()
    rows = []
    jk = key(jobs["chassis_number"]) if not jobs.empty else pd.Series(dtype=str)
    tk = key(tickets["chassis_number"]) if not tickets.empty else pd.Series(dtype=str)
    for v in veh.itertuples():
        j = jobs[jk == v.chassis_number] if not jobs.empty else jobs
        t = tickets[(tk == v.chassis_number) & (tickets["status"] != "RESOLVED")] if not tickets.empty else tickets
        in_shop = (not j.empty) and (~j["closed"]).any()
        last = j["date"].max() if not j.empty else pd.NaT
        rows.append({
            "Vehicle": v.chassis_number, "Store": v.store,
            "Status": ("🔴 Complaint open" if not t.empty else "🔧 Job card open" if in_shop else "✅ Running"),
            "Open complaint": ", ".join(t["ticket_no"]) if not t.empty else "",
            "Last service": last.strftime("%d-%b-%y") if pd.notna(last) else "never",
            "Days since": int((now - last).days) if pd.notna(last) else None,
            "Visits (90 days)": int((j["date"] >= now - pd.Timedelta(days=90)).sum()) if not j.empty else 0,
            "Visits (all)": len(j),
            "Service cost ₹": round(float(j["total"].sum()), 2) if not j.empty else 0.0,
        })
    out = pd.DataFrame(rows)
    if st.session_state.dealer_store:
        out = out.drop(columns="Store")

    m = st.columns(4)
    m[0].metric("Vehicles", len(out))
    m[1].metric("Complaint open", int((out["Status"] == "🔴 Complaint open").sum()))
    m[2].metric("Job card open", int((out["Status"] == "🔧 Job card open").sum()))
    m[3].metric("Repeat visits (90 days)", int((out["Visits (90 days)"] >= 2).sum()),
                help="Vehicles that came in 2 or more times in the last 90 days")
    f1, f2 = st.columns([1, 2])
    flt = f1.selectbox("Show", ["All", "🔴 Complaint open", "🔧 Job card open", "✅ Running"], key="mv_status")
    search = f2.text_input("🔍 Chassis", key="mv_search").strip().upper().replace(" ", "")
    v = out
    if flt != "All":
        v = v[v["Status"] == flt]
    if search:
        v = v[v["Vehicle"].str.contains(search, regex=False)]
    order = {"🔴 Complaint open": 0, "🔧 Job card open": 1, "✅ Running": 2}
    v = v.sort_values(["Status", "Vehicle"], key=lambda s: s.map(order) if s.name == "Status" else s)
    show_table(v, height=520)
    download_excel(v, "My_Vehicles")
    st.caption("To report a problem with a vehicle, use ➕ Raise Complaint. Its full history is in 🧾 Service History.")


def shrink_photo(data, max_side=1600):
    """Phone photos are 3–8 MB — keep them sharp but small (and under OneDrive's 4 MB simple upload)."""
    import io
    from PIL import Image, ImageOps
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
    img.thumbnail((max_side, max_side))
    out = io.BytesIO()
    img.save(out, "JPEG", quality=80, optimize=True)
    return out.getvalue()


# ── 🎫 Tickets (dealer: follow up · FleetCo team: handle) ──
def show_tickets():
    st.markdown("## 🎫 Complaint Tickets")
    if is_dealer():
        st.markdown("Your complaints and what FleetCo is doing about them")
    elif is_tsm():
        st.markdown(f"Complaints raised by your clients' dealers — **{st.session_state.zone} Zone**")
    else:
        st.markdown("Complaints raised by dealers (customer logins)")
    st.markdown("---")
    msg = st.session_state.pop("tk_msg", None)
    if msg:
        (st.success if msg[0] else st.warning)(msg[1])

    t = dealer_tickets_df()
    if t.empty:
        st.info("No complaints raised yet." + (" Use ➕ Raise Complaint to raise one." if is_dealer() else ""))
        return

    f1, f2, f3 = st.columns([1, 1.4, 2])
    status = f1.selectbox("Status", ["Not resolved", "Resolved", "All"], key="tk_status")
    if is_dealer() and not st.session_state.dealer_store:
        stores = sorted(s for s in t["store"].unique() if s)
        store = f2.selectbox("Store", ["All"] + stores, key="tk_store")
    elif not is_dealer():
        clients = sorted(t["client_name"].unique())
        store = f2.selectbox("Client", ["All"] + clients, key="tk_client")
    else:
        store = "All"
    search = f3.text_input("🔍 Ticket / chassis / store", key="tk_search").strip().lower()

    m = st.columns(4)
    m[0].metric("Open", int((t["status"] == "OPEN").sum()))
    m[1].metric("In progress", int((t["status"] == "IN PROGRESS").sum()))
    m[2].metric("Resolved", int((t["status"] == "RESOLVED").sum()))
    res = t[t["status"] == "RESOLVED"]
    m[3].metric("Avg. resolution", f"{res['days'].mean():.1f} days" if not res.empty else "—")

    v = t
    if status != "All":
        v = v[(v["status"] == "RESOLVED") == (status == "Resolved")]
    if store != "All":
        v = v[(v["store"] if is_dealer() else v["client_name"]) == store]
    if search:
        hay = (v["ticket_no"] + " " + v["chassis_number"] + " " + v["store"]).str.lower()
        v = v[hay.str.contains(search, regex=False)]
    if v.empty:
        st.info("No tickets match these filters.")
        return

    out = pd.DataFrame({
        "Ticket": v["ticket_no"],
        "Raised": pd.to_datetime(v["raised_at"]).dt.strftime("%d-%b-%y %I:%M %p"),
        "Client": v["client_name"], "Store": v["store"], "Vehicle": v["chassis_number"],
        "Complaint": v["complaint_type"], "Status": v["status"].map(STATUS_BADGE),
        "Job card": v["job_card_no"], "FleetCo remark": v["customer_remark"],
        "Days": v["days"],
    }, index=v.index)
    if is_dealer():
        out = out.drop(columns=["Client"] + (["Store"] if st.session_state.dealer_store else []))
    else:
        out.insert(out.columns.get_loc("Status"), "TSM", v["tsm"])
    st.caption("Click **ⓘ** (last column) to " + ("see the details." if is_dealer() else "open and update a ticket."))
    clicked = show_info_table(out, v["id"], key="tk_tbl")
    if clicked is not None:
        ticket_dialog(clicked)
    download_excel(out, "Complaint_Tickets")


@st.dialog("🎫 Complaint ticket", width="large")
def ticket_dialog(ticket_id):
    t = dealer_tickets_df(ticket_id)          # re-read with the user's scope: a dealer can't open others' tickets
    if t.empty:
        st.error("This ticket is not available.")
        return
    t = t.iloc[0]
    rows = [("Store", t.store), ("Vehicle", t.chassis_number), ("Complaint", t.complaint_type),
            ("Description", t.description), ("Contact", t.contact), ("Raised by", t.raised_by),
            ("Raised on", pd.Timestamp(t.raised_at).strftime("%d-%b-%Y %I:%M %p")),
            ("FleetCo contact", t.tsm), ("Job card", t.job_card_no)]
    if t.status == "RESOLVED" and pd.notna(t.resolved_at):
        rows.append(("Resolved on", pd.Timestamp(t.resolved_at).strftime("%d-%b-%Y %I:%M %p")))
    body = "".join(f"<tr><td style='color:#64748B;padding:2px 12px 2px 0;vertical-align:top;white-space:nowrap'>{k}</td>"
                   f"<td style='padding:2px 0'>{html.escape(str(val))}</td></tr>" for k, val in rows if val)
    st.markdown(f"""
    <div style="background:#EFF6FF; border:1px solid #BFDBFE; border-radius:10px; padding:12px 16px; margin:0 0 14px;">
        <b style="color:#1B3A6B;">{html.escape(t.ticket_no)} · {html.escape(t.client_name)}</b> &nbsp;·&nbsp;
        {STATUS_BADGE.get(t.status, t.status)}
        <table style="font-size:13px; margin-top:8px;">{body}</table>
    </div>""", unsafe_allow_html=True)
    if t.customer_remark:
        st.info(f"**FleetCo remark:** {t.customer_remark}")
    if t.photo_path:
        img = ticket_photo(t.photo_path)
        if img:
            st.image(img, caption="Photo from the store", width=420)
        else:
            st.caption("📷 Photo saved, but it can't be shown right now.")

    if pd.notna(t.job_card_id):
        job = dealer_job_cards() if is_dealer() else None
        if is_dealer():
            job = job[job["id"] == int(t.job_card_id)]
            if not job.empty:
                show_dealer_job(job.iloc[0])
    if is_dealer():
        return
    show_ticket_editor(t)


def show_ticket_editor(t):
    """FleetCo team: status, remark for the dealer, internal note, link to the technician's job card.
    Resolving the ticket closes its job card (+ Excel) and closing the job card resolves the ticket."""
    k = f"_{int(t.id)}"
    st.markdown("---")
    st.markdown("**✏️ Update this ticket**")
    cands = run_query("""
        SELECT f.id, f.job_card_no, f.job_open_date, f.chassis_number, f.client_location, f.tsm_job_status
        FROM form_job_cards f
        WHERE f.job_type = 'B2B' AND LOWER(f.client_name) = LOWER(:c)
          AND (f.id = :cur OR (f.submitted_at >= :since
               AND NOT EXISTS (SELECT 1 FROM dealer_tickets x WHERE x.job_card_id = f.id)))
        ORDER BY (UPPER(REPLACE(f.chassis_number, ' ', '')) = UPPER(REPLACE(:ch, ' ', ''))) DESC, f.submitted_at DESC
        LIMIT 200""", {"c": t.client_name, "cur": int(t.job_card_id) if pd.notna(t.job_card_id) else -1,
                       "since": pd.Timestamp(t.raised_at) - pd.Timedelta(days=30), "ch": t.chassis_number})
    opts = {None: "— not linked yet —"}
    s = lambda v: "" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v).strip()   # pandas 3: NaN → ""
    for r in cands.itertuples():
        same = "✅ same vehicle · " if s(r.chassis_number).replace(" ", "").upper() == \
            t.chassis_number.replace(" ", "").upper() else ""
        opts[int(r.id)] = (f"{same}{r.job_card_no} · {pd.Timestamp(r.job_open_date):%d-%b} · "
                           f"{s(r.chassis_number) or '?'} · {s(r.client_location)} · {s(r.tsm_job_status) or 'open'}")
    cur_job = int(t.job_card_id) if pd.notna(t.job_card_id) else None
    c1, c2 = st.columns([1, 2])
    status = c1.selectbox("Status", TICKET_STATUSES, index=TICKET_STATUSES.index(t.status), key="tk_st" + k)
    job_id = c2.selectbox("Technician's job card", list(opts), format_func=opts.get,
                          index=list(opts).index(cur_job) if cur_job in opts else 0, key="tk_job" + k,
                          help="Linked automatically when the job card has the same chassis (or the Ticket No).")
    remark = st.text_area("Remark for the dealer (they see this)", value=t.customer_remark, height=70,
                          key="tk_rem" + k, max_chars=1000)
    note = st.text_area("Internal note (FleetCo team only)", value=t.internal_note, height=70, key="tk_note" + k)

    if not st.button("💾 Save ticket", width='stretch', type="primary", key="tk_save" + k):
        return
    if status == "RESOLVED" and not remark.strip():
        st.warning("⚠️ Write a remark for the dealer before resolving (what was done).")
        return
    if status == "OPEN" and job_id is not None:
        status = "IN PROGRESS"                         # a technician is on it
    method = t.link_method if job_id == cur_job else ("manual" if job_id else None)
    ok = run_insert(f"""
        UPDATE dealer_tickets
        SET status=%s, customer_remark=%s, internal_note=%s, job_card_id=%s, link_method=%s,
            resolved_at = CASE WHEN %s = 'RESOLVED' THEN COALESCE(resolved_at, {IST_NOW}) END,
            resolved_by = CASE WHEN %s = 'RESOLVED' THEN COALESCE(resolved_by, %s) END,
            updated_by=%s, updated_at={IST_NOW}
        WHERE id=%s
          AND (NOT %s OR client_location_id IN (SELECT location_id FROM client_locations WHERE tsm_user_id = %s))
    """, (status, remark.strip() or None, note.strip() or None, job_id, method, status, status,
          st.session_state.user_id, st.session_state.user_id, int(t.id), is_tsm(), st.session_state.user_id))
    if not ok:
        return
    audit("UPDATE", "dealer_tickets", int(t.id), f"{t.ticket_no}: status → {status}")

    msg = (True, f"✅ {t.ticket_no} saved.")
    if status == "RESOLVED" and job_id is not None:
        # resolving the complaint closes the technician's job card too (portal + Excel)
        job = run_query("SELECT tsm_job_status, job_card_no FROM form_job_cards WHERE id = :i", {"i": job_id})
        if not job.empty and not is_job_closed(job["tsm_job_status"].iloc[0]):
            run_insert("""
                UPDATE form_job_cards
                SET tsm_job_status='CLOSED', tsm_observation=COALESCE(NULLIF(TRIM(tsm_observation), ''), %s),
                    action_date=COALESCE(action_date, CURRENT_DATE), updated_by=%s, updated_at=NOW(), excel_pending=TRUE
                WHERE id=%s
                  AND (NOT %s OR client_location_id IN (SELECT location_id FROM client_locations WHERE tsm_user_id = %s))
            """, (note.strip() or remark.strip(), st.session_state.user_id, job_id, is_tsm(), st.session_state.user_id))
            no = job["job_card_no"].iloc[0]
            audit("UPDATE", "form_job_cards", job_id, f"B2B {no}: closed with ticket {t.ticket_no}")
            with st.spinner("Writing the job card to Excel…"):
                xl_ok, xl_msg = jobcards.push_to_excel(get_engine(), job_id)
            msg = (True, f"✅ {t.ticket_no} resolved and job card {no} closed (portal + Excel).") if xl_ok else \
                  (False, f"⏳ {t.ticket_no} resolved and job card {no} closed — Excel not updated yet: {xl_msg}")
    st.session_state.tk_msg = msg
    st.rerun()


# ── 🧾 Service History (dealer reports) ──
def show_service_history():
    st.markdown("## 🧾 Service History & Reports")
    st.markdown("Every job card FleetCo did on your vehicles — spares and labour at your price")
    st.markdown("---")
    jobs = dealer_job_cards()
    if jobs.empty:
        st.info("No service history yet.")
        return
    f1, f2, f3 = st.columns([1.3, 1.3, 2])
    first = jobs["date"].min().date()
    period = f1.date_input("Period", value=(max(first, (now_ist() - pd.DateOffset(months=6)).date()), now_ist().date()),
                           min_value=first, max_value=now_ist().date(), format="DD-MM-YYYY", key="sh_period")
    if not st.session_state.dealer_store:
        stores = sorted(s for s in jobs["store"].unique() if s)
        store = f2.selectbox("Store", ["All"] + stores, key="sh_store")
    else:
        store = "All"
        f2.text_input("Store", value=st.session_state.dealer_store, disabled=True, key="sh_store_fixed")
    search = f3.text_input("🔍 Job card / chassis", key="sh_search").strip().lower()

    v = jobs
    if isinstance(period, (list, tuple)) and len(period) == 2:
        v = v[(v["date"] >= pd.Timestamp(period[0])) & (v["date"] <= pd.Timestamp(period[1]))]
    if store != "All":
        v = v[v["store"] == store]
    if search:
        v = v[(v["job_card_no"] + " " + v["chassis_number"]).str.lower().str.contains(search, regex=False)]

    m = st.columns(4)
    m[0].metric("Job cards", len(v))
    m[1].metric("Vehicles", v.loc[v["chassis_number"] != "", "chassis_number"].nunique())
    m[2].metric("Spares ₹", f"{v['spares'].sum():,.0f}")
    m[3].metric("Labour ₹", f"{v['labour'].sum():,.0f}")
    if v.empty:
        st.info("No job cards in this period.")
        return

    tabs = ["🔧 Job cards", "🛵 By vehicle"] + ([] if st.session_state.dealer_store else ["🏪 By store"]) + ["📅 Monthly"]
    tabs = dict(zip(tabs, st.tabs(tabs)))
    with tabs["🔧 Job cards"]:
        out = dealer_job_columns(v)
        st.caption("Click **ⓘ** (last column) to see the parts and charges of a job card.")
        clicked = show_info_table(out, v["id"], key="sh_tbl")
        if clicked is not None:
            dealer_job_dialog(clicked)
        download_excel(out, "Service_History")
    with tabs["🛵 By vehicle"]:
        g = (v.assign(chassis=v["chassis_number"].replace("", "—"))
             .groupby("chassis").agg(**{"Store": ("store", "last"), "Job cards": ("id", "size"),
                                        "Spares ₹": ("spares", "sum"), "Labour ₹": ("labour", "sum"),
                                        "Total ₹": ("total", "sum"), "Last visit": ("date", "max")})
             .reset_index().rename(columns={"chassis": "Vehicle"}).sort_values("Job cards", ascending=False))
        g["Last visit"] = g["Last visit"].dt.strftime("%d-%b-%y")
        show_table(g.round(2), height=480)
        download_excel(g, "Service_by_Vehicle")
    if "🏪 By store" in tabs:
        with tabs["🏪 By store"]:
            g = (v.assign(s=v["store"].replace("", "—")).groupby("s")
                 .agg(**{"Job cards": ("id", "size"), "Vehicles": ("chassis_number", "nunique"),
                         "Open": ("closed", lambda s: int((~s).sum())),
                         "Spares ₹": ("spares", "sum"), "Labour ₹": ("labour", "sum"), "Total ₹": ("total", "sum")})
                 .reset_index().rename(columns={"s": "Store"}).sort_values("Total ₹", ascending=False))
            show_table(g.round(2), height=480)
            download_excel(g, "Service_by_Store")
    with tabs["📅 Monthly"]:
        g = (v.assign(Month=v["date"].dt.to_period("M").dt.to_timestamp()).groupby("Month")
             .agg(**{"Job cards": ("id", "size"), "Vehicles": ("chassis_number", "nunique"),
                     "Spares ₹": ("spares", "sum"), "Labour ₹": ("labour", "sum"), "Total ₹": ("total", "sum")})
             .reset_index().sort_values("Month", ascending=False))
        g["Month"] = g["Month"].dt.strftime("%b %Y")
        show_table(g.round(2), height=480)
        download_excel(g, "Service_by_Month")


def dealer_job_columns(v):
    forms = [f if isinstance(f, dict) else {} for f in v["form"]]

    def answers(names):
        return [", ".join(str(f[n]) for n in names if f.get(n)) for f in forms]
    out = pd.DataFrame({
        "Job Card": v["job_card_no"], "Date": fmt_date(v["job_open_date"]), "Store": v["store"],
        "Vehicle": v["chassis_number"], "KM": v["odo_km"], "Service Type": v["service_type"],
        "General Service": answers(["General Service"]),
        "Spares Replaced / Consumed": answers(["Paid Replaced Spares", "Consumed Spares on General Service",
                                               "Non - Warranty Parts Replaced"]),
        "Warranty Parts (no charge)": answers(["Warranty Parts Replaced"]),
        "Attended By": v["technician"], "Status": v["status"], "Completed On": fmt_date(v["closed_on"]),
        "Spares ₹": v["spares"], "Labour ₹": v["labour"], "Total ₹": v["total"],
        "Ticket": v["ticket_no"],
    }, index=v.index)
    if st.session_state.dealer_store:
        out = out.drop(columns="Store")
    keep = [c for c in out.columns if out[c].astype(str).str.strip().replace({"nan": "", "NaT": ""}).ne("").any()]
    return out[keep]


@st.dialog("🧾 Job card", width="large")
def dealer_job_dialog(job_id):
    jobs = dealer_job_cards()                     # scoped again — the id comes from the page
    job = jobs[jobs["id"] == int(job_id)]
    if job.empty:
        st.error("This job card is not available.")
        return
    show_dealer_job(job.iloc[0])


def show_dealer_job(job):
    """One job card as the dealer sees it: what was done and what it costs (customer price)."""
    rows = [("Job card", job.job_card_no), ("Date", pd.Timestamp(job.date).strftime("%d-%b-%Y")),
            ("Store", job.store), ("Vehicle", job.chassis_number), ("KM", job.odo_km),
            ("Service type", job.service_type), ("Attended by", job.technician), ("Status", job.status)]
    if pd.notna(job.closed_on):
        rows.append(("Completed on", pd.Timestamp(job.closed_on).strftime("%d-%b-%Y")))
    body = "".join(f"<tr><td style='color:#64748B;padding:2px 12px 2px 0;white-space:nowrap'>{k}</td>"
                   f"<td>{html.escape(str(val))}</td></tr>" for k, val in rows if val)
    st.markdown(f"""<div style="background:#F0FDF4; border:1px solid #BBF7D0; border-radius:10px;
                    padding:12px 16px; margin:8px 0 12px;"><b style="color:#1B3A6B;">🔧 Job card</b>
                    <table style="font-size:13px; margin-top:6px;">{body}</table></div>""", unsafe_allow_html=True)
    form = job.form if isinstance(job.form, dict) else {}
    lines = jobcards.cost_lines("B2B", job.service_type, form, jobcards.load_prices(get_engine()))
    if lines:
        show_table(pd.DataFrame([{"Part": p, "Spare ₹": 0 if g == "Warranty" else round(s, 2),
                                  "Labour ₹": 0 if g == "Warranty" else round(l, 2),
                                  "Note": "Covered by warranty" if g == "Warranty" else ""}
                                 for g, p, s, l, _ in lines]), height=min(60 + 38 * len(lines), 320))
    m = st.columns(3)
    m[0].metric("Spares ₹", f"{job.spares:,.2f}")
    m[1].metric("Labour ₹", f"{job.labour:,.2f}")
    m[2].metric("Total ₹", f"{job.total:,.2f}")

# ════════════════════════════════════════════════════════════════════
# CHANGE PASSWORD
# ════════════════════════════════════════════════════════════════════
def show_change_password(first_login=False):
    _, col, _ = st.columns([1, 1.4, 1])
    with col:
        st.markdown("## 🔑 Change Password")
        if first_login:
            st.info(f"👋 Welcome **{st.session_state.full_name}**! You logged in with a "
                    "temporary password. Please set your own password to continue.")
        else:
            current = st.text_input("Current password", type="password", key="pw_cur")
        new1 = st.text_input("New password (min 8 characters)", type="password", key="pw_new1")
        new2 = st.text_input("Repeat new password", type="password", key="pw_new2")

        if st.button("✅ Save Password", width='stretch', key="pw_save"):
            if not first_login:
                row = run_query("SELECT password_hash FROM users WHERE user_id = :u",
                                {"u": st.session_state.user_id})
                if row.empty or not check_password(current, row["password_hash"].iloc[0]):
                    st.error("❌ Current password is wrong.")
                    return
            if len(new1) < 8:
                st.error("❌ Password must be at least 8 characters.")
            elif new1 != new2:
                st.error("❌ The two passwords don't match.")
            elif run_insert("""UPDATE users SET password_hash=%s, must_change_password=FALSE,
                               updated_at=NOW() WHERE user_id=%s""",
                            (hash_password(new1), st.session_state.user_id)):
                audit("PASSWORD", "users", st.session_state.user_id, "Changed own password")
                st.session_state.must_change_password = False
                st.session_state.page = allowed_pages()[0][1]
                st.success("✅ Password changed!")
                st.rerun()

        if first_login and st.button("🚪 Logout", key="pw_logout"):
            st.session_state.clear()
            st.rerun()

# ════════════════════════════════════════════════════════════════════
# USER MANAGEMENT (Super Admin only)
# ════════════════════════════════════════════════════════════════════
def show_users():
    st.markdown("## 👥 User Management")
    st.markdown("Create users, reset passwords, activate / deactivate, client → TSM mapping")
    st.markdown("---")

    # message from the previous action (e.g. a new temporary password) — shown once
    msg = st.session_state.pop("users_msg", None)
    if msg:
        st.success(msg[0])
        if msg[1]:
            st.markdown("**Temporary password** (copy it now — it will not be shown again):")
            st.code(msg[1], language=None)

    tab1, tab2, tab3, tab4 = st.tabs(["👥 Users", "➕ Add User", "🗺️ Clients & Zones", "🛵 Dealer Vehicles"])

    users = run_query("""
        SELECT user_id, username, full_name, role, COALESCE(zone,'') AS zone,
               is_active, last_login, must_change_password,
               COALESCE(dealer_client,'') AS dealer_client, COALESCE(dealer_store,'') AS dealer_store,
               COALESCE(locked_until > NOW(), FALSE) AS locked,
               COALESCE(stock_hub,'') AS stock_hub
        FROM users ORDER BY is_active DESC, role = 'Dealer', role, username
    """)

    with tab1:
        if not users.empty:
            view = users.assign(
                Status=[("🔒 Locked" if lk else "🟢 Active") if a else "⚪ Inactive"
                        for a, lk in zip(users["is_active"], users["locked"])],
                LastLogin=users["last_login"].astype(str).replace({"NaT": "—", "None": "—"}),
                Password=users["must_change_password"].map({True: "Temporary", False: "Set"}),
                Dealer=[f"{c} · {s or 'All stores'}" if r == "Dealer" else ""
                        for r, c, s in zip(users["role"], users["dealer_client"], users["dealer_store"])],
                Hub=users["stock_hub"].map(lambda h: hub_names().get(h, "")),
            )[["username", "full_name", "role", "zone", "Hub", "Dealer", "Status", "Password", "LastLogin"]]
            view.columns = ["Username", "Name", "Role", "Zone", "Stock hub", "Dealer of", "Status", "Password",
                            "Last Login"]
            if not (view["Dealer of"] != "").any():
                view = view.drop(columns="Dealer of")
            show_table(view, height=360)

        st.markdown("#### ✏️ Manage a user")
        opts = {f"{r.username} — {r.full_name}": r for r in users.itertuples()}
        sel = st.selectbox("Select user", list(opts.keys()), key="um_sel")
        u = opts[sel]
        is_me = int(u.user_id) == st.session_state.user_id

        c1, c2 = st.columns(2)
        with c1:
            new_role = st.selectbox("Role", ROLES, index=ROLES.index(u.role) if u.role in ROLES else 0,
                                    key=f"um_role_{u.user_id}", disabled=is_me)
        with c2:
            new_zone = st.selectbox("Zone", ZONES, index=ZONES.index(u.zone) if u.zone in ZONES else 0,
                                    key=f"um_zone_{u.user_id}")
        d_client, d_store = dealer_scope_inputs(f"um_{u.user_id}", u.dealer_client, u.dealer_store) \
            if new_role == "Dealer" else (None, None)
        s_hub = stock_hub_input(f"um_hub_{u.user_id}", u.stock_hub) if new_role != "Dealer" else None

        b1, b2, b3 = st.columns(3)
        if b1.button("💾 Save Role / Zone", width='stretch', key="um_save"):
            if new_role == "Dealer" and not d_client:
                st.warning("⚠️ Choose the dealer's client.")
            elif run_insert("""UPDATE users SET role=%s, zone=%s, dealer_client=%s, dealer_store=%s, stock_hub=%s,
                               updated_at=NOW() WHERE user_id=%s""",
                            (new_role, new_zone, d_client, d_store, s_hub, int(u.user_id))):
                audit("UPDATE", "users", int(u.user_id), f"{u.username}: role={new_role}, zone={new_zone}"
                      + (f", dealer of {d_client} / {d_store or 'all stores'}" if new_role == "Dealer" else "")
                      + (f", stock hub {s_hub}" if s_hub else ""))
                st.session_state.users_msg = (f"✅ {u.username} updated.", None)
                st.rerun()
        if b2.button("🔄 Reset Password", width='stretch', key="um_reset",
                     help="Also unlocks a login locked after wrong passwords"):
            pw = temp_password()
            if run_insert("""UPDATE users SET password_hash=%s, must_change_password=TRUE,
                             failed_logins=0, locked_until=NULL,
                             updated_at=NOW() WHERE user_id=%s""", (hash_password(pw), int(u.user_id))):
                audit("PASSWORD", "users", int(u.user_id), f"{u.username}: password reset by admin")
                st.session_state.users_msg = (
                    f"✅ Password reset for **{u.username}**. They must change it at next login.", pw)
                st.rerun()
        if u.is_active:
            if b3.button("⛔ Deactivate", width='stretch', key="um_deact", disabled=is_me):
                run_insert("UPDATE users SET is_active=FALSE, updated_at=NOW() WHERE user_id=%s", (int(u.user_id),))
                audit("DEACTIVATE", "users", int(u.user_id), f"{u.username} deactivated")
                st.session_state.users_msg = (f"⛔ {u.username} can no longer log in. History is kept.", None)
                st.rerun()
        else:
            if b3.button("✅ Activate", width='stretch', key="um_act"):
                run_insert("UPDATE users SET is_active=TRUE, updated_at=NOW() WHERE user_id=%s", (int(u.user_id),))
                audit("ACTIVATE", "users", int(u.user_id), f"{u.username} activated")
                st.session_state.users_msg = (f"✅ {u.username} activated.", None)
                st.rerun()
        if is_me:
            st.caption("You can't change your own role or deactivate yourself.")

    with tab2:
        c1, c2 = st.columns(2)
        with c1:
            nu_user = st.text_input("Username (e.g. Ravi)", key="nu_user").strip()
            nu_name = st.text_input("Full name", key="nu_name").strip()
            nu_phone = st.text_input("Phone (optional)", key="nu_phone").strip()
        with c2:
            nu_role = st.selectbox("Role", ROLES, index=ROLES.index("Territory Manager"), key="nu_role")
            nu_zone = st.selectbox("Zone", ZONES, key="nu_zone")
            nu_email = st.text_input("Email (optional)", key="nu_email").strip()
        nu_client, nu_store = dealer_scope_inputs("nu", "", "") if nu_role == "Dealer" else (None, None)
        nu_hub = stock_hub_input("nu_hub", "") if nu_role != "Dealer" else None
        if nu_role == "Dealer":
            st.caption("🏪 A dealer login sees ONLY this client's complaints and job cards — "
                       "one store, or all stores for their head office. No costs at landing price, no other clients.")

        if st.button("➕ Create User", width='stretch', key="nu_create"):
            taken = nu_user.lower() in users["username"].str.lower().tolist()
            if not nu_user or not nu_name:
                st.warning("⚠️ Username and full name are required.")
            elif nu_role == "Dealer" and not nu_client:
                st.warning("⚠️ Choose the dealer's client.")
            elif not nu_user.replace(".", "").replace("_", "").isalnum():
                st.warning("⚠️ Username: letters, numbers, . and _ only (no spaces).")
            elif taken:
                st.warning(f"⚠️ Username '{nu_user}' already exists.")
            else:
                pw = temp_password()
                if run_insert("""INSERT INTO users (username, password_hash, full_name, role, zone,
                                                    phone, email, must_change_password, dealer_client, dealer_store,
                                                    stock_hub)
                                 VALUES (%s,%s,%s,%s,%s,%s,%s,TRUE,%s,%s,%s)""",
                              (nu_user, hash_password(pw), nu_name, nu_role, nu_zone,
                               nu_phone or None, nu_email or None, nu_client, nu_store, nu_hub)):
                    audit("CREATE", "users", None, f"Created {nu_user} ({nu_role}, {nu_zone})")
                    st.session_state.users_msg = (
                        f"✅ User **{nu_user}** created. Share the temporary password — "
                        "they will set their own at first login.", pw)
                    st.rerun()

    with tab3:
        show_client_zones(users)
    with tab4:
        show_dealer_vehicles()


def show_dealer_vehicles():
    """Which vehicle belongs to which dealer store. A store login only picks these vehicles in a complaint."""
    cl = run_query("""SELECT DISTINCT client_name FROM client_locations
                      WHERE NOT COALESCE(is_rental, FALSE) AND COALESCE(is_active, TRUE) ORDER BY 1""")
    clients = cl["client_name"].tolist() if not cl.empty else []
    if not clients:
        st.info("No B2B clients yet.")
        return
    client = st.selectbox("Client", clients, index=clients.index("QuickBite") if "QuickBite" in clients else 0, key="dv_client")
    stores = client_stores(client)
    veh = run_query("""SELECT chassis_number, COALESCE(store, '') AS store, is_active, COALESCE(note, '') AS note
                       FROM dealer_vehicles WHERE LOWER(client_name) = LOWER(:c)
                       ORDER BY store NULLS FIRST, chassis_number""", {"c": client})
    for s in veh["store"].unique() if not veh.empty else []:
        if s and s not in stores:
            stores.append(s)

    if not veh.empty:
        act = veh[veh["is_active"]]
        un = int((act["store"] == "").sum())
        m = st.columns(3)
        m[0].metric("Vehicles", len(act))
        m[1].metric("Stores", act.loc[act["store"] != "", "store"].nunique())
        m[2].metric("Not assigned", un)
        if un:
            st.warning(f"⚠️ {un} vehicle(s) have no store — pick one below (they are at the top of the list).")
    st.caption("Pick each vehicle's store. Add a row for a new vehicle; untick **Active** when a vehicle is taken back. "
               "Click 💾 Save when done.")
    f1, f2 = st.columns([1.4, 2])
    store_f = f1.selectbox("Show store", ["All", "— not assigned —"] + stores, key="dv_store")
    search = f2.text_input("🔍 Chassis", key="dv_search").strip().upper().replace(" ", "")
    view = veh
    if store_f == "— not assigned —":
        view = view[view["store"] == ""]
    elif store_f != "All":
        view = view[view["store"] == store_f]
    if search:
        view = view[view["chassis_number"].str.contains(search, regex=False)]
    filtered = store_f != "All" or bool(search)

    edited = st.data_editor(
        view.reset_index(drop=True), key=f"dv_ed_{client}_{store_f}_{search}", width='stretch', height=460,
        num_rows="fixed" if filtered else "dynamic", hide_index=True,
        column_config={
            "chassis_number": st.column_config.TextColumn("Chassis", required=True, max_chars=40),
            "store": st.column_config.SelectboxColumn("Store (empty = not assigned)", options=[""] + stores, width="large"),
            "is_active": st.column_config.CheckboxColumn("Active", default=True),
            "note": st.column_config.TextColumn("Note", max_chars=200),
        })
    if filtered:
        st.caption("To add a vehicle, set **Show store** to All and clear the search.")

    with st.expander("📥 Add / update many vehicles from Excel"):
        st.caption("An Excel sheet with a **Chassis** column and a **Store** column (store names exactly as in the list above).")
        up = st.file_uploader("Excel file", type=["xlsx"], key=f"dv_up_{client}")
        if up is not None and st.button("Import", key="dv_import"):
            try:
                x = pd.read_excel(up)
                cc = next(c for c in x.columns if "chassis" in str(c).lower())
                sc = next((c for c in x.columns if "store" in str(c).lower()), None)
            except Exception:
                st.error("Couldn't read it — the sheet needs a 'Chassis' column (and a 'Store' column).")
            else:
                rows = [(str(r[cc]).replace(" ", "").upper(),
                         (str(r[sc]).strip() if sc is not None and pd.notna(r[sc]) else ""))
                        for _, r in x.iterrows() if pd.notna(r[cc]) and str(r[cc]).strip()]
                bad = sorted({s for _, s in rows if s and s not in stores})
                if bad:
                    st.error(f"Unknown store name(s): {', '.join(bad)}. Use the names from the list above.")
                else:
                    save_dealer_vehicles(client, [{"chassis_number": c, "store": s, "is_active": True, "note": ""}
                                                  for c, s in rows], [])
                    st.session_state.dv_msg = f"✅ {len(rows)} vehicle(s) imported."
                    st.rerun()

    msg = st.session_state.pop("dv_msg", None)
    if msg:
        st.success(msg)
    if st.button("💾 Save vehicles", width='stretch', type="primary", key="dv_save"):
        new = edited.fillna({"store": "", "note": "", "is_active": True})
        new["chassis_number"] = new["chassis_number"].astype(str).str.replace(" ", "").str.upper()
        new = new[new["chassis_number"].str.len() > 0]
        if new["chassis_number"].duplicated().any():
            st.error("The same chassis is in the list twice: " +
                     ", ".join(new.loc[new["chassis_number"].duplicated(), "chassis_number"]))
            return
        old = view.set_index("chassis_number")
        changed = [r for r in new.to_dict("records")
                   if r["chassis_number"] not in old.index
                   or (old.loc[r["chassis_number"], "store"], bool(old.loc[r["chassis_number"], "is_active"]),
                       old.loc[r["chassis_number"], "note"]) != (r["store"], bool(r["is_active"]), r["note"])]
        removed = [c for c in old.index if c not in set(new["chassis_number"])]
        save_dealer_vehicles(client, changed, removed)
        st.session_state.dv_msg = f"✅ Saved — {len(changed)} changed" + (f", {len(removed)} taken back" if removed else "") + "."
        st.rerun()


def save_dealer_vehicles(client, rows, removed):
    """Insert / update vehicles (store '' = not assigned); removed rows become inactive (history is kept)."""
    from sqlalchemy import text
    with get_engine().begin() as c:
        for r in rows:
            c.execute(text(f"""
                INSERT INTO dealer_vehicles (client_name, chassis_number, store, is_active, note, updated_by, updated_at)
                VALUES (:cl, :ch, :s, :a, :n, :u, {IST_NOW})
                ON CONFLICT (LOWER(client_name), chassis_number) DO UPDATE SET
                    store = EXCLUDED.store, is_active = EXCLUDED.is_active, note = EXCLUDED.note,
                    updated_by = EXCLUDED.updated_by, updated_at = EXCLUDED.updated_at"""),
                {"cl": client, "ch": r["chassis_number"], "s": r["store"] or None, "a": bool(r["is_active"]),
                 "n": r["note"] or None, "u": st.session_state.user_id})
        for ch in removed:
            c.execute(text(f"""UPDATE dealer_vehicles SET is_active = FALSE, updated_by = :u, updated_at = {IST_NOW}
                               WHERE LOWER(client_name) = LOWER(:cl) AND chassis_number = :ch"""),
                      {"cl": client, "ch": ch, "u": st.session_state.user_id})
    if rows or removed:
        audit("UPDATE", "dealer_vehicles", None, f"{client}: {len(rows)} vehicle(s) saved, {len(removed)} taken back")

def dealer_scope_inputs(prefix, cur_client, cur_store):
    """Client + store pickers for a Dealer login. Store '' = head office (all stores)."""
    cl = run_query("""SELECT DISTINCT client_name FROM client_locations
                      WHERE NOT COALESCE(is_rental, FALSE) AND COALESCE(is_active, TRUE) ORDER BY 1""")
    clients = cl["client_name"].tolist() if not cl.empty else []
    if cur_client and cur_client not in clients:
        clients.append(cur_client)
    c1, c2 = st.columns(2)
    client = c1.selectbox("Dealer of client", clients, index=clients.index(cur_client) if cur_client in clients else None,
                          placeholder="Choose the client", key=f"{prefix}_dclient")
    stores = [""] + (client_stores(client) if client else [])
    if cur_store and cur_store not in stores:
        stores.append(cur_store)
    store = c2.selectbox("Store", stores, index=stores.index(cur_store) if cur_store in stores else 0,
                         format_func=lambda s: s or "🏢 All stores (head office)", key=f"{prefix}_dstore")
    return client, (store or None)


def show_client_zones(users):
    """Client + location → zone → TSM. Decides which job cards each TSM sees."""
    clients = run_query("""
        SELECT c.location_id, c.client_name, COALESCE(c.location,'') AS location, c.zone,
               u.username AS tsm, c.tsm_user_id, c.is_rental, c.is_active
        FROM client_locations c LEFT JOIN users u ON u.user_id = c.tsm_user_id
        ORDER BY c.zone, c.client_name, c.location
    """)
    if not clients.empty:
        view = clients.assign(
            Location=clients["location"].replace({"": "All locations"}),
            Type=clients["is_rental"].map({True: "Rental (B2C)", False: "B2B"}),
            Status=clients["is_active"].map({True: "🟢 Active", False: "⚪ Inactive"}),
        )[["client_name", "Location", "zone", "tsm", "Type", "Status"]]
        view.columns = ["Client", "Location", "Zone", "TSM", "Type", "Status"]
        show_table(view, height=320)

    tsms = users[(users["role"] == "Territory Manager") & users["is_active"]]
    tsm_opts = dict(zip(tsms["username"], tsms["user_id"]))
    if not tsm_opts:
        st.info("Create a Territory Manager user first.")
        return

    st.markdown("#### ✏️ Edit a client")
    if not clients.empty:
        c_opts = {f"{r.client_name} – {r.location or 'All locations'}": r for r in clients.itertuples()}
        csel = c_opts[st.selectbox("Client", list(c_opts.keys()), key="cz_sel")]
        n1, n2 = st.columns(2)
        new_name = n1.text_input("Client name", value=csel.client_name,
                                 key=f"cz_name_{csel.location_id}").strip()
        new_loc = n2.text_input("Location (blank = all)", value=csel.location,
                                key=f"cz_loc_{csel.location_id}").strip()
        k1, k2, k3 = st.columns(3)
        tsm_names = list(tsm_opts.keys())
        new_tsm = k1.selectbox("TSM", tsm_names,
                               index=tsm_names.index(csel.tsm) if csel.tsm in tsm_names else 0,
                               key=f"cz_tsm_{csel.location_id}")
        new_zone = k2.selectbox("Zone", ZONES, index=ZONES.index(csel.zone) if csel.zone in ZONES else 0,
                                key=f"cz_zone_{csel.location_id}")
        active = k3.checkbox("Active", value=bool(csel.is_active), key=f"cz_act_{csel.location_id}")
        if st.button("💾 Save Client", width='stretch', key="cz_save"):
            dup = clients[(clients["client_name"].str.lower() == new_name.lower())
                          & (clients["location"].str.lower() == new_loc.lower())
                          & (clients["location_id"] != csel.location_id)]
            if not new_name:
                st.warning("⚠️ Client name is required.")
            elif not dup.empty:
                st.warning(f"⚠️ {new_name} – {new_loc or 'All locations'} already exists.")
            elif run_insert("""UPDATE client_locations SET client_name=%s, location=%s, tsm_user_id=%s,
                                      zone=%s, is_active=%s WHERE location_id=%s""",
                            (new_name, new_loc or None, int(tsm_opts[new_tsm]), new_zone, active,
                             int(csel.location_id))):
                audit("UPDATE", "client_locations", int(csel.location_id),
                      f"{csel.client_name} {csel.location} → {new_name} {new_loc}: "
                      f"TSM={new_tsm}, zone={new_zone}, active={active}")
                st.session_state.users_msg = (f"✅ {new_name} updated.", None)
                st.rerun()

    st.markdown("#### ➕ Add client / location")
    a1, a2, a3, a4 = st.columns(4)
    nc_name = a1.text_input("Client name", key="nc_name").strip()
    nc_loc = a2.text_input("Location (blank = all)", key="nc_loc").strip()
    nc_zone = a3.selectbox("Zone", ZONES, key="nc_zone")
    nc_tsm = a4.selectbox("TSM", list(tsm_opts.keys()), key="nc_tsm")
    if st.button("➕ Add Client", width='stretch', key="nc_add"):
        dup = clients[(clients["client_name"].str.lower() == nc_name.lower())
                      & (clients["location"].str.lower() == nc_loc.lower())] if not clients.empty else clients
        if not nc_name:
            st.warning("⚠️ Client name is required.")
        elif not dup.empty:
            st.warning(f"⚠️ {nc_name} – {nc_loc or 'All locations'} already exists.")
        elif run_insert("""INSERT INTO client_locations (client_name, location, zone, tsm_user_id)
                           VALUES (%s,%s,%s,%s)""",
                        (nc_name, nc_loc or None, nc_zone, int(tsm_opts[nc_tsm]))):
            audit("CREATE", "client_locations", None, f"Added {nc_name} {nc_loc} → {nc_tsm}")
            st.session_state.users_msg = (f"✅ {nc_name} added under {nc_tsm}.", None)
            st.rerun()

# ════════════════════════════════════════════════════════════════════
# INVENTORY — 3 hubs: Parts Master & live stock · Stock IN · Stock OUT / Transfer
# Every portal entry is appended to the hub's OneDrive Excel at once (inventory.push_moves).
# ════════════════════════════════════════════════════════════════════
STATUS_ORDER = ["⚠️ Negative", "🔴 No Stock", "🟡 Low Stock", "🟢 In Stock"]
# parts a hub keeps (ever moved there) that are at / below their reorder level — one row per hub + part
LOW_STOCK_SQL = """
    SELECT m.hub, p.part_code, p.description, p.landing_cost, p.reorder_level,
           SUM(CASE m.direction WHEN 'IN' THEN m.qty ELSE -m.qty END) AS stock
    FROM inv_moves m JOIN inv_parts p USING (part_code)
    WHERE p.is_active
    GROUP BY m.hub, p.part_code
    HAVING SUM(CASE m.direction WHEN 'IN' THEN m.qty ELSE -m.qty END) <= p.reorder_level"""


@st.cache_data(ttl=600, show_spinner=False)
def hub_names():
    d = run_query("SELECT hub, name FROM stock_hubs WHERE is_active ORDER BY sort_order")
    return dict(zip(d["hub"], d["name"])) if not d.empty else {}


@st.cache_data(ttl=600, show_spinner=False)
def hub_excel_names():
    d = run_query("SELECT hub, excel_name FROM stock_hubs WHERE is_active ORDER BY sort_order")
    return dict(zip(d["hub"], d["excel_name"])) if not d.empty else {}


@st.cache_data(ttl=300, show_spinner=False)
def parts_options():
    """'CODE — Description' → code, for the part pickers."""
    d = run_query("SELECT part_code, description FROM inv_parts WHERE is_active ORDER BY description, part_code")
    return {f"{r.part_code} — {r.description}": r.part_code for r in d.itertuples()}


def stock_hub_input(key, current):
    names = hub_names()
    opts = [""] + list(names)
    return st.selectbox("Stock hub (keeps this hub's stock)", opts,
                        index=opts.index(current) if current in opts else 0,
                        format_func=lambda h: names.get(h, "— none —"), key=key,
                        help="This user enters Stock IN / OUT for this hub only (even as a TSM). "
                             "None = head office / not a store person.") or None


def entry_hubs(page):
    """Hubs this user may enter stock for on this page (a hub's store person: only that hub)."""
    if not can_edit(page):
        return []
    mine = st.session_state.get("stock_hub")
    return [mine] if mine else list(hub_names())


def hub_filter(key):
    names = hub_names()
    opts = ["ALL"] + list(names)
    mine = st.session_state.get("stock_hub")
    return st.selectbox("Hub", opts, index=opts.index(mine) if mine in opts else 0,
                        format_func=lambda h: "🏢 All hubs" if h == "ALL" else names[h], key=key)


def stock_status(stock, reorder):
    if stock < 0:
        return STATUS_ORDER[0]
    if stock == 0:
        return STATUS_ORDER[1]
    return STATUS_ORDER[2] if stock <= reorder else STATUS_ORDER[3]


def stock_table(hub):
    """One row per part: stock per hub, total, value at landing cost, oldest stock age, status."""
    raw = run_query(inventory.STOCK_SQL.format(hub_filter="" if hub == "ALL" else "AND h.hub = :hub"), {"hub": hub})
    if raw.empty:
        return raw, raw
    raw = raw[raw["is_active"]].copy()
    raw["stock"] = raw["received"] - raw["issued"]
    raw["landing_cost"] = money_col(raw["landing_cost"])
    raw["value"] = raw["stock"].clip(lower=0) * raw["landing_cost"]
    raw["first_in"] = pd.to_datetime(raw["first_in"])      # dates + blanks → one type, so min() works across hubs
    per = raw.groupby("part_code").agg(
        description=("description", "first"), landing=("landing_cost", "first"),
        customer=("customer_price", "first"), reorder=("reorder_level", "first"),
        received=("received", "sum"), issued=("issued", "sum"), stock=("stock", "sum"),
        value=("value", "sum"), first_in=("first_in", "min"), lowest=("stock", "min")).reset_index()
    per["aging"] = [(now_ist().normalize() - d).days if s > 0 and pd.notna(d) else None
                    for d, s in zip(per["first_in"], per["stock"])]
    # below zero at ANY hub is flagged, even if another hub's stock makes the total look fine
    per["status"] = [STATUS_ORDER[0] if lo < 0 else stock_status(s, r)
                     for s, r, lo in zip(per["stock"], per["reorder"], per["lowest"])]
    per["kept"] = (per["received"] > 0) | (per["issued"] > 0)
    return per, raw


def show_parts():
    st.markdown("## 📦 Parts Master & Live Stock")
    st.caption("One parts list for all hubs · stock = everything received − everything issued at the hub · "
               "value at FleetCo landing cost")
    st.markdown("---")
    names = hub_names()
    f1, f2, f3, f4 = st.columns([1.3, 1.7, 1.2, 1])
    with f1:
        hub = hub_filter("pm_hub")
    q = f2.text_input("🔎 Search code / part", key="pm_q").strip().lower()
    status = f3.selectbox("Status", ["All"] + STATUS_ORDER, key="pm_status")
    kept_only = f4.toggle("Only parts we stock", value=True, key="pm_kept",
                          help="Hide parts never received or issued at this hub")
    per, raw = stock_table(hub)
    if per.empty:
        show_table(per)
        return
    kept = per[per["kept"]]
    m = st.columns(5)
    m[0].metric("Parts we stock", f"{len(kept):,}")
    m[1].metric("Stock qty (pcs)", f"{int(kept['stock'].clip(lower=0).sum()):,}")
    m[2].metric("Stock value ₹", f"{kept['value'].sum():,.0f}")
    m[3].metric("Low / no stock", f"{int(kept['status'].isin(STATUS_ORDER[1:3]).sum()):,}")
    m[4].metric("⚠️ Negative", f"{int((kept['status'] == STATUS_ORDER[0]).sum()):,}",
                help="Issued more than received — an IN entry is missing or a wrong code/qty was entered")

    view = kept if kept_only else per
    if status != "All":
        view = view[view["status"] == status]
    if q:
        view = view[view["part_code"].str.lower().str.contains(q, regex=False)
                    | view["description"].str.lower().str.contains(q, regex=False)]
    view = view.assign(_o=view["status"].map(STATUS_ORDER.index)).sort_values(["_o", "description"])
    out = pd.DataFrame({"Code": view["part_code"], "Part": view["description"],
                        "Landing ₹": view["landing"].round(2), "Customer ₹": money_col(view["customer"]).round(2)})
    if hub == "ALL":
        piv = raw.pivot_table(index="part_code", columns="hub", values="stock", aggfunc="sum").reindex(view["part_code"])
        for h in names:
            if h in piv:
                out[names[h].split(" (")[0]] = piv[h].fillna(0).astype(int).values
    out["Received"] = view["received"].astype(int).values
    out["Issued"] = view["issued"].astype(int).values
    out["Stock"] = view["stock"].astype(int).values
    out["Value ₹"] = view["value"].round(0).astype(int).values
    out["Oldest (days)"] = view["aging"].map(lambda v: "" if pd.isna(v) else int(v)).values
    out["Status"] = view["status"].values
    st.caption(f"{len(out):,} parts")
    show_table(out.reset_index(drop=True), height=560)
    download_excel(out, f"FleetCo_Stock_{hub}")

    if can_edit("Parts Master") and not is_tsm():
        show_parts_admin()


def show_parts_admin():
    st.markdown("---")
    st.markdown("#### ⚙️ Manage parts")
    t1, t2, t3 = st.tabs(["➕ New part", "🎚️ Reorder level / active", "🔄 Prices from Excel"])
    with t1:
        st.caption("A new part is added here and to every hub's Excel (PARTS LIST + LIVE STOCK).")
        n = st.session_state.setdefault("np_n", 0)
        msg = st.session_state.pop("np_msg", None)
        if msg:
            (st.success if msg[0] else st.warning)(msg[1])
        with st.form(f"np_form_{n}"):
            c1, c2, c3 = st.columns([1, 2, 1])
            code = c1.text_input("Part code *")
            desc = c2.text_input("Description *")
            hsn = c3.text_input("HSN")
            c4, c5, c6, c7 = st.columns(4)
            landing = c4.number_input("Landing cost ₹ *", min_value=0.0, step=1.0)
            margin = c5.number_input("Margin %", min_value=0.0, value=10.0, step=1.0)
            gst = c6.number_input("GST %", min_value=0.0, value=18.0, step=1.0)
            reorder = c7.number_input("Low stock at or below", min_value=0, value=10, step=1)
            ok = st.form_submit_button("➕ Add part", type="primary")
        if ok:
            key = re.sub(r"\s+", "", code).upper()
            if not key or not desc.strip() or landing <= 0:
                st.warning("⚠️ Part code, description and landing cost are required.")
            elif key in set(parts_options().values()) or not run_query(
                    "SELECT 1 FROM inv_parts WHERE part_code = :c", {"c": key}).empty:
                st.warning(f"⚠️ Part code {key} already exists.")
            elif run_insert("""INSERT INTO inv_parts (part_code, description, hsn, landing_cost, margin, customer_price,
                                                      gst, reorder_level, in_excel, updated_by)
                               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,FALSE,%s)""",
                            (key, desc.strip()[:200], hsn.strip() or None, landing, margin / 100,
                             round(landing * (1 + margin / 100), 2), gst / 100, int(reorder),
                             st.session_state.user_id)):
                audit("CREATE", "inv_parts", None, f"New part {key} — {desc.strip()}")
                parts_options.clear()
                with st.spinner("Adding to every hub's Excel…"):
                    res = inventory.push_parts(get_engine())
                r = next((x for x in res if x[0] == key), None)
                st.session_state.np_msg = (True, f"✅ {key} added — and to every hub's Excel.") if r and r[1] else \
                    (False, f"⏳ {key} added in the portal — Excel not updated yet: "
                            f"{r[2] if r else 'Excel connection not set up here (only on the live portal)'}")
                st.session_state.np_n = n + 1
                st.rerun()
    with t2:
        d = run_query("SELECT part_code, description, reorder_level, is_active FROM inv_parts ORDER BY description")
        d.columns = ["Code", "Part", "Low stock at or below", "Active"]
        ed = st.data_editor(d, key="pr_edit", hide_index=True, width="stretch", height=420,
                            disabled=["Code", "Part"],
                            column_config={"Low stock at or below": st.column_config.NumberColumn(min_value=0, step=1)})
        if st.button("💾 Save reorder levels", key="pr_save"):
            ch = ed[(ed["Low stock at or below"] != d["Low stock at or below"]) | (ed["Active"] != d["Active"])]
            for r in ch.itertuples(index=False):
                run_insert("UPDATE inv_parts SET reorder_level=%s, is_active=%s, updated_by=%s WHERE part_code=%s",
                           (int(r[2] or 0), bool(r[3]), st.session_state.user_id, r[0]))
            if len(ch):
                audit("UPDATE", "inv_parts", None, f"Reorder level / active changed for {len(ch)} part(s)")
                parts_options.clear()
            st.success(f"✅ {len(ch)} part(s) updated.")
    with t3:
        st.caption("Names and prices come from the **🔧 PARTS LIST** of the Central Hub inventory Excel — "
                   "change a price there, then refresh here.")
        if st.button("🔄 Refresh prices from Excel", key="pr_refresh"):
            try:
                with st.spinner("Reading the PARTS LIST…"):
                    changed, total = inventory.refresh_prices(get_engine())
                parts_options.clear()
                audit("UPDATE", "inv_parts", None, f"Prices refreshed from Excel: {changed} changed")
                st.success(f"✅ {total} parts read — {changed} new or changed.")
            except Exception as e:
                st.error(f"Could not read the Excel: {e}")


# ── entries ─────────────────────────────────────────────────────────
def excel_state(origin, pending, row):
    if origin == "excel":
        return "📄 old Excel log"
    if pending:
        return "⏳ pending"
    return f"✅ row {int(row)}" if pd.notna(row) else "✅"


def show_moves(direction):
    """History of stock received (IN) or issued (OUT), with filters and Excel download."""
    k = direction.lower()
    names = hub_names()
    f1, f2, f3, f4 = st.columns([1.2, 1, 1, 1.8])
    with f1:
        hub = hub_filter(f"mv_hub_{k}")
    today = now_ist().date()
    since = f2.date_input("From", value=today - pd.Timedelta(days=90), format="DD-MM-YYYY", key=f"mv_from_{k}")
    until = f3.date_input("To", value=today, format="DD-MM-YYYY", key=f"mv_to_{k}")
    q = f4.text_input("🔎 Search part / chassis / technician / ref", key=f"mv_q_{k}").strip().lower()
    d = run_query("""
        SELECT m.id, m.hub, m.move_date, m.part_code, p.description, m.qty, m.unit_cost,
               m.source, m.ref_no, m.purpose, m.issued_for, m.technician, m.chassis_number, m.in_charge,
               m.remarks, m.origin, m.excel_row, m.excel_pending, m.excel_error, f.job_card_no
        FROM inv_moves m
        JOIN inv_parts p USING (part_code)
        LEFT JOIN form_job_cards f ON f.id = m.job_card_id
        WHERE m.direction = :d AND (:hub = 'ALL' OR m.hub = :hub)
          AND (m.move_date IS NULL OR m.move_date BETWEEN :a AND :b)
        ORDER BY m.move_date DESC NULLS LAST, m.id DESC""",
                  {"d": direction, "hub": hub, "a": since, "b": until})
    if d.empty:
        show_table(d)
        return
    d["value"] = money_col(d["unit_cost"]) * d["qty"]
    if q:
        hay = d[["part_code", "description", "chassis_number", "technician", "ref_no", "source", "issued_for",
                 "job_card_no", "remarks"]].fillna("").astype(str).agg(" ".join, axis=1).str.lower()
        d = d[hay.str.contains(q, regex=False)]
    m = st.columns(4)
    m[0].metric("Entries", f"{len(d):,}")
    m[1].metric("Qty (pcs)", f"{int(d['qty'].sum()):,}")
    m[2].metric("Value ₹ (landing)", f"{d['value'].sum():,.0f}")
    pend = d[d["excel_pending"]]
    m[3].metric("Waiting for Excel", f"{len(pend):,}")
    out = pd.DataFrame({"Date": fmt_date(d["move_date"]).replace("", "no date")})
    if hub == "ALL":
        out["Hub"] = d["hub"].map(lambda h: names.get(h, h).split(" (")[0])
    out["Code"], out["Part"], out["Qty"] = d["part_code"], d["description"], d["qty"]
    out["Unit ₹"], out["Value ₹"] = money_col(d["unit_cost"]).round(2), d["value"].round(2)
    if direction == "IN":
        out["Source"], out["Ref No."], out["In-charge"] = d["source"], d["ref_no"], d["in_charge"]
    else:
        out["Purpose"], out["Issued for"], out["Technician"] = d["purpose"], d["issued_for"], d["technician"]
        out["Chassis"], out["Job card"], out["Issued by"] = d["chassis_number"], d["job_card_no"], d["in_charge"]
        out["Remarks"] = d["remarks"]
    out["Excel"] = [excel_state(o, p, r) for o, p, r in zip(d["origin"], d["excel_pending"], d["excel_row"])]
    show_table(out.fillna("").reset_index(drop=True), height=520)
    download_excel(out, f"FleetCo_Stock_{direction}_{hub}")
    if len(pend) and entry_hubs(f"Stock {direction}"):
        st.caption(f"⏳ Last Excel error: {pend['excel_error'].dropna().iloc[0] if pend['excel_error'].notna().any() else '—'}")
        if st.button("🔁 Write pending entries to Excel now", key=f"mv_retry_{k}"):
            with st.spinner("Writing to Excel…"):
                res = inventory.push_moves(get_engine(), [int(i) for i in pend["id"]])
            ok = sum(1 for r in res if r[1])
            (st.success if ok == len(res) else st.warning)(f"{ok} of {len(res)} written to Excel.")
            if ok:
                st.rerun()


def lines_editor(key):
    """Part + qty lines. Returns ([(code, qty)], incomplete_rows?) — the same part twice is added up."""
    opts = parts_options()
    blank = pd.DataFrame({"Part": pd.Series([None] * 4, dtype="object"), "Qty": pd.Series([None] * 4, dtype="Int64")})
    ed = st.data_editor(blank, key=key, num_rows="dynamic", hide_index=True, width="stretch",
                        column_config={
                            "Part": st.column_config.SelectboxColumn("Part (type a code or name)", options=list(opts),
                                                                     width="large"),
                            "Qty": st.column_config.NumberColumn("Qty", min_value=1, step=1, width="small")})
    lines, half = {}, False
    for p, qv in zip(ed["Part"], ed["Qty"]):
        has_p, has_q = isinstance(p, str) and p in opts, pd.notna(qv) and int(qv) > 0
        if has_p and has_q:
            lines[opts[p]] = lines.get(opts[p], 0) + int(qv)
        elif has_p or has_q:
            half = True
    return list(lines.items()), half


def save_moves(rows, check_hub_stock=None):
    """Insert stock entries in ONE transaction, then write them to the hubs' Excel.
    check_hub_stock: hub to check — an issue can't take more than that hub has.
    Returns (ids, excel results) or (None, error message)."""
    cols = ["hub", "direction", "move_date", "part_code", "qty", "source", "ref_no", "purpose", "issued_for",
            "technician", "chassis_number", "remarks", "in_charge", "transfer_id"]
    eng = get_engine()
    with eng.begin() as c:
        if check_hub_stock:
            # one issue at a time per hub, so two people can't both take the last piece
            c.execute(sqltext("SELECT 1 FROM stock_hubs WHERE hub = :h FOR UPDATE"), {"h": check_hub_stock})
            want = {}
            for r in rows:
                if r["direction"] == "OUT" and r["hub"] == check_hub_stock:
                    want[r["part_code"]] = want.get(r["part_code"], 0) + r["qty"]
            have = dict(c.execute(sqltext("""
                SELECT part_code, SUM(CASE direction WHEN 'IN' THEN qty ELSE -qty END) FROM inv_moves
                WHERE hub = :h AND part_code = ANY(:p) GROUP BY part_code"""),
                {"h": check_hub_stock, "p": list(want)}).all())
            short = [f"{p}: asked {q}, in stock {int(have.get(p) or 0)}" for p, q in want.items()
                     if q > int(have.get(p) or 0)]
            if short:
                return None, "Not enough stock at this hub — " + "; ".join(short)
        costs = dict(c.execute(sqltext("SELECT part_code, landing_cost FROM inv_parts WHERE part_code = ANY(:p)"),
                               {"p": list({r["part_code"] for r in rows})}).all())
        ids = [c.execute(sqltext(f"""
                   INSERT INTO inv_moves ({", ".join(cols)}, unit_cost, origin, excel_pending, created_by)
                   VALUES ({", ".join(":" + k for k in cols)}, :unit_cost, 'portal', TRUE, :uid) RETURNING id"""),
                         {**{k: r.get(k) for k in cols}, "unit_cost": costs.get(r["part_code"]),
                          "uid": st.session_state.user_id}).scalar() for r in rows]
    try:
        inventory.link_jobs(eng)                     # an issue to a chassis joins that vehicle's job card
    except Exception:
        pass
    with st.spinner("Writing to the hub's Excel…"):
        res = inventory.push_moves(eng, ids)
    return ids, res


def save_message(what, ids, res):
    ok = [r for r in res if r[1]]
    if len(ok) == len(res):
        rows = ", ".join(r[2].replace("Excel row ", "") for r in ok)
        return True, f"✅ {what} — saved in the portal and the hub's Excel (rows {rows})."
    err = next((r[2] for r in res if not r[1]), "")
    return False, (f"⏳ {what} — saved in the portal. Excel not updated yet ({err}). "
                   "It stays queued — use “Write pending entries to Excel now” in the history.")


def show_form_message(key):
    msg = st.session_state.pop(key, None)
    if msg:
        (st.success if msg[0] else st.warning)(msg[1])


def show_stock_in():
    st.markdown("## 📥 Stock IN")
    st.caption("Parts received into a hub — from OEM, a local shop, or removed from rental vehicles")
    st.markdown("---")
    hubs = entry_hubs("Stock IN")
    tabs = st.tabs((["➕ Receive stock"] if hubs else []) + ["📋 Received history"])
    if hubs:
        with tabs[0]:
            receive_form(hubs)
    with tabs[-1]:
        show_moves("IN")


def receive_form(hubs):
    show_form_message("si_msg")
    n = st.session_state.setdefault("si_n", 0)
    names = hub_names()
    st.caption("Parts from another FleetCo hub? Use **Stock OUT → 🔁 Transfer** — it enters both sides.")
    with st.form(f"si_form_{n}"):
        c1, c2, c3 = st.columns(3)
        hub = c1.selectbox("Hub *", hubs, format_func=names.get, disabled=len(hubs) == 1)
        day = c2.date_input("Date received *", value=now_ist().date(), max_value=now_ist().date(), format="DD-MM-YYYY")
        source = c3.selectbox("Source *", inventory.SOURCES, accept_new_options=True)
        c4, c5 = st.columns(2)
        ref = c4.text_input("Ref No. (PO / bill / note)")
        incharge = c5.text_input("In-charge (responsible) *", value=st.session_state.full_name)
        lines, half = lines_editor(f"si_lines_{n}")
        ok = st.form_submit_button("💾 Save — portal + Excel", type="primary", width="stretch")
    if ok:
        if not lines or half:
            st.warning("⚠️ Each line needs a part AND a quantity." if half else "⚠️ Add at least one part.")
        elif not source or not incharge.strip():
            st.warning("⚠️ Source and in-charge are required.")
        else:
            rows = [{"hub": hub, "direction": "IN", "move_date": day, "part_code": p, "qty": q, "source": source,
                     "ref_no": ref.strip() or None, "in_charge": incharge.strip()} for p, q in lines]
            ids, res = save_moves(rows)
            audit("CREATE", "inv_moves", ids[0], f"Stock IN {hub}: {len(rows)} line(s), {sum(q for _, q in lines)} pcs "
                                                  f"from {source}")
            st.session_state.si_msg = save_message(f"{sum(q for _, q in lines)} pcs received at {names[hub]}", ids, res)
            st.session_state.si_n = n + 1
            st.rerun()


def show_stock_out():
    st.markdown("## 📤 Stock OUT")
    st.caption("Parts issued from a hub — to a technician for a vehicle, or sent to another FleetCo hub")
    st.markdown("---")
    hubs = entry_hubs("Stock OUT")
    tabs = st.tabs((["➖ Issue parts", "🔁 Transfer to another hub"] if hubs else []) + ["📋 Issued history"])
    if hubs:
        with tabs[0]:
            issue_form(hubs)
        with tabs[1]:
            transfer_form(hubs)
    with tabs[-1]:
        show_moves("OUT")


@st.cache_data(ttl=300, show_spinner=False)
def known_technicians():
    d = run_query("""SELECT technician FROM inv_moves WHERE technician IS NOT NULL
                     GROUP BY technician ORDER BY COUNT(*) DESC""")
    return d["technician"].tolist() if not d.empty else []


VEHICLE_PURPOSES = {"Vehicle Repair", "Complaint Rectification", "Preventive Maintenance"}


def issue_form(hubs):
    show_form_message("so_msg")
    n = st.session_state.setdefault("so_n", 0)
    names = hub_names()
    with st.form(f"so_form_{n}"):
        c1, c2, c3 = st.columns(3)
        hub = c1.selectbox("Hub *", hubs, format_func=names.get, disabled=len(hubs) == 1)
        day = c2.date_input("Date issued *", value=now_ist().date(), max_value=now_ist().date(), format="DD-MM-YYYY")
        purpose = c3.selectbox("Purpose *", inventory.PURPOSES, accept_new_options=True)
        c4, c5, c6 = st.columns(3)
        issued_for = c4.selectbox("Issued for *", inventory.ISSUED_FOR, accept_new_options=True)
        tech = c5.selectbox("Issued to (technician) *", known_technicians(), index=None, accept_new_options=True,
                            placeholder="Choose or type a name")
        chassis = c6.text_input("Vehicle / chassis no.", help="Needed for repairs — links the parts to the job card")
        c7, c8 = st.columns(2)
        incharge = c7.text_input("Issued by (in-charge) *", value=st.session_state.full_name)
        remarks = c8.text_input("Remarks")
        lines, half = lines_editor(f"so_lines_{n}")
        ok = st.form_submit_button("💾 Save — portal + Excel", type="primary", width="stretch")
    if ok:
        ch = inventory.chassis_key(chassis)
        if not lines or half:
            st.warning("⚠️ Each line needs a part AND a quantity." if half else "⚠️ Add at least one part.")
        elif not (purpose and issued_for and tech and incharge.strip()):
            st.warning("⚠️ Purpose, issued for, technician and issued by are required.")
        elif purpose in VEHICLE_PURPOSES and not ch:
            st.warning(f"⚠️ “{purpose}” needs the vehicle's chassis number.")
        else:
            rows = [{"hub": hub, "direction": "OUT", "move_date": day, "part_code": p, "qty": q, "purpose": purpose,
                     "issued_for": issued_for, "technician": tech.strip(), "chassis_number": ch,
                     "remarks": remarks.strip() or None, "in_charge": incharge.strip()} for p, q in lines]
            ids, res = save_moves(rows, check_hub_stock=hub)
            if ids is None:
                st.error(f"❌ {res}")
                return
            audit("CREATE", "inv_moves", ids[0], f"Stock OUT {hub}: {len(rows)} line(s) to {tech} ({ch or '-'})")
            known_technicians.clear()
            st.session_state.so_msg = save_message(f"{sum(q for _, q in lines)} pcs issued from {names[hub]}", ids, res)
            st.session_state.so_n = n + 1
            st.rerun()


def transfer_form(hubs):
    show_form_message("tr_msg")
    n = st.session_state.setdefault("tr_n", 0)
    names, xl = hub_names(), hub_excel_names()
    st.caption("One entry does both sides: an OUT at the sending hub and an IN at the receiving hub "
               "(both written to their Excel).")
    with st.form(f"tr_form_{n}"):
        c1, c2, c3 = st.columns(3)
        src = c1.selectbox("From hub *", hubs, format_func=names.get, disabled=len(hubs) == 1)
        dst = c2.selectbox("To hub *", list(names), index=None, format_func=names.get, placeholder="Choose hub")
        day = c3.date_input("Date sent *", value=now_ist().date(), max_value=now_ist().date(), format="DD-MM-YYYY")
        c4, c5 = st.columns(2)
        incharge = c4.text_input("Sent by (in-charge) *", value=st.session_state.full_name)
        remarks = c5.text_input("Remarks (courier / DC no.)")
        lines, half = lines_editor(f"tr_lines_{n}")
        ok = st.form_submit_button("🔁 Transfer — portal + both Excels", type="primary", width="stretch")
    if ok:
        if not lines or half:
            st.warning("⚠️ Each line needs a part AND a quantity." if half else "⚠️ Add at least one part.")
        elif not dst or dst == src:
            st.warning("⚠️ Choose a different hub to send to.")
        elif not incharge.strip():
            st.warning("⚠️ Sent by is required.")
        else:
            tid = int(run_query("SELECT nextval('inv_transfer_seq') AS n")["n"].iloc[0])
            note = f"Transfer TR-{tid}" + (f" · {remarks.strip()}" if remarks.strip() else "")
            rows = [{"hub": src, "direction": "OUT", "move_date": day, "part_code": p, "qty": q,
                     "purpose": inventory.transfer_purpose(src), "issued_for": xl[dst], "technician": incharge.strip(),
                     "remarks": note, "in_charge": incharge.strip(), "transfer_id": tid} for p, q in lines]
            rows += [{"hub": dst, "direction": "IN", "move_date": day, "part_code": p, "qty": q, "source": xl[src],
                      "ref_no": f"TR-{tid}", "in_charge": incharge.strip(), "transfer_id": tid} for p, q in lines]
            ids, res = save_moves(rows, check_hub_stock=src)
            if ids is None:
                st.error(f"❌ {res}")
                return
            audit("CREATE", "inv_moves", ids[0], f"Transfer TR-{tid}: {src} → {dst}, {len(lines)} part(s)")
            st.session_state.tr_msg = save_message(
                f"TR-{tid}: {sum(q for _, q in lines)} pcs {names[src]} → {names[dst]}", ids, res)
            st.session_state.tr_n = n + 1
            st.rerun()


def show_job_stock(job_id):
    """Parts the store issued for this job card (same chassis, issued around the job card date)."""
    d = run_query("""SELECT m.move_date, m.hub, m.part_code, p.description, m.qty, m.unit_cost, m.technician
                     FROM inv_moves m JOIN inv_parts p USING (part_code)
                     WHERE m.job_card_id = :i AND m.direction = 'OUT' ORDER BY m.move_date, m.id""", {"i": job_id})
    if d.empty:
        return
    st.markdown("**🔩 Parts issued from stock for this vehicle** (store's Stock OUT, same chassis)")
    show_table(pd.DataFrame({"Date": fmt_date(d["move_date"]), "Hub": d["hub"], "Code": d["part_code"],
                             "Part": d["description"], "Qty": d["qty"],
                             "Value ₹ (landing)": (money_col(d["unit_cost"]) * d["qty"]).round(2),
                             "Technician": d["technician"].fillna("")}),
               height=min(60 + 38 * len(d), 300))

# ════════════════════════════════════════════════════════════════════
# REPORTS PAGE — FleetCo Service Bizops
# ════════════════════════════════════════════════════════════════════
def show_reports():
    import plotly.express as px
    import plotly.graph_objects as go
    from datetime import date, timedelta

    st.markdown("""
    <h2 style="color:#1B3A6B; font-size:24px; font-weight:700; margin-bottom:4px;">
        📈 Reports & Analytics
    </h2>
    <p style="color:#475569; font-size:14px; margin-bottom:4px;">
        Parts Revenue · RCA · Spare Usage · Financial Summary
    </p>

    """, unsafe_allow_html=True)

    st.markdown("---")

    # ── TIME PERIOD SLICER ─────────────────────────────────────────
    st.markdown("""
    <p style="color:#1B3A6B; font-size:14px; font-weight:600; margin-bottom:8px;">
        🗓️ Time Period Slicer — Applies to ALL reports below</p>
    """, unsafe_allow_html=True)

    sc1, sc2 = st.columns([1, 1])
    with sc1:
        period_type = st.radio(
            "Group By",
            ["Monthly", "Weekly"],
            horizontal=True,
            key="rpt_period"
        )
    with sc2:
        months_back = st.select_slider(
            "Show Last",
            options=[1, 2, 3, 6, 12],
            value=3,
            key="rpt_months",
            format_func=lambda x: f"{x} Month{'s' if x > 1 else ''}"
        )

    end_date   = date.today()
    start_date = end_date - timedelta(days=months_back * 30)
    period_fmt = "YYYY-MM" if period_type == "Monthly" else "IYYY-IW"
    period_lbl = "Month" if period_type == "Monthly" else "Week"

    st.markdown(f"""
    <div style="background:#EFF6FF; border:1px solid #BFDBFE; border-radius:8px;
                padding:8px 16px; margin-bottom:20px;">
        <span style="color:#1B3A6B; font-size:13px;">
            📅 Showing: <b>{start_date.strftime('%d %b %Y')}</b>
            to <b>{end_date.strftime('%d %b %Y')}</b>
            — Grouped by <b>{period_lbl}</b>
        </span>
    </div>
    """, unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════════════
    # SECTION 1 — REVENUE & MARGIN SUMMARY
    # ════════════════════════════════════════════════════════════════
    st.markdown("""
    <div style="background:linear-gradient(135deg,#1B3A6B,#0F2347);
                border-radius:12px; padding:14px 20px; margin-bottom:16px;">
        <h3 style="color:white; margin:0; font-size:17px;">💰 Revenue & Margin Summary</h3>
        <p style="color:rgba(255,255,255,0.6); margin:4px 0 0; font-size:12px;">
            What parts we gave · What we charged · What we earned (margin)
        </p>
    </div>
    """, unsafe_allow_html=True)

    # KPIs — Rental Fleet Parts
    rental_kpi = run_query(f"""
        SELECT
            COALESCE(SUM(so.quantity),0)        AS total_parts_issued,
            COALESCE(SUM(so.total_cost),0)      AS total_cost,
            COALESCE(SUM(so.total_billing),0)   AS total_charged,
            COALESCE(SUM(so.total_billing - so.total_cost),0) AS total_margin
        FROM stock_out so
        WHERE so.issue_date BETWEEN '{start_date}' AND '{end_date}'
    """)

    b2b_kpi = run_query(f"""
        SELECT
            COALESCE(SUM(csi.quantity),0)       AS total_parts_dispatched,
            COALESCE(SUM(csi.total_cost),0)     AS total_cost,
            COALESCE(SUM(csi.total_amount),0)   AS total_charged,
            COALESCE(SUM(csi.margin),0)         AS total_margin
        FROM counter_sale_items csi
        JOIN counter_sales cs ON csi.cs_id = cs.cs_id
        WHERE cs.cs_date BETWEEN '{start_date}' AND '{end_date}'
    """)

    # Show 4 summary cards
    # Safely extract scalar values from DataFrames
    r_cost     = float(rental_kpi['total_cost'].iloc[0])    if not rental_kpi.empty else 0
    r_charged  = float(rental_kpi['total_charged'].iloc[0]) if not rental_kpi.empty else 0
    r_margin   = float(rental_kpi['total_margin'].iloc[0])  if not rental_kpi.empty else 0
    r_qty      = float(rental_kpi['total_parts_issued'].iloc[0]) if not rental_kpi.empty else 0

    b_cost     = float(b2b_kpi['total_cost'].iloc[0])              if not b2b_kpi.empty else 0
    b_charged  = float(b2b_kpi['total_charged'].iloc[0])           if not b2b_kpi.empty else 0
    b_margin   = float(b2b_kpi['total_margin'].iloc[0])            if not b2b_kpi.empty else 0
    b_qty      = float(b2b_kpi['total_parts_dispatched'].iloc[0])  if not b2b_kpi.empty else 0

    total_cost    = r_cost    + b_cost
    total_charged = r_charged + b_charged
    total_margin  = r_margin  + b_margin
    total_qty     = int(r_qty + b_qty)
    margin_pct    = (total_margin / total_cost * 100) if total_cost > 0 else 0

    k1, k2, k3, k4 = st.columns(4)
    for col, icon, label, value, color, bg in [
        (k1, "🛒", "Total Parts Given",  f"{total_qty} units", "#1B3A6B","#EFF6FF"),
        (k2, "💸", "Our Cost (OEM)",     f"Rs {int(total_cost):,}",    "#EF4444","#FEF2F2"),
        (k3, "💰", "We Charged",         f"Rs {int(total_charged):,}", "#2E7D32","#F0FDF4"),
        (k4, "📈", "Our Margin Profit",  f"Rs {int(total_margin):,} ({margin_pct:.1f}%)", "#E87722","#FFF7ED"),
    ]:
        col.markdown(f"""
        <div style="background:{bg}; border-radius:12px; padding:16px;
                    border:1px solid {color}44; text-align:center;
                    box-shadow:0 2px 8px rgba(0,0,0,0.05);">
            <div style="font-size:24px;">{icon}</div>
            <div style="color:#64748B; font-size:11px; margin-top:4px;">{label}</div>
            <div style="color:{color}; font-size:18px; font-weight:700; margin-top:4px;">
                {value}
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Chart: Rental vs B2B breakdown
    ch1, ch2 = st.columns(2)

    with ch1:
        # Simple comparison: Rental vs B2B
        compare_data = {
            "Segment":    ["Rental Fleet", "B2B Partners"],
            "Our Cost":   [r_cost,    b_cost],
            "We Charged": [r_charged, b_charged],
            "Margin":     [r_margin,  b_margin]
        }
        import pandas as pd
        df_compare = pd.DataFrame(compare_data)
        fig1 = go.Figure()
        fig1.add_trace(go.Bar(
            name="Our Cost (what we paid OEM)",
            x=df_compare["Segment"], y=df_compare["Our Cost"],
            marker_color="#EF4444", text=df_compare["Our Cost"].apply(lambda x: f"Rs {int(x):,}"),
            textposition="inside"
        ))
        fig1.add_trace(go.Bar(
            name="We Charged (Revenue)",
            x=df_compare["Segment"], y=df_compare["We Charged"],
            marker_color="#2E7D32", text=df_compare["We Charged"].apply(lambda x: f"Rs {int(x):,}"),
            textposition="inside"
        ))
        fig1.add_trace(go.Bar(
            name="Our Margin Profit",
            x=df_compare["Segment"], y=df_compare["Margin"],
            marker_color="#1B3A6B", text=df_compare["Margin"].apply(lambda x: f"Rs {int(x):,}"),
            textposition="inside"
        ))
        fig1.update_layout(
            title="Rental Fleet vs B2B: Cost → Revenue → Margin",
            barmode="group", height=360,
            plot_bgcolor="white", paper_bgcolor="white",
            font=dict(family="Arial", size=12),
            yaxis_title="Amount (Rs)",
            legend=dict(orientation="h", y=1.15),
            annotations=[dict(
                text="📌 Margin = Revenue − Cost = Our Profit",
                xref="paper", yref="paper", x=0, y=-0.15,
                showarrow=False, font=dict(size=10, color="#64748B")
            )]
        )
        st.plotly_chart(fig1, width='stretch')

    with ch2:
        # Period-wise margin trend
        margin_trend = run_query(f"""
            SELECT period, segment, SUM(margin) AS margin FROM (
                SELECT
                    TO_CHAR(so.issue_date, '{period_fmt}') AS period,
                    'Rental Fleet' AS segment,
                    (so.total_billing - so.total_cost) AS margin
                FROM stock_out so
                WHERE so.issue_date BETWEEN '{start_date}' AND '{end_date}'
                UNION ALL
                SELECT
                    TO_CHAR(cs.cs_date, '{period_fmt}') AS period,
                    'B2B Partners' AS segment,
                    csi.margin AS margin
                FROM counter_sale_items csi
                JOIN counter_sales cs ON csi.cs_id = cs.cs_id
                WHERE cs.cs_date BETWEEN '{start_date}' AND '{end_date}'
            ) t
            GROUP BY period, segment
            ORDER BY period
        """)
        if not margin_trend.empty:
            # FIX: Convert period to string → forces category axis not timestamp
            margin_trend["period"] = margin_trend["period"].astype(str)

            # Pivot for side-by-side grouped bar
            import pandas as pd
            pivot = margin_trend.pivot_table(
                index="period", columns="segment", values="margin", aggfunc="sum"
            ).reset_index().fillna(0)

            fig2 = go.Figure()
            colors = {"Rental Fleet": "#1B3A6B", "B2B Partners": "#2E7D32"}
            for seg in [c for c in pivot.columns if c != "period"]:
                fig2.add_trace(go.Bar(
                    name=seg,
                    x=pivot["period"],
                    y=pivot[seg],
                    marker_color=colors.get(seg, "#0EA5E9"),
                    text=pivot[seg].apply(lambda v: f"Rs {int(v):,}"),
                    textposition="outside",
                    textfont=dict(size=11)
                ))
            fig2.update_layout(
                title=f"Our Margin Profit — {period_lbl}-wise (Rental Fleet vs B2B)",
                barmode="group",
                plot_bgcolor="white", paper_bgcolor="white",
                height=360, font=dict(family="Arial", size=12),
                xaxis=dict(type="category", title=period_lbl,
                           tickangle=-30 if len(pivot) > 4 else 0),
                yaxis=dict(title="Margin Profit (Rs)"),
                legend=dict(orientation="h", y=1.15),
                annotations=[dict(
                    text="📌 Taller bar = More profit earned that period",
                    xref="paper", yref="paper", x=0, y=-0.18,
                    showarrow=False, font=dict(size=10, color="#64748B")
                )]
            )
            st.plotly_chart(fig2, width="stretch")
        else:
            st.info("No margin data for selected period — try increasing the date range")


    # B2B Partner wise revenue
    b2b_partner = run_query(f"""
        SELECT
            cs.b2b_partner              AS "B2B Partner",
            COUNT(DISTINCT cs.cs_id)    AS "Total Dispatches",
            SUM(csi.quantity)           AS "Parts Qty",
            SUM(csi.total_cost)         AS "Our Cost (Rs)",
            SUM(csi.total_amount)       AS "We Charged (Rs)",
            SUM(csi.margin)             AS "Our Margin (Rs)",
            ROUND(SUM(csi.margin)::numeric / NULLIF(SUM(csi.total_cost)::numeric,0) * 100, 1)
                                        AS "Margin %"
        FROM counter_sales cs
        JOIN counter_sale_items csi ON cs.cs_id = csi.cs_id
        WHERE cs.cs_date BETWEEN '{start_date}' AND '{end_date}'
        GROUP BY cs.b2b_partner
        ORDER BY "We Charged (Rs)" DESC
    """)
    if not b2b_partner.empty:
        st.markdown("""
        <p style="color:#1B3A6B; font-size:13px; font-weight:600; margin:8px 0 6px;">
            🏢 B2B Partner-wise Revenue Breakdown</p>
        """, unsafe_allow_html=True)
        show_table(b2b_partner)
        download_excel(b2b_partner, "B2B_Revenue")

    st.markdown("<br><br>", unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════════════
    # SECTION 2 — RCA (Most Problematic Cases)
    # ════════════════════════════════════════════════════════════════
    st.markdown("""
    <div style="background:linear-gradient(135deg,#7C3AED,#5B21B6);
                border-radius:12px; padding:14px 20px; margin-bottom:16px;">
        <h3 style="color:white; margin:0; font-size:17px;">🔍 RCA — Root Cause Analysis</h3>
        <p style="color:rgba(255,255,255,0.6); margin:4px 0 0; font-size:12px;">
            Which issues happen most? Which vehicles break down repeatedly?
        </p>
    </div>
    """, unsafe_allow_html=True)

    rca1, rca2 = st.columns(2)

    with rca1:
        rca_data = run_query(f"""
            SELECT
                complaint_category          AS "Issue Type",
                COUNT(*)                    AS "No. of Cases",
                COUNT(DISTINCT vehicle_id)  AS "Vehicles Affected"
            FROM job_cards
            WHERE job_date BETWEEN '{start_date}' AND '{end_date}'
                AND complaint_category IS NOT NULL
            GROUP BY complaint_category
            ORDER BY "No. of Cases" DESC
        """)
        if not rca_data.empty:
            fig3 = px.bar(
                rca_data,
                x="No. of Cases",
                y="Issue Type",
                orientation="h",
                title="Most Common Issues (How many times each problem occurred)",
                color="No. of Cases",
                color_continuous_scale=["#C4B5FD","#7C3AED"],
                text="No. of Cases"
            )
            fig3.update_traces(textposition="outside")
            fig3.update_layout(
                plot_bgcolor="white", paper_bgcolor="white",
                height=350, showlegend=False,
                font=dict(family="Arial", size=12),
                yaxis=dict(categoryorder="total ascending"),
                xaxis_title="Number of Times This Issue Occurred",
                annotations=[dict(
                    text="📌 Longest bar = most frequent problem to fix first!",
                    xref="paper", yref="paper", x=0, y=-0.18,
                    showarrow=False, font=dict(size=10, color="#64748B")
                )]
            )
            st.plotly_chart(fig3, width='stretch')

            # Show as table too
            show_table(rca_data)
        else:
            st.info("No job card data for selected period")

    with rca2:
        # Vehicles with most breakdowns
        repeat_vehicles = run_query(f"""
            SELECT
                f.vehicle_number            AS "Vehicle",
                f.vehicle_model             AS "Model",
                COUNT(j.job_card_id)        AS "Times in Service",
                STRING_AGG(
                    DISTINCT j.complaint_category,
                    ', ' ORDER BY j.complaint_category
                )                           AS "Issues Faced"
            FROM job_cards j
            JOIN rental_fleet f ON j.vehicle_id = f.vehicle_id
            WHERE j.job_date BETWEEN '{start_date}' AND '{end_date}'
            GROUP BY f.vehicle_id, f.vehicle_number, f.vehicle_model
            HAVING COUNT(j.job_card_id) >= 1
            ORDER BY "Times in Service" DESC
            LIMIT 10
        """)
        if not repeat_vehicles.empty:
            fig4 = px.bar(
                repeat_vehicles,
                x="Vehicle",
                y="Times in Service",
                title="Top 10 Vehicles — How many times sent for service",
                color="Times in Service",
                color_continuous_scale=["#FDE68A","#EF4444"],
                text="Times in Service"
            )
            fig4.update_traces(textposition="outside")
            fig4.update_layout(
                plot_bgcolor="white", paper_bgcolor="white",
                height=280, showlegend=False,
                font=dict(family="Arial", size=11),
                yaxis_title="No. of Service Visits",
                xaxis_title="Vehicle Number",
                annotations=[dict(
                    text="📌 Red bars = vehicles needing most attention",
                    xref="paper", yref="paper", x=0, y=-0.22,
                    showarrow=False, font=dict(size=10, color="#64748B")
                )]
            )
            st.plotly_chart(fig4, width='stretch')
            show_table(repeat_vehicles)

    st.markdown("<br><br>", unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════════════
    # SECTION 3 — HIGH SPARES USAGE
    # ════════════════════════════════════════════════════════════════
    st.markdown("""
    <div style="background:linear-gradient(135deg,#0EA5E9,#0284C7);
                border-radius:12px; padding:14px 20px; margin-bottom:16px;">
        <h3 style="color:white; margin:0; font-size:17px;">📦 Spare Parts Usage Analysis</h3>
        <p style="color:rgba(255,255,255,0.6); margin:4px 0 0; font-size:12px;">
            Which parts are used most? Which category consumes our stock fastest?
        </p>
    </div>
    """, unsafe_allow_html=True)

    sp1, sp2 = st.columns(2)

    with sp1:
        top_parts = run_query(f"""
            SELECT
                p.part_name         AS "Part Name",
                p.category          AS "Category",
                SUM(so.quantity)    AS "Total Used",
                SUM(so.total_cost)  AS "Total We Paid (Rs)",
                SUM(so.total_billing) AS "Total We Charged (Rs)",
                SUM(so.total_billing - so.total_cost) AS "Total Margin (Rs)"
            FROM stock_out so
            JOIN parts_master p ON so.part_id = p.part_id
            WHERE so.issue_date BETWEEN '{start_date}' AND '{end_date}'
            GROUP BY p.part_id, p.part_name, p.category
            ORDER BY "Total Used" DESC
            LIMIT 10
        """)
        if not top_parts.empty:
            fig5 = px.bar(
                top_parts,
                x="Total Used",
                y="Part Name",
                orientation="h",
                color="Category",
                title="Top 10 Most Used Spare Parts (by quantity)",
                text="Total Used",
                color_discrete_sequence=["#0EA5E9","#1B3A6B","#2E7D32","#E87722","#8B5CF6"]
            )
            fig5.update_traces(textposition="outside")
            fig5.update_layout(
                plot_bgcolor="white", paper_bgcolor="white",
                height=380, font=dict(family="Arial", size=11),
                yaxis=dict(categoryorder="total ascending"),
                xaxis_title="Quantity Used",
                legend=dict(orientation="h", y=1.15),
                annotations=[dict(
                    text="📌 These parts need to always be in stock!",
                    xref="paper", yref="paper", x=0, y=-0.15,
                    showarrow=False, font=dict(size=10, color="#64748B")
                )]
            )
            st.plotly_chart(fig5, width='stretch')
        else:
            st.info("No spare usage data for selected period")

    with sp2:
        cat_usage = run_query(f"""
            SELECT
                p.category              AS "Category",
                SUM(so.quantity)        AS qty,
                SUM(so.total_cost)      AS cost
            FROM stock_out so
            JOIN parts_master p ON so.part_id = p.part_id
            WHERE so.issue_date BETWEEN '{start_date}' AND '{end_date}'
            GROUP BY p.category
            ORDER BY qty DESC
        """)
        if not cat_usage.empty:
            fig6 = px.pie(
                cat_usage,
                values="qty",
                names="Category",
                title="Which Category of Parts Used Most?",
                color_discrete_sequence=["#1B3A6B","#2E7D32","#0EA5E9","#E87722","#8B5CF6","#EF4444"],
                hole=0.45
            )
            fig6.update_layout(
                font=dict(family="Arial", size=12), height=380,
                legend=dict(orientation="v", x=1.05, y=0.5),
                annotations=[
                    dict(text="Parts Usage", x=0.5, y=0.5,
                         font=dict(size=12, color="#1B3A6B"), showarrow=False),
                    dict(
                        text="📌 Biggest slice = category you use most",
                        xref="paper", yref="paper", x=0, y=-0.1,
                        showarrow=False, font=dict(size=10, color="#64748B")
                    )
                ]
            )
            fig6.update_traces(textposition="inside", textinfo="percent+label")
            st.plotly_chart(fig6, width='stretch')

    # Parts usage table
    if not top_parts.empty:
        st.markdown("""
        <p style="color:#0EA5E9; font-size:13px; font-weight:600; margin-bottom:6px;">
            📋 Spare Parts Detail — What we gave, what it cost us, what we earned</p>
        """, unsafe_allow_html=True)
        show_table(top_parts)
        download_excel(top_parts, "Spare_Parts_Usage")

    st.markdown("<br><br>", unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════════════
    # SECTION 4 — FINANCIAL SUMMARY (Simple P&L)
    # ════════════════════════════════════════════════════════════════
    st.markdown("""
    <div style="background:linear-gradient(135deg,#2E7D32,#166534);
                border-radius:12px; padding:14px 20px; margin-bottom:16px;">
        <h3 style="color:white; margin:0; font-size:17px;">💹 Financial Summary (Internal Tracking)</h3>
        <p style="color:rgba(255,255,255,0.6); margin:4px 0 0; font-size:12px;">
            What we spent · What we should collect · Our margin profit
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Simple explanation box
    st.markdown("""
    <div style="background:#F0FDF4; border:1px solid #BBF7D0; border-radius:10px;
                padding:12px 20px; margin-bottom:16px;">
        <p style="color:#166534; font-size:13px; margin:0; line-height:1.8;">
            <b>How to read this:</b><br>
            🔴 <b>Our Cost</b> = Money we spent buying parts from OEM<br>
            🟢 <b>We Charged</b> = Amount customer/B2B partner should pay us for those parts<br>
            🔵 <b>Our Margin</b> = We Charged − Our Cost = Our PROFIT on parts<br>
            <i>Note: We only track values here. Actual payment collection is handled by Accounts team.</i>
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Period-wise financial trend
    fin_trend = run_query(f"""
        SELECT period, SUM(our_cost) AS our_cost,
               SUM(we_charged) AS we_charged,
               SUM(our_margin) AS our_margin
        FROM (
            SELECT TO_CHAR(so.issue_date, '{period_fmt}') AS period,
                   so.total_cost    AS our_cost,
                   so.total_billing AS we_charged,
                   (so.total_billing - so.total_cost) AS our_margin
            FROM stock_out so
            WHERE so.issue_date BETWEEN '{start_date}' AND '{end_date}'
            UNION ALL
            SELECT TO_CHAR(cs.cs_date, '{period_fmt}') AS period,
                   csi.total_cost   AS our_cost,
                   csi.total_amount AS we_charged,
                   csi.margin       AS our_margin
            FROM counter_sale_items csi
            JOIN counter_sales cs ON csi.cs_id = cs.cs_id
            WHERE cs.cs_date BETWEEN '{start_date}' AND '{end_date}'
        ) t
        GROUP BY period
        ORDER BY period
    """)

    if not fin_trend.empty:
        # FIX: Convert period to string → forces category axis not timestamp
        fin_trend["period"] = fin_trend["period"].astype(str)

        # Chart: Simple horizontal bar for easy comparison
        fig7 = go.Figure()

        # Add bars side by side
        fig7.add_trace(go.Bar(
            name="Our Cost (paid to OEM)",
            x=fin_trend["period"],
            y=fin_trend["our_cost"],
            marker_color="#EF4444",
            text=fin_trend["our_cost"].apply(lambda x: f"Rs {int(x):,}"),
            textposition="auto",
            textfont=dict(color="white", size=11)
        ))
        fig7.add_trace(go.Bar(
            name="We Charged (Revenue)",
            x=fin_trend["period"],
            y=fin_trend["we_charged"],
            marker_color="#2E7D32",
            text=fin_trend["we_charged"].apply(lambda x: f"Rs {int(x):,}"),
            textposition="auto",
            textfont=dict(color="white", size=11)
        ))
        fig7.add_trace(go.Bar(
            name="Our Margin Profit",
            x=fin_trend["period"],
            y=fin_trend["our_margin"],
            marker_color="#1B3A6B",
            text=fin_trend["our_margin"].apply(lambda x: f"Rs {int(x):,}"),
            textposition="auto",
            textfont=dict(color="white", size=11)
        ))
        fig7.update_layout(
            title=f"Cost vs Revenue vs Margin — {period_lbl}-wise",
            barmode="group",
            plot_bgcolor="white", paper_bgcolor="white",
            height=400, font=dict(family="Arial", size=12),
            xaxis=dict(
                type="category",
                title=period_lbl,
                tickangle=-30 if len(fin_trend) > 4 else 0
            ),
            yaxis=dict(title="Amount (Rs)"),
            legend=dict(orientation="h", y=1.15),
            annotations=[dict(
                text="📌 Green bar > Red bar = We made profit! | Blue = Margin amount",
                xref="paper", yref="paper", x=0, y=-0.18,
                showarrow=False, font=dict(size=10, color="#1B3A6B")
            )]
        )
        st.plotly_chart(fig7, width="stretch")


        # Financial summary table
        import pandas as pd
        fin_table = fin_trend.copy()
        fin_table.columns = [period_lbl, "Our Cost (Rs)", "We Charged (Rs)", "Our Margin (Rs)"]
        fin_table["Our Cost (Rs)"]    = fin_table["Our Cost (Rs)"].apply(lambda x: int(x))
        fin_table["We Charged (Rs)"]  = fin_table["We Charged (Rs)"].apply(lambda x: int(x))
        fin_table["Our Margin (Rs)"]  = fin_table["Our Margin (Rs)"].apply(lambda x: int(x))

        st.markdown("""
        <p style="color:#2E7D32; font-size:13px; font-weight:600; margin:12px 0 6px;">
            📋 Financial Summary Table</p>
        """, unsafe_allow_html=True)
        show_table(fin_table)
        download_excel(fin_table, "Financial_Summary")

        # Grand total row
        gt1, gt2, gt3 = st.columns(3)
        total_c = int(fin_trend["our_cost"].sum())
        total_r = int(fin_trend["we_charged"].sum())
        total_m = int(fin_trend["our_margin"].sum())
        mpct    = round(total_m / total_c * 100, 1) if total_c > 0 else 0

        for col, label, val, color, bg in [
            (gt1, "Total We Spent (OEM Cost)", f"Rs {total_c:,}", "#EF4444","#FEF2F2"),
            (gt2, "Total We Should Collect",   f"Rs {total_r:,}", "#2E7D32","#F0FDF4"),
            (gt3, f"Total Margin Profit ({mpct}%)", f"Rs {total_m:,}", "#1B3A6B","#EFF6FF"),
        ]:
            col.markdown(f"""
            <div style="background:{bg}; border:1px solid {color}44; border-radius:12px;
                        padding:16px; text-align:center; margin-top:12px;
                        box-shadow:0 2px 8px rgba(0,0,0,0.05);">
                <div style="color:#64748B; font-size:12px;">{label}</div>
                <div style="color:{color}; font-size:22px; font-weight:700; margin-top:4px;">
                    {val}
                </div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("No financial data for selected period")

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("""
    <div style="text-align:center; padding:12px; color:#94A3B8; font-size:11px;">
        📊 All charts update automatically when you change the time slicer at the top
        · Data is for internal tracking only · Accounts team handles actual invoicing
    </div>
    """, unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════
# MAIN ROUTER
# ════════════════════════════════════════════════════════════════════
def main():
    if not st.session_state.logged_in:
        show_login()
    elif st.session_state.must_change_password:
        # first login with a temporary password → must set own password
        show_change_password(first_login=True)
    else:
        show_topbar()
        show_sidebar()
        # never render a page the role isn't allowed to open
        if not page_access(st.session_state.page):
            st.session_state.page = allowed_pages()[0][1]
        p = st.session_state.page
        if   p == "Change Password":  show_change_password()
        elif p == "Users":            show_users()
        elif p == "Dashboard":        show_dashboard()
        elif p == "Fleet":            show_fleet()
        elif p == "Parts Master":     show_parts()
        elif p == "Stock IN":         show_stock_in()
        elif p == "Stock OUT":        show_stock_out()
        elif p == "Job Cards":        show_jobs()
        elif p == "Overview":         show_overview()
        elif p == "Raise Complaint":  show_raise_complaint()
        elif p == "My Vehicles":      show_my_vehicles()
        elif p == "Tickets":          show_tickets()
        elif p == "Service History":  show_service_history()
        elif p == "Reports":          show_reports()

if __name__ == "__main__":
    main()
