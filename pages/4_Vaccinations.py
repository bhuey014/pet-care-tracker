import streamlit as st
import psycopg2
import psycopg2.extras
from datetime import date, timedelta

st.set_page_config(page_title="Vaccinations", layout="wide")
st.title("💉 Vaccinations")

# ── DB connection ──────────────────────────────────────────────────────────────

@st.cache_resource
def get_connection():
    return psycopg2.connect(st.secrets["DB_URL"])

def get_cursor():
    conn = get_connection()
    # Reconnect if the connection was lost
    try:
        conn.isolation_level  # lightweight ping
    except Exception:
        conn = psycopg2.connect(st.secrets["DB_URL"])
    return conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

# ── Helpers ────────────────────────────────────────────────────────────────────

def fetch_pets():
    conn, cur = get_cursor()
    cur.execute("SELECT id, name, species FROM pets ORDER BY name")
    return cur.fetchall()

def fetch_vaccinations():
    conn, cur = get_cursor()
    cur.execute("SELECT id, name FROM vaccinations ORDER BY name")
    return cur.fetchall()

def fetch_upcoming(days=30):
    conn, cur = get_cursor()
    cur.execute("""
        SELECT p.name AS pet_name,
               v.name AS vaccination_name,
               pv.date_given,
               pv.next_due_date
        FROM pet_vaccinations pv
        JOIN pets p ON p.id = pv.pet_id
        JOIN vaccinations v ON v.id = pv.vaccination_id
        WHERE pv.next_due_date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '30 days'
        ORDER BY pv.next_due_date ASC
    """, (days,))
    return cur.fetchall()

def fetch_history(pet_id=None):
    conn, cur = get_cursor()
    if pet_id:
        cur.execute("""
            SELECT pv.id,
                   p.name AS pet_name,
                   v.name AS vaccination_name,
                   pv.date_given,
                   pv.next_due_date,
                   pv.pet_id,
                   pv.vaccination_id
            FROM pet_vaccinations pv
            JOIN pets p ON p.id = pv.pet_id
            JOIN vaccinations v ON v.id = pv.vaccination_id
            WHERE pv.pet_id = %s
            ORDER BY pv.date_given DESC
        """, (pet_id,))
    else:
        cur.execute("""
            SELECT pv.id,
                   p.name AS pet_name,
                   v.name AS vaccination_name,
                   pv.date_given,
                   pv.next_due_date,
                   pv.pet_id,
                   pv.vaccination_id
            FROM pet_vaccinations pv
            JOIN pets p ON p.id = pv.pet_id
            JOIN vaccinations v ON v.id = pv.vaccination_id
            ORDER BY pv.date_given DESC
        """)
    return cur.fetchall()

def insert_vaccination(pet_id, vaccination_id, date_given, next_due_date):
    conn, cur = get_cursor()
    cur.execute("""
        INSERT INTO pet_vaccinations (pet_id, vaccination_id, date_given, next_due_date)
        VALUES (%s, %s, %s, %s)
    """, (pet_id, vaccination_id, date_given, next_due_date or None))
    conn.commit()

def update_vaccination(record_id, pet_id, vaccination_id, date_given, next_due_date):
    conn, cur = get_cursor()
    cur.execute("""
        UPDATE pet_vaccinations
        SET pet_id = %s,
            vaccination_id = %s,
            date_given = %s,
            next_due_date = %s
        WHERE id = %s
    """, (pet_id, vaccination_id, date_given, next_due_date or None, record_id))
    conn.commit()

def delete_vaccination(record_id):
    conn, cur = get_cursor()
    cur.execute("DELETE FROM pet_vaccinations WHERE id = %s", (record_id,))
    conn.commit()

# ── Session state defaults ─────────────────────────────────────────────────────

if "editing_id" not in st.session_state:
    st.session_state.editing_id = None
if "deleting_id" not in st.session_state:
    st.session_state.deleting_id = None

# ── 1. Log Vaccination Form ────────────────────────────────────────────────────

st.header("Log Vaccination")

pets = fetch_pets()
vaccinations = fetch_vaccinations()

pet_options = {f"{p['name']} ({p['species']})": p["id"] for p in pets}
vax_options = {v["name"]: v["id"] for v in vaccinations}

with st.form("log_vaccination_form", clear_on_submit=True):
    col1, col2 = st.columns(2)

    with col1:
        pet_label = st.selectbox(
            "Pet *",
            options=list(pet_options.keys()),
            index=None,
            placeholder="Select a pet…",
        )
        date_given = st.date_input(
            "Date Given *",
            value=date.today(),
            max_value=date.today(),
        )

    with col2:
        vax_label = st.selectbox(
            "Vaccination Type *",
            options=list(vax_options.keys()),
            index=None,
            placeholder="Select a vaccination…",
        )
        next_due_date = st.date_input(
            "Next Due Date (optional)",
            value=None,
            min_value=date.today() + timedelta(days=1),
        )

    submitted = st.form_submit_button("💾 Log Vaccination", use_container_width=True)

    if submitted:
        errors = []

        if not pet_label:
            errors.append("Pet is required.")
        if not vax_label:
            errors.append("Vaccination type is required.")
        if date_given > date.today():
            errors.append("Date Given cannot be in the future.")
        if next_due_date and date_given and next_due_date <= date_given:
            errors.append("Next Due Date must be after Date Given.")

        if errors:
            st.error("\n".join(f"• {e}" for e in errors))
        else:
            try:
                insert_vaccination(
                    pet_options[pet_label],
                    vax_options[vax_label],
                    date_given,
                    next_due_date,
                )
                st.success("Vaccination logged successfully!")
                st.rerun()
            except Exception as e:
                st.error(f"Database error: {e}")

