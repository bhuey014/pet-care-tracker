import streamlit as st
import psycopg2
import psycopg2.extras
from datetime import date

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Manage Pets", page_icon="🐾", layout="wide")

SPECIES_OPTIONS = ["dog", "cat"]

# ── DB helpers ─────────────────────────────────────────────────────────────────

@st.cache_resource
def get_connection():
    return psycopg2.connect(st.secrets["DB_URL"])


def get_cursor():
    """Return a dict-cursor, reconnecting if the connection dropped."""
    conn = get_connection()
    try:
        conn.isolation_level          # lightweight ping
    except Exception:
        get_connection.clear()
        conn = get_connection()
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)


def commit():
    get_connection().commit()


def rollback():
    get_connection().rollback()


# ── Data fetchers ───────────────────────────────────────────────────────────────

def fetch_owners():
    with get_cursor() as cur:
        cur.execute(
            "SELECT id, first_name || ' ' || last_name AS full_name "
            "FROM owners ORDER BY last_name, first_name"
        )
        return cur.fetchall()


def fetch_pets(search: str = ""):
    with get_cursor() as cur:
        sql = """
            SELECT
                p.id,
                p.name        AS pet_name,
                p.species,
                p.breed,
                p.birthdate,
                p.created_at,
                p.owner_id,
                o.first_name || ' ' || o.last_name AS owner_name
            FROM pets p
            JOIN owners o ON o.id = p.owner_id
            WHERE (%s = '' OR p.name ILIKE '%%' || %s || '%%')
            ORDER BY p.name
        """
        cur.execute(sql, (search, search))
        return cur.fetchall()


def insert_pet(name, species, breed, birthdate, owner_id):
    with get_cursor() as cur:
        cur.execute(
            "INSERT INTO pets (name, species, breed, birthdate, owner_id) "
            "VALUES (%s, %s, %s, %s, %s)",
            (name, species, breed or None, birthdate, owner_id),
        )
    commit()


def update_pet(pet_id, name, species, breed, birthdate, owner_id):
    with get_cursor() as cur:
        cur.execute(
            "UPDATE pets SET name=%s, species=%s, breed=%s, birthdate=%s, owner_id=%s "
            "WHERE id=%s",
            (name, species, breed or None, birthdate, owner_id, pet_id),
        )
    commit()


def delete_pet(pet_id):
    with get_cursor() as cur:
        cur.execute("DELETE FROM pets WHERE id=%s", (pet_id,))
    commit()


# ── Session-state defaults ──────────────────────────────────────────────────────
for key in ("editing_id", "deleting_id", "add_success"):
    if key not in st.session_state:
        st.session_state[key] = None

# ── Page header ────────────────────────────────────────────────────────────────
st.title("🐾 Manage Pets")
st.caption("Add, search, edit and delete pet records.")
st.divider()

# ── Owner data (used in both Add and Edit forms) ────────────────────────────────
try:
    owners = fetch_owners()
except Exception as e:
    st.error(f"Could not load owners: {e}")
    st.stop()

owner_options = {o["id"]: o["full_name"] for o in owners}   # id → name
owner_ids     = list(owner_options.keys())
owner_labels  = list(owner_options.values())


# ══════════════════════════════════════════════════════════════════════════════
# 1. ADD PET FORM
# ══════════════════════════════════════════════════════════════════════════════
with st.expander("➕ Add a New Pet", expanded=st.session_state.add_success is None):

    with st.form("add_pet_form", clear_on_submit=True):
        st.subheader("New Pet")

        col1, col2 = st.columns(2)
        with col1:
            new_name    = st.text_input("Pet Name *")
            new_species = st.selectbox("Species *", [""] + SPECIES_OPTIONS)
            new_breed   = st.text_input("Breed")
        with col2:
            new_birthdate = st.date_input(
                "Birthdate",
                value=None,
                min_value=date(2000, 1, 1),
                max_value=date.today(),
            )
            owner_label_sel = st.selectbox(
                "Owner *",
                ["— select owner —"] + owner_labels,
            )

        submitted = st.form_submit_button("Add Pet", type="primary")

    if submitted:
        errors = []
        if not new_name.strip():
            errors.append("Pet name is required.")
        if not new_species:
            errors.append("Species is required.")
        if owner_label_sel == "— select owner —":
            errors.append("Please select an owner.")

        if errors:
            st.error("\n".join(f"• {e}" for e in errors))
        else:
            selected_owner_id = owner_ids[owner_labels.index(owner_label_sel)]
            try:
                insert_pet(
                    new_name.strip(),
                    new_species,
                    new_breed.strip(),
                    new_birthdate,
                    selected_owner_id,
                )
                st.session_state.add_success = True
                st.success(f"✅ **{new_name.strip()}** added successfully!")
                st.rerun()
            except Exception as e:
                rollback()
                st.error(f"Database error while adding pet: {e}")

if st.session_state.add_success:
    st.session_state.add_success = None


# ══════════════════════════════════════════════════════════════════════════════
# 2. SEARCH
# ══════════════════════════════════════════════════════════════════════════════
st.divider()
search_term = st.text_input(
    "🔍 Search pets by name",
    placeholder="e.g. Buddy",
    label_visibility="collapsed",
)

