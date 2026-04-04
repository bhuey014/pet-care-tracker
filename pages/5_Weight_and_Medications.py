import streamlit as st
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import date, datetime
from contextlib import contextmanager

# ──────────────────────────────────────────────
# DB HELPERS
# ──────────────────────────────────────────────

@contextmanager
def get_conn():
    conn = psycopg2.connect(st.secrets["DB_URL"])
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def fetch_all(query: str, params=None):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params or ())
            return cur.fetchall()


def execute(query: str, params=None):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params or ())


def fetch_pets():
    return fetch_all("SELECT id, name, species FROM pets ORDER BY name")


def pet_label(p):
    return f"{p['name']} ({p['species']})"


# ──────────────────────────────────────────────
# SESSION STATE INIT
# ──────────────────────────────────────────────

for key, default in {
    "wl_delete_confirm_id": None,   # weight log pending delete
    "med_delete_confirm_id": None,  # medication pending delete
    "med_editing_id": None,         # medication being edited
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


# ──────────────────────────────────────────────
# PAGE CONFIG
# ──────────────────────────────────────────────

st.set_page_config(page_title="Weight & Medications", layout="wide")

st.markdown("""
<style>
    /* ── global tokens ── */
    :root {
        --clr-bg:        #F7F8FA;
        --clr-card:      #FFFFFF;
        --clr-border:    #E3E6ED;
        --clr-primary:   #3B6FE8;
        --clr-danger:    #E8503B;
        --clr-success:   #2EB67D;
        --clr-muted:     #8A93A6;
        --clr-text:      #1A1D27;
        --radius:        10px;
        --shadow:        0 2px 12px rgba(0,0,0,.07);
    }

    /* section divider */
    .section-header {
        font-size: 1.15rem;
        font-weight: 700;
        letter-spacing: .03em;
        color: var(--clr-text);
        border-left: 4px solid var(--clr-primary);
        padding: 6px 0 6px 12px;
        margin: 24px 0 16px;
    }

    /* subtle table row highlight */
    .stDataFrame tbody tr:hover { background: #F0F4FF !important; }

    /* compact error */
    div[data-testid="stAlert"] { border-radius: var(--radius); }

    /* action button row */
    .btn-row { display: flex; gap: 8px; }
</style>
""", unsafe_allow_html=True)

st.title("🐾 Weight & Medications")
st.caption("Track your pets' health history in one place.")

try:
    pets = fetch_pets()
except Exception as e:
    st.error(f"Could not load pets: {e}")
    st.stop()

pet_options = {p["id"]: pet_label(p) for p in pets}
pet_id_list = list(pet_options.keys())

# ══════════════════════════════════════════════
#  SECTION 1 — WEIGHT TRACKING
# ══════════════════════════════════════════════

st.markdown('<div class="section-header">⚖️ Section 1 — Weight Tracking</div>',
            unsafe_allow_html=True)

# ── Log Weight form ──────────────────────────

with st.expander("➕ Log a New Weight", expanded=False):
    with st.form("form_log_weight", clear_on_submit=True):
        st.subheader("Log Weight")

        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            wf_pet_id = st.selectbox(
                "Pet *",
                options=pet_id_list,
                format_func=lambda pid: pet_options[pid],
                key="wf_pet",
            )
        with col2:
            wf_weight = st.number_input(
                "Weight (lbs) *",
                min_value=0.0, step=0.1, value=0.0,
                key="wf_weight",
            )
        with col3:
            wf_date = st.date_input(
                "Date *",
                value=date.today(),
                key="wf_date",
            )

        submitted_wl = st.form_submit_button("Save Weight Log", type="primary")

    if submitted_wl:
        errors = []
        if wf_pet_id is None:
            errors.append("Pet is required.")
        if wf_weight <= 0:
            errors.append("Weight must be a positive number.")
        if wf_date > date.today():
            errors.append("Date cannot be in the future.")

        if errors:
            st.error("\n\n".join(f"• {e}" for e in errors))
        else:
            try:
                execute(
                    "INSERT INTO weight_logs (pet_id, weight_lbs, logged_at) VALUES (%s, %s, %s)",
                    (wf_pet_id, wf_weight, wf_date),
                )
                st.success("Weight logged successfully!")
                st.rerun()
            except Exception as e:
                st.error(f"Database error: {e}")

# ── Filter + History ─────────────────────────

st.markdown("**Filter by Pet**")
wl_filter_options = ["All Pets"] + [pet_options[pid] for pid in pet_id_list]
wl_filter = st.selectbox(
    "Show weight logs for",
    options=wl_filter_options,
    key="wl_filter_pet",
    label_visibility="collapsed",
)

try:
    if wl_filter == "All Pets":
        wl_rows = fetch_all("""
            SELECT wl.id, p.name AS pet_name, wl.weight_lbs,
                   wl.logged_at::date AS date_logged
            FROM weight_logs wl
            JOIN pets p ON p.id = wl.pet_id
            ORDER BY wl.logged_at DESC
        """)
    else:
        # find pet_id from label
        selected_pid = next(
            pid for pid, lbl in pet_options.items() if lbl == wl_filter
        )
        wl_rows = fetch_all("""
            SELECT wl.id, p.name AS pet_name, wl.weight_lbs,
                   wl.logged_at::date AS date_logged
            FROM weight_logs wl
            JOIN pets p ON p.id = wl.pet_id
            WHERE wl.pet_id = %s
            ORDER BY wl.logged_at DESC
        """, (selected_pid,))
except Exception as e:
    st.error(f"Database error loading weight history: {e}")
    wl_rows = []

if not wl_rows:
    st.info("No weight logs found.")
else:
    st.markdown(f"**{len(wl_rows)} record(s)**")

    header_cols = st.columns([3, 2, 2, 1, 1])
    for col, label in zip(header_cols, ["Pet", "Weight (lbs)", "Date Logged", "", ""]):
        col.markdown(f"**{label}**")

    for row in wl_rows:
        rid = row["id"]
        c1, c2, c3, c4, c5 = st.columns([3, 2, 2, 1, 1])
        c1.write(row["pet_name"])
        c2.write(f"{float(row['weight_lbs']):.2f}")
        c3.write(str(row["date_logged"]))

        # Delete flow
        if st.session_state.wl_delete_confirm_id == rid:
            with c4:
                if st.button("✅ Confirm", key=f"wl_del_yes_{rid}"):
                    try:
                        execute("DELETE FROM weight_logs WHERE id = %s", (rid,))
                        st.session_state.wl_delete_confirm_id = None
                        st.rerun()
                    except Exception as e:
                        st.error(f"Delete failed: {e}")
            with c5:
                if st.button("❌ Cancel", key=f"wl_del_no_{rid}"):
                    st.session_state.wl_delete_confirm_id = None
                    st.rerun()
        else:
            with c4:
                if st.button("🗑 Delete", key=f"wl_del_{rid}"):
                    st.session_state.wl_delete_confirm_id = rid
                    st.rerun()

st.divider()

# ══════════════════════════════════════════════
#  SECTION 2 — MEDICATIONS
# ══════════════════════════════════════════════

st.markdown('<div class="section-header">💊 Section 2 — Medications</div>',
            unsafe_allow_html=True)

# ── Add Medication form ───────────────────────

with st.expander("➕ Add a New Medication", expanded=False):
    with st.form("form_add_med", clear_on_submit=True):
        st.subheader("Add Medication")

        col1, col2 = st.columns(2)
        with col1:
            mf_pet_id = st.selectbox(
                "Pet *",
                options=pet_id_list,
                format_func=lambda pid: pet_options[pid],
                key="mf_pet",
            )
            mf_name = st.text_input("Medication Name *", key="mf_name")
            mf_dosage = st.text_input("Dosage (optional)", key="mf_dosage")
        with col2:
            mf_frequency = st.text_input("Frequency (optional)", key="mf_frequency")
            mf_start = st.date_input("Start Date *", value=date.today(), key="mf_start")
            mf_end = st.date_input(
                "End Date (optional)",
                value=None,
                key="mf_end",
            )

        submitted_med = st.form_submit_button("Save Medication", type="primary")

    if submitted_med:
        errors = []
        if mf_pet_id is None:
            errors.append("Pet is required.")
        if not mf_name.strip():
            errors.append("Medication name is required.")
        if mf_start is None:
            errors.append("Start date is required.")
        if mf_end is not None and mf_start is not None and mf_end <= mf_start:
            errors.append("End date must be after start date.")

        if errors:
            st.error("\n\n".join(f"• {e}" for e in errors))
        else:
            try:
                execute(
                    """INSERT INTO medications
                       (pet_id, medication_name, dosage, frequency, start_date, end_date)
                       VALUES (%s, %s, %s, %s, %s, %s)""",
                    (
                        mf_pet_id,
                        mf_name.strip(),
                        mf_dosage.strip() or None,
                        mf_frequency.strip() or None,
                        mf_start,
                        mf_end,
                    ),
                )
                st.success("Medication saved successfully!")
                st.rerun()
            except Exception as e:
                st.error(f"Database error: {e}")

# ── Filter + Medication list ──────────────────

st.markdown("**Filter by Pet**")
med_filter_opts = ["All Pets"] + [pet_options[pid] for pid in pet_id_list]
med_filter = st.selectbox(
    "Show medications for",
    options=med_filter_opts,
    key="med_filter_pet",
    label_visibility="collapsed",
)

try:
    if med_filter == "All Pets":
        med_rows = fetch_all("""
            SELECT m.id, p.name AS pet_name, m.medication_name,
                   m.dosage, m.frequency, m.start_date, m.end_date, m.pet_id
            FROM medications m
            JOIN pets p ON p.id = m.pet_id
            ORDER BY m.start_date DESC
        """)
    else:
        selected_pid_med = next(
            pid for pid, lbl in pet_options.items() if lbl == med_filter
        )
        med_rows = fetch_all("""
            SELECT m.id, p.name AS pet_name, m.medication_name,
                   m.dosage, m.frequency, m.start_date, m.end_date, m.pet_id
            FROM medications m
            JOIN pets p ON p.id = m.pet_id
            WHERE m.pet_id = %s
            ORDER BY m.start_date DESC
        """, (selected_pid_med,))
except Exception as e:
    st.error(f"Database error loading medications: {e}")
    med_rows = []

if not med_rows:
    st.info("No medications found.")
else:
    st.markdown(f"**{len(med_rows)} record(s)**")

    hdr = st.columns([2, 2, 1, 1, 1, 1, 1, 1])
    for col, lbl in zip(hdr, ["Pet", "Medication", "Dosage", "Frequency",
                               "Start", "End", "", ""]):
        col.markdown(f"**{lbl}**")

    for row in med_rows:
        rid = row["id"]

        # ── Edit mode ──────────────────────────────
        if st.session_state.med_editing_id == rid:
            with st.container():
                st.markdown(f"**✏️ Editing:** {row['medication_name']} for {row['pet_name']}")
                with st.form(f"form_edit_med_{rid}"):
                    ec1, ec2 = st.columns(2)
                    with ec1:
                        e_pet = st.selectbox(
                            "Pet *",
                            options=pet_id_list,
                            index=pet_id_list.index(row["pet_id"]) if row["pet_id"] in pet_id_list else 0,
                            format_func=lambda pid: pet_options[pid],
                            key=f"e_pet_{rid}",
                        )
                        e_name = st.text_input(
                            "Medication Name *",
                            value=row["medication_name"],
                            key=f"e_name_{rid}",
                        )
                        e_dosage = st.text_input(
                            "Dosage",
                            value=row["dosage"] or "",
                            key=f"e_dosage_{rid}",
                        )
                    with ec2:
                        e_freq = st.text_input(
                            "Frequency",
                            value=row["frequency"] or "",
                            key=f"e_freq_{rid}",
                        )
                        e_start = st.date_input(
                            "Start Date *",
                            value=row["start_date"],
                            key=f"e_start_{rid}",
                        )
                        e_end = st.date_input(
                            "End Date",
                            value=row["end_date"],
                            key=f"e_end_{rid}",
                        )

                    save_edit, cancel_edit = st.columns(2)
                    with save_edit:
                        submitted_edit = st.form_submit_button("💾 Save Changes", type="primary")
                    with cancel_edit:
                        cancel_clicked = st.form_submit_button("Cancel")

                if cancel_clicked:
                    st.session_state.med_editing_id = None
                    st.rerun()

                if submitted_edit:
                    errors = []
                    if e_pet is None:
                        errors.append("Pet is required.")
                    if not e_name.strip():
                        errors.append("Medication name is required.")
                    if e_start is None:
                        errors.append("Start date is required.")
                    if e_end is not None and e_start is not None and e_end <= e_start:
                        errors.append("End date must be after start date.")

                    if errors:
                        st.error("\n\n".join(f"• {e}" for e in errors))
                    else:
                        try:
                            execute(
                                """UPDATE medications
                                   SET pet_id=%s, medication_name=%s, dosage=%s,
                                       frequency=%s, start_date=%s, end_date=%s
                                   WHERE id=%s""",
                                (
                                    e_pet,
                                    e_name.strip(),
                                    e_dosage.strip() or None,
                                    e_freq.strip() or None,
                                    e_start,
                                    e_end,
                                    rid,
                                ),
                            )
                            st.session_state.med_editing_id = None
                            st.success("Medication updated.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Database error: {e}")
            continue  # skip normal row rendering while in edit mode

        # ── Normal row ──────────────────────────────
        c1, c2, c3, c4, c5, c6, c7, c8 = st.columns([2, 2, 1, 1, 1, 1, 1, 1])
        c1.write(row["pet_name"])
        c2.write(row["medication_name"])
        c3.write(row["dosage"] or "—")
        c4.write(row["frequency"] or "—")
        c5.write(str(row["start_date"]))
        c6.write(str(row["end_date"]) if row["end_date"] else "—")

        with c7:
            if st.button("✏️ Edit", key=f"med_edit_{rid}"):
                st.session_state.med_editing_id = rid
                st.session_state.med_delete_confirm_id = None
                st.rerun()

        # Delete flow
        if st.session_state.med_delete_confirm_id == rid:
            with c8:
                if st.button("✅ Yes", key=f"med_del_yes_{rid}"):
                    try:
                        execute("DELETE FROM medications WHERE id = %s", (rid,))
                        st.session_state.med_delete_confirm_id = None
                        st.rerun()
                    except Exception as e:
                        st.error(f"Delete failed: {e}")
            # Show cancel inline below
            st.caption(f"⚠️ Delete **{row['medication_name']}** for {row['pet_name']}?")
            if st.button("❌ Cancel", key=f"med_del_no_{rid}"):
                st.session_state.med_delete_confirm_id = None
                st.rerun()
        else:
            with c8:
                if st.button("🗑 Del", key=f"med_del_{rid}"):
                    st.session_state.med_delete_confirm_id = rid
                    st.session_state.med_editing_id = None
                    st.rerun()