st.divider()

# ── 2. Upcoming Vaccinations ───────────────────────────────────────────────────

st.header("📅 Upcoming Vaccinations (Next 30 Days)")

try:
    upcoming = fetch_upcoming(30)
except Exception as e:
    st.error(f"Database error loading upcoming vaccinations: {e}")
    upcoming = []

if upcoming:
    st.dataframe(
        [
            {
                "Pet": r["pet_name"],
                "Vaccination": r["vaccination_name"],
                "Date Given": r["date_given"].strftime("%Y-%m-%d"),
                "Next Due": r["next_due_date"].strftime("%Y-%m-%d"),
            }
            for r in upcoming
        ],
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info("No vaccinations due in the next 30 days.")

st.divider()

# ── 3 & 4 & 5. Full History with Edit / Delete ────────────────────────────────

st.header("📋 Full Vaccination History")

# Filter by pet
filter_options = {"All Pets": None, **{f"{p['name']} ({p['species']})": p["id"] for p in pets}}
filter_label = st.selectbox("Filter by Pet", options=list(filter_options.keys()))
filter_pet_id = filter_options[filter_label]

try:
    history = fetch_history(filter_pet_id)
except Exception as e:
    st.error(f"Database error loading history: {e}")
    history = []

if not history:
    st.info("No vaccination records found.")
else:
    # Column headers
    h0, h1, h2, h3, h4, h5, h6 = st.columns([2, 2, 2, 2, 0.8, 0.8, 0.1])
    h0.markdown("**Pet**")
    h1.markdown("**Vaccination**")
    h2.markdown("**Date Given**")
    h3.markdown("**Next Due**")
    h4.markdown("**Edit**")
    h5.markdown("**Delete**")
    st.markdown("---")

    for row in history:
        rid = row["id"]
        c0, c1, c2, c3, c4, c5, _ = st.columns([2, 2, 2, 2, 0.8, 0.8, 0.1])
        c0.write(row["pet_name"])
        c1.write(row["vaccination_name"])
        c2.write(row["date_given"].strftime("%Y-%m-%d"))
        c3.write(row["next_due_date"].strftime("%Y-%m-%d") if row["next_due_date"] else "—")

        if c4.button("✏️", key=f"edit_{rid}", help="Edit this record"):
            st.session_state.editing_id = rid
            st.session_state.deleting_id = None

        if c5.button("🗑️", key=f"del_{rid}", help="Delete this record"):
            st.session_state.deleting_id = rid
            st.session_state.editing_id = None

        # ── Edit form (inline, below matching row) ─────────────────────────
        if st.session_state.editing_id == rid:
            with st.form(f"edit_form_{rid}"):
                st.markdown(f"**Edit record #{rid}**")
                ec1, ec2 = st.columns(2)

                current_pet_label = next(
                    (k for k, v in pet_options.items() if v == row["pet_id"]), None
                )
                current_vax_label = next(
                    (k for k, v in vax_options.items() if v == row["vaccination_id"]), None
                )

                edit_pet = ec1.selectbox(
                    "Pet *",
                    options=list(pet_options.keys()),
                    index=list(pet_options.keys()).index(current_pet_label)
                    if current_pet_label
                    else 0,
                    key=f"ep_{rid}",
                )
                edit_vax = ec2.selectbox(
                    "Vaccination *",
                    options=list(vax_options.keys()),
                    index=list(vax_options.keys()).index(current_vax_label)
                    if current_vax_label
                    else 0,
                    key=f"ev_{rid}",
                )
                edit_date_given = ec1.date_input(
                    "Date Given *",
                    value=row["date_given"],
                    max_value=date.today(),
                    key=f"edg_{rid}",
                )
                edit_next_due = ec2.date_input(
                    "Next Due Date (optional)",
                    value=row["next_due_date"],
                    key=f"end_{rid}",
                )

                save_col, cancel_col = st.columns(2)
                save = save_col.form_submit_button("💾 Save Changes", use_container_width=True)
                cancel = cancel_col.form_submit_button("✕ Cancel", use_container_width=True)

                if cancel:
                    st.session_state.editing_id = None
                    st.rerun()

                if save:
                    errors = []
                    if edit_date_given > date.today():
                        errors.append("Date Given cannot be in the future.")
                    if edit_next_due and edit_next_due <= edit_date_given:
                        errors.append("Next Due Date must be after Date Given.")

                    if errors:
                        st.error("\n".join(f"• {e}" for e in errors))
                    else:
                        try:
                            update_vaccination(
                                rid,
                                pet_options[edit_pet],
                                vax_options[edit_vax],
                                edit_date_given,
                                edit_next_due,
                            )
                            st.session_state.editing_id = None
                            st.success("Record updated.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Database error: {e}")

        # ── Delete confirmation ────────────────────────────────────────────
        if st.session_state.deleting_id == rid:
            st.warning(
                f"Are you sure you want to delete the **{row['vaccination_name']}** "
                f"record for **{row['pet_name']}** ({row['date_given'].strftime('%Y-%m-%d')})?"
            )
            yes_col, no_col, _ = st.columns([1, 1, 4])
            if yes_col.button("✅ Yes, delete", key=f"confirm_del_{rid}"):
                try:
                    delete_vaccination(rid)
                    st.session_state.deleting_id = None
                    st.success("Record deleted.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Database error: {e}")
            if no_col.button("❌ Cancel", key=f"cancel_del_{rid}"):
                st.session_state.deleting_id = None
                st.rerun()