# ══════════════════════════════════════════════════════════════════════════════
# 3 + 4 + 5. PETS TABLE WITH EDIT / DELETE
# ══════════════════════════════════════════════════════════════════════════════
try:
    pets = fetch_pets(search_term)
except Exception as e:
    st.error(f"Could not load pets: {e}")
    st.stop()

if not pets:
    st.info("No pets found." if search_term else "No pets recorded yet.")
else:
    # Column headers
    hcols = st.columns([2, 1.2, 1.5, 2, 1.3, 1.8, 0.9, 0.9])
    headers = ["Pet Name", "Species", "Breed", "Owner", "Birthdate", "Date Added", "Edit", "Delete"]
    for hc, h in zip(hcols, headers):
        hc.markdown(f"**{h}**")

    st.divider()

    for pet in pets:
        pid = pet["id"]
        row_cols = st.columns([2, 1.2, 1.5, 2, 1.3, 1.8, 0.9, 0.9])

        row_cols[0].write(pet["pet_name"])
        row_cols[1].write(pet["species"].capitalize())
        row_cols[2].write(pet["breed"] or "—")
        row_cols[3].write(pet["owner_name"])
        row_cols[4].write(
            pet["birthdate"].strftime("%b %d, %Y") if pet["birthdate"] else "—"
        )
        row_cols[5].write(pet["created_at"].strftime("%b %d, %Y"))

        # ── Edit button ──────────────────────────────────────────────────────
        if row_cols[6].button("✏️", key=f"edit_btn_{pid}", help="Edit this pet"):
            st.session_state.editing_id = pid
            st.session_state.deleting_id = None

        # ── Delete button ────────────────────────────────────────────────────
        if row_cols[7].button("🗑️", key=f"del_btn_{pid}", help="Delete this pet"):
            st.session_state.deleting_id = pid
            st.session_state.editing_id = None

        # ── Delete confirmation ──────────────────────────────────────────────
        if st.session_state.deleting_id == pid:
            with st.container(border=True):
                st.warning(
                    f"Are you sure you want to delete **{pet['pet_name']}**? "
                    "This cannot be undone."
                )
                conf_cols = st.columns([1, 1, 6])
                if conf_cols[0].button("Yes, delete", key=f"confirm_del_{pid}", type="primary"):
                    try:
                        delete_pet(pid)
                        st.session_state.deleting_id = None
                        st.success(f"Deleted **{pet['pet_name']}**.")
                        st.rerun()
                    except Exception as e:
                        rollback()
                        st.error(f"Database error while deleting: {e}")
                if conf_cols[1].button("Cancel", key=f"cancel_del_{pid}"):
                    st.session_state.deleting_id = None
                    st.rerun()

        # ── Edit form ────────────────────────────────────────────────────────
        if st.session_state.editing_id == pid:
            with st.container(border=True):
                st.subheader(f"Edit: {pet['pet_name']}")

                # Pre-select current owner index
                try:
                    cur_owner_idx = owner_ids.index(pet["owner_id"])
                except ValueError:
                    cur_owner_idx = 0

                with st.form(f"edit_form_{pid}"):
                    ec1, ec2 = st.columns(2)
                    with ec1:
                        e_name = st.text_input("Pet Name *", value=pet["pet_name"])
                        e_species = st.selectbox(
                            "Species *",
                            SPECIES_OPTIONS,
                            index=SPECIES_OPTIONS.index(pet["species"])
                            if pet["species"] in SPECIES_OPTIONS
                            else 0,
                        )
                        e_breed = st.text_input("Breed", value=pet["breed"] or "")
                    with ec2:
                        e_birthdate = st.date_input(
                            "Birthdate",
                            value=pet["birthdate"],
                            min_value=date(2000, 1, 1),
                            max_value=date.today(),
                        )
                        e_owner_label = st.selectbox(
                            "Owner *",
                            owner_labels,
                            index=cur_owner_idx,
                        )

                    save_col, cancel_col = st.columns([1, 1])
                    save   = save_col.form_submit_button("💾 Save Changes", type="primary")
                    cancel = cancel_col.form_submit_button("Cancel")

                if cancel:
                    st.session_state.editing_id = None
                    st.rerun()

                if save:
                    edit_errors = []
                    if not e_name.strip():
                        edit_errors.append("Pet name is required.")
                    if not e_species:
                        edit_errors.append("Species is required.")

                    if edit_errors:
                        st.error("\n".join(f"• {e}" for e in edit_errors))
                    else:
                        new_owner_id = owner_ids[owner_labels.index(e_owner_label)]
                        try:
                            update_pet(
                                pid,
                                e_name.strip(),
                                e_species,
                                e_breed.strip(),
                                e_birthdate,
                                new_owner_id,
                            )
                            st.session_state.editing_id = None
                            st.success("✅ Pet updated.")
                            st.rerun()
                        except Exception as e:
                            rollback()
                            st.error(f"Database error while updating: {e}")

        st.divider()
