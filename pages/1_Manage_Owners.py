import re
import streamlit as st
import psycopg2
import psycopg2.extras
from datetime import datetime

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Manage Owners",
    page_icon="👤",
    layout="wide",
)

# ── Styling ───────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Card-style sections */
    .section-card {
        background: #f8f9fb;
        border: 1px solid #e2e6ea;
        border-radius: 10px;
        padding: 1.25rem 1.5rem;
        margin-bottom: 1.5rem;
    }
    .section-title {
        font-size: 1rem;
        font-weight: 700;
        color: #1a1d23;
        letter-spacing: 0.03em;
        text-transform: uppercase;
        margin-bottom: 0.75rem;
    }
    /* Owner row styling */
    .owner-row {
        background: #ffffff;
        border: 1px solid #e8eaed;
        border-radius: 8px;
        padding: 0.65rem 1rem;
        margin-bottom: 0.4rem;
        display: flex;
        align-items: center;
    }
    /* Confirmation banner */
    .confirm-banner {
        background: #fff8e1;
        border-left: 4px solid #f59e0b;
        border-radius: 6px;
        padding: 0.6rem 1rem;
        margin: 0.4rem 0;
        font-size: 0.9rem;
    }
    /* Subtle header row */
    .table-header {
        font-size: 0.75rem;
        font-weight: 700;
        color: #6b7280;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        padding: 0 0.5rem 0.4rem 0.5rem;
    }
