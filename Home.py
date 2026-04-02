import streamlit as st
import psycopg2
from datetime import date, timedelta
import pandas as pd

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Paw Clinic Tracker",
    page_icon="🐾",
    layout="wide",
)

# ── Custom styling ────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=DM+Sans:wght@400;500;600&display=swap');

        html, body, [class*="css"] {
            font-family: 'DM Sans', sans-serif;
        }
        h1, h2, h3 {
            font-family: 'DM Serif Display', serif;
        }

        /* Metric card tweaks */
        [data-testid="metric-container"] {
            background: #fdf8f4;
            border: 1px solid #e8ddd4;
            border-radius: 12px;
            padding: 18px 22px;
        }
        [data-testid="stMetricLabel"] {
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: #8a7060;
            font-weight: 600;
        }
        [data-testid="stMetricValue"] {
            font-family: 'DM Serif Display', serif;
            font-size: 2.2rem;
            color: #2d1f14;
        }

        /* Dataframe styling */
        [data-testid="stDataFrame"] {
            border-radius: 10px;
            overflow: hidden;
        }

        /* Divider */
        hr {
            border: none;
            border-top: 1px solid #e8ddd4;
            margin: 1.5rem 0;
        }

        /* Section headers */
        .section-label {
            font-size: 0.72rem;
            text-transform: uppercase;
            letter-spacing: 0.12em;
            color: #b09880;
            font-weight: 600;
            margin-bottom: 0.75rem;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── DB connection ─────────────────────────────────────────────────────────────
@st.cache_resource
def get_connection():
    return psycopg2.connect(st.secrets["DB_URL"])


def run_query(sql: str, params: tuple = ()):
    """Execute a parameterized query and return rows + column names."""
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
            cols = [desc[0] for desc in cur.description]
        return rows, cols
    except psycopg2.OperationalError:
        # Connection may have timed out — retry once with a fresh connection
        try:
            st.cache_resource.clear()
            conn = get_connection()
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
                cols = [desc[0] for desc in cur.description]
            return rows, cols
        except Exception as e:
            st.error(f"Database error: {e}")
            return None, None
    except Exception as e:
        st.error(f"Database error: {e}")
        return None, None


# ── Header ────────────────────────────────────────────────────────────────────
st.title("🐾 Paw Clinic Tracker")
st.markdown(
    "A centralised dashboard for managing pet owners, veterinary visits, "
    "vaccinations, medications, and health records — all in one place."
)
st.markdown("<hr>", unsafe_allow_html=True)

# ── Metric queries ────────────────────────────────────────────────────────────
today = date.today()
month_start = today.replace(day=1)
due_window = today + timedelta(days=30)

total_owners_sql = "SELECT COUNT(*) FROM owners"
total_pets_sql = "SELECT COUNT(*) FROM pets"
visits_this_month_sql = (
    "SELECT COUNT(*) FROM vet_visits "
    "WHERE visit_date >= %s AND visit_date <= %s"
)
vaccinations_due_sql = (
    "SELECT COUNT(*) FROM pet_vaccinations "
    "WHERE next_due_date >= %s AND next_due_date <= %s"
)

col1, col2, col3, col4 = st.columns(4)

with col1:
    rows, _ = run_query(total_owners_sql)
    value = rows[0][0] if rows else "—"
    st.metric("Total Owners", value)

with col2:
    rows, _ = run_query(total_pets_sql)
    value = rows[0][0] if rows else "—"
    st.metric("Total Pets", value)

with col3:
    rows, _ = run_query(visits_this_month_sql, (month_start, today))
    value = rows[0][0] if rows else "—"
    st.metric("Vet Visits This Month", value)

with col4:
    rows, _ = run_query(vaccinations_due_sql, (today, due_window))
    value = rows[0][0] if rows else "—"
    st.metric("Vaccinations Due (30 days)", value)

st.markdown("<hr>", unsafe_allow_html=True)

# ── Recent vet visits table ───────────────────────────────────────────────────
st.markdown('<p class="section-label">Recent Vet Visits</p>', unsafe_allow_html=True)
st.subheader("Last 5 Vet Visits")

recent_visits_sql = """
    SELECT
        p.name        AS "Pet Name",
        v.reason      AS "Reason",
        v.vet_name    AS "Vet Name",
        v.visit_date  AS "Visit Date"
    FROM vet_visits v
    JOIN pets p ON p.id = v.pet_id
    ORDER BY v.visit_date DESC
    LIMIT %s
"""

rows, cols = run_query(recent_visits_sql, (5,))

if rows is not None and cols is not None:
    if rows:
        df = pd.DataFrame(rows, columns=cols)
        df["Visit Date"] = pd.to_datetime(df["Visit Date"]).dt.strftime("%b %d, %Y")
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No vet visits recorded yet.")
