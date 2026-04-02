import streamlit as st

st.title("🐾 Paw Clinic Tracker")
st.write("Welcome to the Paw Clinic Tracker. Use the sidebar to navigate.")
```

Once those are committed, go to **Streamlit Community Cloud**, connect it to your `pet-care-tracker` repo, and set the main file as `Home.py`.

Then go to your app's **Settings → Secrets** and paste this:
```
DB_URL = "postgresql://retool:npg_sci2nbLeAg3j@ep-sweet-glade-akxd2l8v-pooler.c-3.us-west-2.retooldb.com/retool?sslmode=require"