</style>
""", unsafe_allow_html=True)


# ── DB helpers ────────────────────────────────────────────────────────────────

@st.cache_resource
def get_connection():
    """Return a persistent connection from st.secrets."""
    return psycopg2.connect(st.secrets["DB_URL"])


def get_cursor():
    conn = get_connection()
    # Re-connect if the connection was closed / timed out
    try:
        conn.isolation_level  # lightweight ping
    except Exception:
        conn = psycopg2.connect(st.secrets["DB_URL"])
        get_connection.clear()
    return conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)


def fetch_owners(search: str = ""):
    conn, cur = get_cursor()
    try:
        if search.strip():
            cur.execute(
                """
                SELECT id, first_name, last_name, email, phone, created_at
                FROM owners
                WHERE last_name ILIKE %s
                ORDER BY last_name, first_name
                """,
                (f"%{search.strip()}%",),
            )
        else:
            cur.execute(
                """
                SELECT id, first_name, last_name, email, phone, created_at
                FROM owners
                ORDER BY last_name, first_name
                """
            )
        return cur.fetchall()
    except Exception as e:
        st.error(f"Database error fetching owners: {e}")
        return []
    finally:
        cur.close()


def insert_owner(first_name, last_name, email, phone):
    conn, cur = get_cursor()
    try:
        cur.execute(
            """
            INSERT INTO owners (first_name, last_name, email, phone)
            VALUES (%s, %s, %s, %s)
            """,
            (first_name, last_name, email, phone or None),
        )
        conn.commit()
        return True, None
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        return False, "A owner with that email address already exists."
    except Exception as e:
        conn.rollback()
        return False, f"Database error: {e}"
    finally:
        cur.close()


def update_owner(owner_id, first_name, last_name, email, phone):
    conn, cur = get_cursor()
    try:
        cur.execute(
            """
            UPDATE owners
            SET first_name = %s, last_name = %s, email = %s, phone = %s
            WHERE id = %s
            """,
            (first_name, last_name, email, phone or None, owner_id),
        )
        conn.commit()
        return True, None
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        return False, "Another owner with that email address already exists."
    except Exception as e:
        conn.rollback()
        return False, f"Database error: {e}"
    finally:
        cur.close()


def delete_owner(owner_id):
    conn, cur = get_cursor()
    try:
        cur.execute("DELETE FROM owners WHERE id = %s", (owner_id,))
        conn.commit()
        return True, None
    except Exception as e:
        conn.rollback()
        return False, f"Database error: {e}"
    finally:
        cur.close()


# ── Validation ────────────────────────────────────────────────────────────────

EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")

def validate_owner_fields(first_name, last_name, email, phone):
    errors = []
    if not first_name.strip():
        errors.append("First name is required.")
    if not last_name.strip():
        errors.append("Last name is required.")
    if not email.strip():
        errors.append("Email is required.")
    elif not EMAIL_RE.match(email.strip()):
        errors.append("Email does not match a valid format (e.g. user@example.com).")
    if phone.strip():
        if not phone.strip().isdigit():
            errors.append("Phone must contain digits only.")
        elif len(phone.strip()) != 10:
            errors.append("Phone must be exactly 10 digits.")
    return errors


# ── Session state init ────────────────────────────────────────────────────────

if "editing_id" not in st.session_state:
    st.session_state.editing_id = None        # id of owner currently being edited
if "confirm_delete_id" not in st.session_state:
    st.session_state.confirm_delete_id = None # id of owner pending delete confirmation
if "search_query" not in st.session_state:
    st.session_state.search_query = ""


# ─────────────────────────────────────────────────────────────────────────────
# PAGE HEADER
# ─────────────────────────────────────────────────────────────────────────────

st.title("👤 Manage Owners")
st.caption("Add, search, edit, and remove pet owners from the database.")
st.divider()


# ─────────────────────────────────────────────────────────────────────────────
# 1. ADD OWNER FORM
# ─────────────────────────────────────────────────────────────────────────────

with st.expander("➕ Add New Owner", expanded=True):
    with st.form("add_owner_form", clear_on_submit=True):
        st.markdown("#### New Owner Details")
        col1, col2 = st.columns(2)
        with col1:
            new_first = st.text_input("First Name *")
            new_email = st.text_input("Email *")
        with col2:
            new_last  = st.text_input("Last Name *")
            new_phone = st.text_input("Phone (10 digits, optional)")

        submitted = st.form_submit_button("💾 Save Owner", use_container_width=True)

    if submitted:
        errors = validate_owner_fields(new_first, new_last, new_email, new_phone)
        if errors:
            st.error("\n".join(f"• {e}" for e in errors))
        else:
            ok, msg = insert_owner(
                new_first.strip(), new_last.strip(),
                new_email.strip(), new_phone.strip()
            )
            if ok:
                st.success(f"Owner **{new_first.strip()} {new_last.strip()}** added successfully!")
                st.rerun()
            else:
                st.error(msg)


# ─────────────────────────────────────────────────────────────────────────────
# 2. SEARCH
# ─────────────────────────────────────────────────────────────────────────────

st.subheader("🔍 Search Owners")
search_val = st.text_input(
    "Filter by last name",
    value=st.session_state.search_query,
    placeholder="e.g. Smith",
    label_visibility="collapsed",
)
st.session_state.search_query = search_val


# ─────────────────────────────────────────────────────────────────────────────
# 3 + 4 + 5. OWNERS TABLE WITH EDIT / DELETE
# ─────────────────────────────────────────────────────────────────────────────

st.subheader("📋 Owners")
owners = fetch_owners(search_val)

if not owners:
    st.info("No owners found." + (" Try a different search term." if search_val else " Add one above!"))
else:
    # Header row
    hcols = st.columns([2, 2, 3, 2, 2, 1, 1])
    headers = ["First Name", "Last Name", "Email", "Phone", "Date Added", "", ""]
    for hc, h in zip(hcols, headers):
        hc.markdown(f"<span class='table-header'>{h}</span>", unsafe_allow_html=True)

    st.divider()

    for owner in owners:
        oid        = owner["id"]
        first      = owner["first_name"]
        last       = owner["last_name"]
        email      = owner["email"]
        phone      = owner["phone"] or "—"
        created    = owner["created_at"]
        date_str   = created.strftime("%b %d, %Y") if isinstance(created, datetime) else str(created)

        row_cols = st.columns([2, 2, 3, 2, 2, 1, 1])
        row_cols[0].write(first)
        row_cols[1].write(last)
        row_cols[2].write(email)
        row_cols[3].write(phone)
        row_cols[4].write(date_str)

        # Edit button
        if row_cols[5].button("✏️", key=f"edit_{oid}", help="Edit this owner"):
            st.session_state.editing_id      = oid
            st.session_state.confirm_delete_id = None

        # Delete button
        if row_cols[6].button("🗑️", key=f"del_{oid}", help="Delete this owner"):
            st.session_state.confirm_delete_id = oid
            st.session_state.editing_id        = None

        # ── Delete confirmation ───────────────────────────────────────────
        if st.session_state.confirm_delete_id == oid:
            st.warning(
                f"⚠️ Are you sure you want to delete **{first} {last}**? This cannot be undone."
            )
            c1, c2, _ = st.columns([1, 1, 6])
            if c1.button("Yes, delete", key=f"confirm_del_{oid}", type="primary"):
                ok, msg = delete_owner(oid)
                if ok:
                    st.success(f"Owner **{first} {last}** deleted.")
                    st.session_state.confirm_delete_id = None
                    st.rerun()
                else:
                    st.error(msg)
            if c2.button("Cancel", key=f"cancel_del_{oid}"):
                st.session_state.confirm_delete_id = None
                st.rerun()

        # ── Edit form ─────────────────────────────────────────────────────
        if st.session_state.editing_id == oid:
            with st.form(f"edit_form_{oid}"):
                st.markdown(f"#### Edit — {first} {last}")
                ec1, ec2 = st.columns(2)
                with ec1:
                    e_first = st.text_input("First Name *", value=first)
                    e_email = st.text_input("Email *", value=email)
                with ec2:
                    e_last  = st.text_input("Last Name *", value=last)
                    e_phone = st.text_input(
                        "Phone (10 digits, optional)",
                        value=owner["phone"] or ""
                    )
                fc1, fc2 = st.columns([1, 5])
                save_edit   = fc1.form_submit_button("💾 Save", use_container_width=True)
                cancel_edit = fc2.form_submit_button("✖ Cancel", use_container_width=False)

            if save_edit:
                errors = validate_owner_fields(e_first, e_last, e_email, e_phone)
                if errors:
                    st.error("\n".join(f"• {e}" for e in errors))
                else:
                    ok, msg = update_owner(
                        oid,
                        e_first.strip(), e_last.strip(),
                        e_email.strip(), e_phone.strip()
                    )
                    if ok:
                        st.success("Owner updated successfully!")
                        st.session_state.editing_id = None
                        st.rerun()
                    else:
                        st.error(msg)

            if cancel_edit:
                st.session_state.editing_id = None
                st.rerun()

        st.divider()
