import streamlit as st
import psycopg2
import psycopg2.extras
from datetime import date

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Vet Visits", page_icon="🐾", layout="wide")

st.title("🐾 Vet Visits")
st.markdown("---")


# ── Database helpers ────────────────────────────────────────────────────────────
def get_connection():
    return psycopg2.connect(st.secrets["DB_URL"])


def fetch_all(query: str, params=None):
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(query, params)
                return cur.fetchall(), None
    except Exception as e:
        return None, str(e)


def execute_query(query: str, params=None):
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
            conn.commit()
        return None
    except Exception as e:
        return str(e)


# ── Load pets for selectbox ─────────────────────────────────────────────────────
def load_pets():
    rows, err = fetch_all(
        "SELECT id, name, species FROM pets ORDER BY name"
    )
    if err:
        st.error(f"Could not load pets: {err}")
        return []
    return rows or []


# ── Session-state defaults ──────────────────────────────────────────────────────
for key, default in {
    "editing_visit_id": None,
    "deleting_visit_id": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


# ══════════════════════════════════════════════════════════════════════════════
# 1. LOG VISIT FORM
# ══════════════════════════════════════════════════════════════════════════════
st.subheader("➕ Log a New Visit")

pets = load_pets()
pet_options = {f"{p['name']} ({p['species']})": p["id"] for p in pets}
pet_labels = ["— select a pet —"] + list(pet_options.keys())

with st.form("log_visit_form", clear_on_submit=True):
    col1, col2 = st.columns(2)
    with col1:
        selected_pet_label = st.selectbox("Pet *", pet_labels)
        visit_date = st.date_input("Visit Date *", value=date.today())
        vet_name = st.text_input("Vet Name", placeholder="Dr. Smith")
    with col2:
        reason = st.text_input("Reason *", placeholder="Annual checkup")
        notes = st.text_area("Notes", placeholder="Optional notes…", height=120)

    submitted = st.form_submit_button("💾 Log Visit", use_container_width=True)

    if submitted:
        errors = []
        if selected_pet_label == "— select a pet —":
            errors.append("• Please select a pet.")
        if visit_date > date.today():
            errors.append("• Visit date cannot be in the future.")
        if not reason.strip():
            errors.append("• Reason is required.")

        if errors:
            st.error("\n".join(errors))
        else:
            pet_id = pet_options[selected_pet_label]
            err = execute_query(
                """
                INSERT INTO vet_visits (pet_id, visit_date, reason, notes, vet_name)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (pet_id, visit_date, reason.strip(), notes.strip() or None, vet_name.strip() or None),
            )
            if err:
                st.error(f"Database error: {err}")
            else:
                st.success("Visit logged successfully!")
                st.rerun()

st.markdown("---")


# ══════════════════════════════════════════════════════════════════════════════
# 2. FILTER
# ══════════════════════════════════════════════════════════════════════════════
st.subheader("📋 Vet Visit History")

filter_labels = ["All Pets"] + [f"{p['name']} ({p['species']})" for p in pets]
filter_pet_ids = [None] + [p["id"] for p in pets]

filter_col, _ = st.columns([2, 5])
with filter_col:
    filter_idx = st.selectbox(
        "Filter by pet",
        range(len(filter_labels)),
        format_func=lambda i: filter_labels[i],
        key="visit_filter",
    )

selected_filter_pet_id = filter_pet_ids[filter_idx]


# ══════════════════════════════════════════════════════════════════════════════
# 3. VISITS TABLE
# ══════════════════════════════════════════════════════════════════════════════
if selected_filter_pet_id is None:
    visits, err = fetch_all(
        """
        SELECT vv.id, p.name AS pet_name, vv.reason, vv.vet_name,
               vv.visit_date, vv.notes, vv.pet_id
        FROM vet_visits vv
        JOIN pets p ON p.id = vv.pet_id
        ORDER BY vv.visit_date DESC
        """
    )
else:
    visits, err = fetch_all(
        """
        SELECT vv.id, p.name AS pet_name, vv.reason, vv.vet_name,
               vv.visit_date, vv.notes, vv.pet_id
        FROM vet_visits vv
        JOIN pets p ON p.id = vv.pet_id
        WHERE vv.pet_id = %s
        ORDER BY vv.visit_date DESC
        """,
        (selected_filter_pet_id,),
    )

if err:
    st.error(f"Database error loading visits: {err}")
    st.stop()

if not visits:
    st.info("No vet visits found.")
    st.stop()

# Header row
hc = st.columns([2, 3, 2, 1.5, 3, 1, 1])
for col, label in zip(
    hc, ["Pet", "Reason", "Vet", "Date", "Notes", "Edit", "Delete"]
):
    col.markdown(f"**{label}**")

st.markdown('<hr style="margin:4px 0 8px"/>', unsafe_allow_html=True)

# Data rows
for visit in visits:
    vid = visit["id"]
    row_cols = st.columns([2, 3, 2, 1.5, 3, 1, 1])

    row_cols[0].write(visit["pet_name"])
    row_cols[1].write(visit["reason"])
    row_cols[2].write(visit["vet_name"] or "—")
    row_cols[3].write(str(visit["visit_date"]))
    row_cols[4].write(visit["notes"] or "—")

    # ── Edit button ────────────────────────────────────────────────────────
    if row_cols[5].button("✏️", key=f"edit_{vid}", help="Edit visit"):
        st.session_state.editing_visit_id = vid
        st.session_state.deleting_visit_id = None

    # ── Delete button ──────────────────────────────────────────────────────
    if row_cols[6].button("🗑️", key=f"del_{vid}", help="Delete visit"):
        st.session_state.deleting_visit_id = vid
        st.session_state.editing_visit_id = None

    # ── Delete confirmation ────────────────────────────────────────────────
    if st.session_state.deleting_visit_id == vid:
        with st.container():
            st.warning(
                f"Delete the visit on **{visit['visit_date']}** for **{visit['pet_name']}**? "
                "This cannot be undone."
            )
            confirm_col, cancel_col, _ = st.columns([1, 1, 5])
            if confirm_col.button("Yes, delete", key=f"confirm_del_{vid}", type="primary"):
                err = execute_query("DELETE FROM vet_visits WHERE id = %s", (vid,))
                if err:
                    st.error(f"Database error: {err}")
                else:
                    st.session_state.deleting_visit_id = None
                    st.success("Visit deleted.")
                    st.rerun()
            if cancel_col.button("Cancel", key=f"cancel_del_{vid}"):
                st.session_state.deleting_visit_id = None
                st.rerun()

    # ── Inline edit form ───────────────────────────────────────────────────
    if st.session_state.editing_visit_id == vid:
        with st.container():
            st.markdown(f"**Edit visit for {visit['pet_name']}**")
            with st.form(f"edit_form_{vid}"):
                ec1, ec2 = st.columns(2)
                with ec1:
                    e_pet_labels = ["— select a pet —"] + list(pet_options.keys())
                    current_pet_label = next(
                        (lbl for lbl, pid in pet_options.items() if pid == visit["pet_id"]),
                        "— select a pet —",
                    )
                    e_pet_idx = e_pet_labels.index(current_pet_label)
                    e_selected_pet = st.selectbox("Pet *", e_pet_labels, index=e_pet_idx)
                    e_visit_date = st.date_input("Visit Date *", value=visit["visit_date"])
                    e_vet_name = st.text_input("Vet Name", value=visit["vet_name"] or "")
                with ec2:
                    e_reason = st.text_input("Reason *", value=visit["reason"])
                    e_notes = st.text_area("Notes", value=visit["notes"] or "", height=100)

                save_col, cancel_col2 = st.columns([1, 1])
                save = save_col.form_submit_button("💾 Save Changes", use_container_width=True)
                cancel = cancel_col2.form_submit_button("✖ Cancel", use_container_width=True)

                if cancel:
                    st.session_state.editing_visit_id = None
                    st.rerun()

                if save:
                    edit_errors = []
                    if e_selected_pet == "— select a pet —":
                        edit_errors.append("• Please select a pet.")
                    if e_visit_date > date.today():
                        edit_errors.append("• Visit date cannot be in the future.")
                    if not e_reason.strip():
                        edit_errors.append("• Reason is required.")

                    if edit_errors:
                        st.error("\n".join(edit_errors))
                    else:
                        e_pet_id = pet_options[e_selected_pet]
                        err = execute_query(
                            """
                            UPDATE vet_visits
                            SET pet_id = %s,
                                visit_date = %s,
                                reason = %s,
                                notes = %s,
                                vet_name = %s
                            WHERE id = %s
                            """,
                            (
                                e_pet_id,
                                e_visit_date,
                                e_reason.strip(),
                                e_notes.strip() or None,
                                e_vet_name.strip() or None,
                                vid,
                            ),
                        )
                        if err:
                            st.error(f"Database error: {err}")
                        else:
                            st.session_state.editing_visit_id = None
                            st.success("Visit updated.")
                            st.rerun()

    st.markdown('<hr style="margin:4px 0"/>', unsafe_allow_html=True)
