import streamlit as st
import pandas as pd
import plotly.express as px
from io import StringIO

# =========================
#   PAGE / THEME SETTINGS
# =========================
st.set_page_config(page_title="Travel Dashboard", page_icon="🌍", layout="wide")
st.title("🌍 Travel Dashboard")
st.caption("Add trips & meals in-app • Auto-fill map coordinates from City + Country • Explore maps & costs")

# --- Robust background (uses a fixed pseudo-element so it always shows) ---
# If you prefer a different map, just replace IMAGE_URL below.
st.markdown("""
<style>
/* Make all base layers transparent so our image is visible */
html, body, .stApp, [data-testid="stAppViewContainer"] { background: transparent !important; }

/* Full-viewport background via pseudo-element */
[data-testid="stAppViewContainer"]::before {
  content: "";
  position: fixed;
  inset: 0;
  z-index: -1;
  background:
    linear-gradient(rgba(0,0,0,0.08), rgba(0,0,0,0.08)),
    url('https://upload.wikimedia.org/wikipedia/commons/2/21/Mercator_projection_SW.jpg')
    center center / cover no-repeat;
  filter: brightness(0.75) contrast(1.1);
}

/* Glass panels */
.block-container {
  background: rgba(255, 255, 255, 0.88);
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
  border-radius: 16px;
  padding: 1.2rem 1.4rem;
}
[data-testid="stSidebar"] > div:first-child {
  background: rgba(255, 255, 255, 0.88);
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
}

/* Headings + chart bg */
h1, h2, h3, h4, h5, h6 { color: #0f172a; }
.js-plotly-plot .plotly .bg { fill: rgba(255,255,255,0.0) !important; }
</style>
""", unsafe_allow_html=True)

# -------------------------
#   KALEIDO DETECTION & CONFIG (optional PNG export)
# -------------------------
try:
    import kaleido  # noqa: F401
    KALEIDO_OK = True
except Exception:
    KALEIDO_OK = False

PLOTLY_CONFIG = {"displaylogo": False, "modeBarButtonsToAdd": ["toImage"] if not KALEIDO_OK else []}

# -------------------------
#   OPTIONAL GEOCODER (geopy)
# -------------------------
try:
    from geopy.geocoders import Nominatim
    from geopy.extra.rate_limiter import RateLimiter
    GEOCODER_OK = True
except Exception:
    GEOCODER_OK = False

@st.cache_data(show_spinner=False)
def geocode_city_country(city: str, country: str):
    """Return (lat, lon) or None using OpenStreetMap Nominatim; polite rate limits."""
    if not GEOCODER_OK or not city or not country:
        return None
    try:
        geolocator = Nominatim(user_agent="travel_dashboard_app", timeout=6)
        geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)
        loc = geocode(f"{city}, {country}")
        if loc:
            return float(loc.latitude), float(loc.longitude)
    except Exception:
        pass
    return None

# -------------------------
#   HELPERS
# -------------------------
def empty_trips_df() -> pd.DataFrame:
    return pd.DataFrame({
        "trip_id": pd.Series(dtype="Int64"),
        "trip_name": pd.Series(dtype="string"),
        "start_date": pd.Series(dtype="datetime64[ns]"),
        "end_date": pd.Series(dtype="datetime64[ns]"),
        "primary_city": pd.Series(dtype="string"),
        "country": pd.Series(dtype="string"),
        "lat": pd.Series(dtype="float"),
        "lon": pd.Series(dtype="float"),
        "total_cost_usd": pd.Series(dtype="float"),
        "transportation_cost_usd": pd.Series(dtype="float"),
        "accommodation_cost_usd": pd.Series(dtype="float"),
        "notes": pd.Series(dtype="string"),
    })

def empty_meals_df() -> pd.DataFrame:
    return pd.DataFrame({
        "meal_id": pd.Series(dtype="Int64"),
        "trip_id": pd.Series(dtype="Int64"),
        "date": pd.Series(dtype="datetime64[ns]"),
        "cuisine": pd.Series(dtype="string"),
        "restaurant": pd.Series(dtype="string"),
        "dish_name": pd.Series(dtype="string"),
        "rating_1_10": pd.Series(dtype="Int64"),
        "cost_usd": pd.Series(dtype="float"),
        "notes": pd.Series(dtype="string"),
    })

def year_series(dts):
    try:
        return dts.dt.year
    except Exception:
        return pd.to_datetime(dts, errors="coerce").dt.year

def apply_common_layout(fig, height=420):
    fig.update_layout(template="simple_white", height=height, margin=dict(t=30, r=10, l=10, b=10), coloraxis_showscale=False)
    return fig

from io import StringIO as _StringIO
def df_to_csv_bytes(df: pd.DataFrame) -> bytes:
    buf = _StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")

def template_trips_bytes() -> bytes:
    # headers + ONE EXAMPLE ROW
    df = pd.DataFrame([{
        "trip_id": 1,
        "trip_name": "Tokyo Spring Break",
        "start_date": "2023-03-15",
        "end_date": "2023-03-22",
        "primary_city": "Tokyo",
        "country": "Japan",
        "lat": 35.6895,
        "lon": 139.6917,
        "total_cost_usd": 2000,
        "transportation_cost_usd": 600,
        "accommodation_cost_usd": 800,
        "notes": "Cherry blossoms",
    }])
    return df_to_csv_bytes(df)

def template_meals_bytes() -> bytes:
    # headers + ONE EXAMPLE ROW
    df = pd.DataFrame([{
        "meal_id": 1,
        "trip_id": 1,
        "date": "2023-03-16",
        "cuisine": "Japanese",
        "restaurant": "Ichiran",
        "dish_name": "Tonkotsu Ramen",
        "rating_1_10": 9,
        "cost_usd": 12,
        "notes": "Late-night bowl",
    }])
    return df_to_csv_bytes(df)

def next_int(series):
    s = pd.to_numeric(series, errors="coerce").dropna().astype(int)
    return (s.max() + 1) if len(s) else 1

def fig_png_bytes(fig, scale=2):
    if not KALEIDO_OK:
        return None
    try:
        return fig.to_image(format="png", scale=scale)
    except Exception:
        return None

def add_download(fig, filename, key):
    png = fig_png_bytes(fig)
    if png:
        st.download_button("⬇️ Download PNG", data=png, file_name=filename, mime="image/png", key=key)

# -------------------------
#   SIDEBAR: How to Use, Uploads, Templates, Clear
# -------------------------
with st.sidebar.expander("ℹ️ How to use this app"):
    st.write("""
    1. Download the **sample CSVs** below.
    2. Open them in Excel or Google Sheets.
    3. Replace the example row with **your own trip and meal data**.
    4. Upload the updated files in the **Upload your data** section.
    5. Or, skip CSVs and use the **Add Trip / Add Meal** tabs to enter data directly.
    """)

st.sidebar.header("Upload your data (optional)")
up_trips = st.sidebar.file_uploader("Upload trips.csv", type=["csv"], key="uploader_trips")
up_meals = st.sidebar.file_uploader("Upload meals.csv", type=["csv"], key="uploader_meals")

st.sidebar.header("Download Templates")
st.sidebar.download_button("Download trips.csv template", data=template_trips_bytes(), file_name="trips.csv", mime="text/csv", key="tmpl_trips")
st.sidebar.download_button("Download meals.csv template", data=template_meals_bytes(), file_name="meals.csv", mime="text/csv", key="tmpl_meals")

col_clear1, col_clear2 = st.sidebar.columns(2)
with col_clear1:
    if st.button("Clear trips", use_container_width=True):
        st.session_state.trips_df = empty_trips_df()
        st.sidebar.success("Trips cleared.")
with col_clear2:
    if st.button("Clear meals", use_container_width=True):
        st.session_state.meals_df = empty_meals_df()
        st.sidebar.success("Meals cleared.")

# Initialize session-state authoritative copies
if "trips_df" not in st.session_state:
    st.session_state.trips_df = empty_trips_df()
if "meals_df" not in st.session_state:
    st.session_state.meals_df = empty_meals_df()

# Replace data immediately when files are uploaded
if up_trips is not None:
    try:
        trips_loaded = pd.read_csv(up_trips, parse_dates=["start_date", "end_date"])
    except Exception:
        trips_loaded = pd.read_csv(up_trips)
        for c in ["start_date", "end_date"]:
            if c in trips_loaded.columns:
                trips_loaded[c] = pd.to_datetime(trips_loaded[c], errors="coerce")
    st.session_state.trips_df = trips_loaded
    st.sidebar.success(f"Loaded {len(trips_loaded)} trip(s) from uploads.")

if up_meals is not None:
    try:
        meals_loaded = pd.read_csv(up_meals, parse_dates=["date"])
    except Exception:
        meals_loaded = pd.read_csv(up_meals)
        if "date" in meals_loaded.columns:
            meals_loaded["date"] = pd.to_datetime(meals_loaded["date"], errors="coerce")
    st.session_state.meals_df = meals_loaded
    st.sidebar.success(f"Loaded {len(meals_loaded)} meal(s) from uploads.")

trips = st.session_state.trips_df.copy()
meals = st.session_state.meals_df.copy()

# -------------------------
#   LIGHT SIDEBAR DIAGNOSTICS
# -------------------------
with st.sidebar.expander("Data check", expanded=False):
    st.write("**trips.csv columns:**")
    st.code(", ".join(map(str, trips.columns)))
    st.write("Rows:", len(trips))
    st.write("**meals.csv columns:**")
    st.code(", ".join(map(str, meals.columns)))
    st.write("Rows:", len(meals))
    st.write("Geocoder:", "✅ enabled" if GEOCODER_OK else "⚠️ add `geopy>=2.4` to requirements.txt")

# -------------------------
#   BASIC SCHEMA (ensure required cols exist even if empty)
# -------------------------
required_trip_cols = {"trip_id","trip_name","start_date","end_date","primary_city","country","lat","lon","total_cost_usd"}
missing = required_trip_cols - set(trips.columns)
if missing:
    templ = empty_trips_df()
    for col in missing:
        trips[col] = templ[col]
    st.session_state.trips_df = trips
    trips = st.session_state.trips_df

# -------------------------
#   DERIVED COLUMNS (safe on empty)
# -------------------------
for col in ["lat", "lon", "total_cost_usd", "transportation_cost_usd", "accommodation_cost_usd"]:
    if col in trips.columns:
        trips[col] = pd.to_numeric(trips[col], errors="coerce")

trips["start_date"] = pd.to_datetime(trips["start_date"], errors="coerce")
trips["end_date"] = pd.to_datetime(trips["end_date"], errors="coerce")
if len(trips):
    trips["days"] = (trips["end_date"] - trips["start_date"]).dt.days.clip(lower=1)
else:
    trips["days"] = pd.Series(dtype="Int64")

trips["cost_per_day"] = (
    pd.to_numeric(trips.get("total_cost_usd", pd.Series(dtype="float")), errors="coerce").fillna(0) /
    trips["days"].replace({0: 1})
).round(2)

# Compute food per trip from meals if present
if {"trip_id", "cost_usd"}.issubset(meals.columns) and len(meals):
    meals = meals.copy()
    meals["cost_usd"] = pd.to_numeric(meals["cost_usd"], errors="coerce").fillna(0)
    meals["trip_id"] = pd.to_numeric(meals["trip_id"], errors="coerce").astype("Int64")
    food_by_trip = meals.groupby("trip_id", dropna=False)["cost_usd"].sum().rename("food_cost_usd")
    trips = trips.drop(columns=[c for c in trips.columns if c.startswith("food_cost_usd")], errors="ignore")
    trips = trips.merge(food_by_trip, how="left", left_on="trip_id", right_index=True)
else:
    if "food_cost_usd" not in trips.columns:
        trips["food_cost_usd"] = 0

trips["food_cost_usd"] = pd.to_numeric(trips["food_cost_usd"], errors="coerce").fillna(0).clip(lower=0)
trips["year"] = year_series(pd.to_datetime(trips["start_date"], errors="coerce"))

# Write back (post-derivations)
st.session_state.trips_df = trips
st.session_state.meals_df = meals

# =========================
#   ➕ ADD / MANAGE DATA
# =========================
st.markdown("## ➕ Add / Manage Data")
tab_add_trip, tab_add_meal, tab_edit = st.tabs(["Add Trip", "Add Meal", "Edit Tables"])

with tab_add_trip:
    st.write("Add a new trip. Fields with * are required.")
    with st.form("form_add_trip", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            trip_name = st.text_input("Trip name *", placeholder="Tokyo Spring Break")
            primary_city = st.text_input("Primary city *", placeholder="Tokyo")
            country = st.text_input("Country *", placeholder="Japan")
        with c2:
            total_cost_usd = st.number_input("Total cost (USD) *", min_value=0.0, step=10.0)
            transportation_cost_usd = st.number_input("Transportation cost (USD)", min_value=0.0, step=5.0, value=0.0)
            accommodation_cost_usd = st.number_input("Accommodation cost (USD)", min_value=0.0, step=5.0, value=0.0)
            notes = st.text_input("Notes (optional)", placeholder="Cherry blossoms season")
        d1, d2 = st.columns(2)
        with d1:
            start_date = st.date_input("Start date *")
        with d2:
            end_date = st.date_input("End date *")
        auto_coords = st.checkbox("Auto-fill coordinates from city & country", value=True)
        submitted = st.form_submit_button("Add trip")

    if submitted:
        if not trip_name or not primary_city or not country or start_date is None or end_date is None:
            st.error("Please fill all required fields (marked with *).")
        elif pd.to_datetime(end_date) < pd.to_datetime(start_date):
            st.error("End date cannot be before start date.")
        else:
            lat_val, lon_val = (0.0, 0.0)
            if auto_coords:
                coords = geocode_city_country(primary_city, country)
                if coords:
                    lat_val, lon_val = coords
                else:
                    if GEOCODER_OK:
                        st.warning("Couldn’t auto-find coordinates for that city/country. Using (0.0, 0.0).")
                    else:
                        st.info("To enable auto-fill, add `geopy>=2.4` to requirements.txt.")

            cur = st.session_state.trips_df
            new_id = next_int(cur["trip_id"]) if "trip_id" in cur.columns else 1
            new_row = {
                "trip_id": new_id,
                "trip_name": trip_name,
                "start_date": pd.to_datetime(start_date),
                "end_date": pd.to_datetime(end_date),
                "primary_city": primary_city,
                "country": country,
                "lat": float(lat_val),
                "lon": float(lon_val),
                "total_cost_usd": float(total_cost_usd),
                "transportation_cost_usd": float(transportation_cost_usd),
                "accommodation_cost_usd": float(accommodation_cost_usd),
                "notes": notes,
            }
            st.session_state.trips_df = pd.concat([cur, pd.DataFrame([new_row])], ignore_index=True)
            st.success(f"Trip “{trip_name}” added!")

with tab_add_meal:
    st.write("Add a meal for one of the trips in view.")
    if st.session_state.trips_df.empty:
        st.info("Add a trip first.")
    else:
        with st.form("form_add_meal", clear_on_submit=True):
            colA, colB, colC = st.columns(3)
            with colA:
                trip_options = st.session_state.trips_df.sort_values("start_date")[["trip_id", "trip_name"]].copy()
                trip_options["label"] = trip_options["trip_name"] + " (" + trip_options["trip_id"].astype(str) + ")"
                trip_choice = st.selectbox("Trip *", trip_options["label"].tolist())
                cuisine = st.text_input("Cuisine *", placeholder="Japanese")
                restaurant = st.text_input("Restaurant", placeholder="Ichiran")
            with colB:
                dish_name = st.text_input("Dish name", placeholder="Tonkotsu Ramen")
                cost_usd = st.number_input("Cost (USD) *", min_value=0.0, step=1.0)
                rating_1_10 = st.slider("Rating (1–10) *", 1, 10, 8)
            with colC:
                date = st.date_input("Meal date *")
                notes_meal = st.text_input("Notes (optional)", placeholder="Late-night bowl.")
            submitted_meal = st.form_submit_button("Add meal")
        if submitted_meal:
            if not cuisine or date is None:
                st.error("Please complete all required fields.")
            else:
                try:
                    sel = trip_options.iloc[[trip_options["label"].tolist().index(trip_choice)]].iloc[0]
                    use_trip_id = int(sel["trip_id"])
                except Exception:
                    st.error("Could not read the selected trip. Please try again.")
                    use_trip_id = None
                if use_trip_id is not None:
                    cur = st.session_state.meals_df
                    new_meal_id = next_int(cur["meal_id"]) if "meal_id" in cur.columns else 1
                    new_row = {
                        "meal_id": new_meal_id,
                        "trip_id": use_trip_id,
                        "cuisine": cuisine,
                        "restaurant": restaurant,
                        "dish_name": dish_name,
                        "cost_usd": float(cost_usd),
                        "rating_1_10": int(rating_1_10),
                        "date": pd.to_datetime(date),
                        "notes": notes_meal,
                    }
                    st.session_state.meals_df = pd.concat([cur, pd.DataFrame([new_row])], ignore_index=True)
                    st.success(f"Meal “{dish_name or cuisine}” added to trip “{sel['trip_name']}”!")

with tab_edit:
    st.write("You can make quick edits below (affects this session only).")
    st.caption("Download buttons will save updated CSVs you can commit to your repo.")
    e1, e2 = st.columns(2)
    with e1:
        st.write("**Trips (editable)**")
        st.session_state.trips_df = st.data_editor(st.session_state.trips_df, use_container_width=True, num_rows="dynamic", key="edit_trips")
        if GEOCODER_OK and st.button("Auto-fill missing coordinates for existing trips"):
            df = st.session_state.trips_df.copy()
            miss = df["lat"].isna() | df["lon"].isna()
            filled = 0
            for idx, row in df.loc[miss].iterrows():
                city = str(row.get("primary_city") or "").strip()
                country = str(row.get("country") or "").strip()
                coords = geocode_city_country(city, country)
                if coords:
                    df.at[idx, "lat"], df.at[idx, "lon"] = coords
                    filled += 1
            st.session_state.trips_df = df
            st.success(f"Filled {filled} trip(s) with coordinates.")
        st.download_button("⬇️ Download updated trips.csv", data=df_to_csv_bytes(st.session_state.trips_df),
                           file_name="trips.csv", mime="text/csv", key="dl_trips_csv")
    with e2:
        st.write("**Meals (editable)**")
        meals_show = st.session_state.meals_df.copy()
        if "date" in meals_show.columns:
            meals_show["date"] = pd.to_datetime(meals_show["date"], errors="coerce").dt.date
        st.session_state.meals_df = st.data_editor(meals_show, use_container_width=True, num_rows="dynamic", key="edit_meals")
        if "date" in st.session_state.meals_df.columns:
            st.session_state.meals_df["date"] = pd.to_datetime(st.session_state.meals_df["date"], errors="coerce")
        st.download_button("⬇️ Download updated meals.csv", data=df_to_csv_bytes(st.session_state.meals_df),
                           file_name="meals.csv", mime="text/csv", key="dl_meals_csv")

# Refresh working copies and re-compute derived columns after edits
trips = st.session_state.trips_df.copy()
meals = st.session_state.meals_df.copy()
for col in ["lat", "lon", "total_cost_usd", "transportation_cost_usd", "accommodation_cost_usd"]:
    if col in trips.columns:
        trips[col] = pd.to_numeric(trips[col], errors="coerce")
trips["start_date"] = pd.to_datetime(trips["start_date"], errors="coerce")
trips["end_date"] = pd.to_datetime(trips["end_date"], errors="coerce")
if len(trips):
    trips["days"] = (trips["end_date"] - trips["start_date"]).dt.days.clip(lower=1)
else:
    trips["days"] = pd.Series(dtype="Int64")
trips["cost_per_day"] = (
    pd.to_numeric(trips.get("total_cost_usd", pd.Series(dtype="float")), errors="coerce").fillna(0) /
    trips["days"].replace({0: 1})
).round(2)
if {"trip_id", "cost_usd"}.issubset(meals.columns) and len(meals):
    meals["cost_usd"] = pd.to_numeric(meals["cost_usd"], errors="coerce").fillna(0)
    meals["trip_id"] = pd.to_numeric(meals["trip_id"], errors="coerce").astype("Int64")
    food_by_trip = meals.groupby("trip_id", dropna=False)["cost_usd"].sum().rename("food_cost_usd")
    trips = trips.drop(columns=[c for c in trips.columns if c.startswith("food_cost_usd")], errors="ignore")
    trips = trips.merge(food_by_trip, how="left", left_on="trip_id", right_index=True)
trips["food_cost_usd"] = pd.to_numeric(trips["food_cost_usd"], errors="coerce").fillna(0).clip(lower=0)
trips["year"] = year_series(pd.to_datetime(trips["start_date"], errors="coerce"))

# =========================
#   FILTERS & METRICS
# =========================
st.markdown("---")
st.sidebar.header("Filters")
countries = sorted(trips["country"].dropna().unique().tolist())
years = sorted(trips["year"].dropna().unique().tolist())
sel_countries = st.sidebar.multiselect("Country", countries, default=countries)
sel_years = st.sidebar.multiselect("Year", years, default=years)
search = st.sidebar.text_input("Search trips/cities", placeholder="e.g., Tokyo")
show_labels = st.sidebar.checkbox("Show values on bars", value=True)
sort_by = st.sidebar.selectbox("Sort bars by", ["Start date", "Trip name", "Value"], index=0)

mask = trips["country"].isin(sel_countries) & trips["year"].isin(sel_years) if len(trips) else pd.Series([], dtype=bool)
t = trips.loc[mask].copy() if len(trips) else trips.copy()
if len(t) and search:
    s = search.strip()
    search_mask = pd.Series(False, index=t.index)
    for c in ["trip_name", "primary_city"] + (["notes"] if "notes" in t.columns else []):
        search_mask |= t[c].astype(str).str.contains(s, case=False, na=False)
    t = t.loc[search_mask].copy()

# Metrics
c1, c2, c3, c4 = st.columns(4)
with c1: st.metric("Trips", f"{len(t)}")
with c2: st.metric("Countries", f"{t['country'].nunique() if len(t) else 0}")
with c3: st.metric("Total Spend (USD)", f"${int(pd.to_numeric(t.get('total_cost_usd', pd.Series(dtype='float')), errors='coerce').fillna(0).sum()):,}")
with c4: st.metric("Median Cost/Day", f"${(t['cost_per_day'].median() if len(t) else 0):,.2f}")

st.markdown("---")

# =========================
#   MAP + TOTAL SPEND
# =========================
col1, col2 = st.columns([1.25, 1])

with col1:
    st.subheader("🗺️ Where you've been")
    if len(t):
        fig_map = px.scatter_geo(
            t, lat="lat", lon="lon", hover_name="trip_name",
            hover_data={"country": True,"total_cost_usd": True,"days": True,"lat": False,"lon": False},
            projection="natural earth",
        )
        fig_map.update_traces(marker=dict(color="red", size=9, line=dict(width=1, color="black")))
        fig_map.update_geos(showcountries=True, showframe=False, landcolor="lightgray", oceancolor="lightblue", showocean=True)
        fig_map.update_layout(margin=dict(l=0,r=0,t=0,b=0), height=450, template="simple_white")
        st.plotly_chart(fig_map, use_container_width=True, config=PLOTLY_CONFIG)
        add_download(fig_map, "map.png", key="dl_map")
    else:
        st.info("No trips yet. Add your first trip in **Add / Manage Data → Add Trip**.")

with col2:
    st.subheader("💵 Total spend per trip")
    if len(t):
        if sort_by == "Start date":
            df_total = t.sort_values("start_date")
        elif sort_by == "Trip name":
            df_total = t.sort_values("trip_name")
        else:
            df_total = t.sort_values("total_cost_usd", ascending=False)
        fig_cost = px.bar(
            df_total, x="trip_name", y="total_cost_usd",
            labels={"trip_name": "Trip", "total_cost_usd": "USD"},
            color="total_cost_usd", color_continuous_scale="Tealgrn",
        )
        if show_labels:
            fig_cost.update_traces(text=df_total["total_cost_usd"].map(lambda v: f"${int(v):,}"),
                                   textposition="outside", cliponaxis=False)
        fig_cost.update_traces(hovertemplate="<b>%{x}</b><br>USD: %{y:,}<extra></extra>")
        fig_cost.update_layout(xaxis_tickangle=-20)
        apply_common_layout(fig_cost, height=450)
        st.plotly_chart(fig_cost, use_container_width=True, config=PLOTLY_CONFIG)
        add_download(fig_cost, "total_spend.png", key="dl_total")
    else:
        st.info("Add some trips to see spending charts.")

st.markdown("---")

# =========================
#   COST PER DAY
# =========================
st.subheader("🏆 Cost per day leaderboard")
if len(t):
    df_cpd = t.sort_values("cost_per_day", ascending=True).copy()
    fig_cpd = px.bar(
        df_cpd, x="cost_per_day", y="trip_name", orientation="h",
        labels={"cost_per_day": "USD per day","trip_name": "Trip"},
        color="cost_per_day", color_continuous_scale="Blugrn",
    )
    if show_labels:
        fig_cpd.update_traces(text=df_cpd["cost_per_day"].map(lambda v: f"${v:,.2f}"),
                              textposition="outside", cliponaxis=False)
    fig_cpd.update_traces(hovertemplate="<b>%{y}</b><br>USD/day: %{x:,.2f}<extra></extra>")
    apply_common_layout(fig_cpd, height=520)
    st.plotly_chart(fig_cpd, use_container_width=True, config=PLOTLY_CONFIG)
    add_download(fig_cpd, "cost_per_day.png", key="dl_cpd")
else:
    st.info("Add some trips to see the cost-per-day leaderboard.")

st.markdown("---")

# =========================
#   FOOD RATINGS
# =========================
st.subheader("🍴 Food Ratings")
if {"trip_id","cuisine","rating_1_10"}.issubset(meals.columns) and len(meals) and len(t):
    meals_r = meals.copy()
    meals_r["rating_1_10"] = pd.to_numeric(meals_r["rating_1_10"], errors="coerce")
    if "date" in meals_r.columns:
        meals_r["date_str"] = pd.to_datetime(meals_r["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    meals_r = meals_r[meals_r["trip_id"].isin(t["trip_id"])]
    meals_r = meals_r.merge(t[["trip_id", "trip_name"]], how="left", on="trip_id")

    if meals_r.empty:
        st.info("No meals match the current filters.")
    else:
        display_cols = [c for c in ["meal_id","trip_name","date_str","cuisine","restaurant","dish_name","rating_1_10","cost_usd"] if c in meals_r.columns]
        sort_col = "meal_id" if "meal_id" in meals_r.columns else "trip_name"
        table_df = meals_r[display_cols].sort_values(sort_col, ascending=True).reset_index(drop=True)
        table_df = table_df.rename(columns={"date_str": "date"})
        try:
            st.dataframe(table_df, use_container_width=True, hide_index=True)
        except TypeError:
            st.dataframe(table_df, use_container_width=True)

        top_cuisines = (
            meals_r.dropna(subset=["cuisine","rating_1_10"])
                   .groupby("cuisine", as_index=False)
                   .agg(avg_rating=("rating_1_10","mean"), count=("rating_1_10","size"))
                   .sort_values(["avg_rating","count"], ascending=[False,False])
        )
        fig_cuisine = px.bar(
            top_cuisines, x="cuisine", y="avg_rating",
            hover_data=["count"], labels={"avg_rating":"Avg Rating"},
            color="avg_rating", color_continuous_scale="Viridis", range_y=[0,10],
        )
        if show_labels:
            fig_cuisine.update_traces(text=top_cuisines["avg_rating"].map(lambda v: f"{v:.1f}"),
                                      textposition="outside", cliponaxis=False)
        fig_cuisine.update_layout(xaxis_tickangle=-30)
        apply_common_layout(fig_cuisine)
        st.plotly_chart(fig_cuisine, use_container_width=True, config=PLOTLY_CONFIG)
        add_download(fig_cuisine, "food_ratings_cuisines.png", key="dl_cuisine")
else:
    st.info("Add meals (and at least one trip) to see Food Ratings.")

st.markdown("---")

# =========================
#   TRANSPORT / FOOD / ACCOM
# =========================
st.subheader("🚗 Transportation spend per trip")
if "transportation_cost_usd" in t.columns and len(t) and t["transportation_cost_usd"].notna().any():
    df_tr = t.sort_values("start_date")
    fig_transport = px.bar(
        df_tr, x="trip_name", y="transportation_cost_usd",
        labels={"trip_name":"Trip","transportation_cost_usd":"USD"},
        color="transportation_cost_usd", color_continuous_scale="Tealgrn",
    )
    if show_labels:
        fig_transport.update_traces(text=df_tr["transportation_cost_usd"].fillna(0).map(lambda v: f"${int(v):,}"),
                                    textposition="outside", cliponaxis=False)
    fig_transport.update_traces(hovertemplate="<b>%{x}</b><br>USD: %{y:,}<extra></extra>")
    fig_transport.update_layout(xaxis_tickangle=-20)
    apply_common_layout(fig_transport)
    st.plotly_chart(fig_transport, use_container_width=True, config=PLOTLY_CONFIG)
    add_download(fig_transport,"transportation.png",key="dl_transport")
else:
    st.info("Add trips with transportation costs to see this chart.")

st.subheader("🍜 Food spend per trip")
if {"trip_id","cost_usd"}.issubset(meals.columns) and len(meals) and len(t):
    meals_f = meals.copy()
    meals_f["cost_usd"] = pd.to_numeric(meals_f["cost_usd"], errors="coerce").fillna(0)
    meals_f["trip_id"] = pd.to_numeric(meals_f["trip_id"], errors="coerce").astype("Int64")
    food_by_trip_f = meals_f.groupby("trip_id", dropna=False)["cost_usd"].sum().rename("food_cost_usd")

    tf = t.drop(columns=[c for c in t.columns if c.startswith("food_cost_usd")], errors="ignore")
    tf = tf.merge(food_by_trip_f, how="left", left_on="trip_id", right_index=True)
    tf["food_cost_usd"] = pd.to_numeric(tf["food_cost_usd"], errors="coerce").fillna(0)

    df_food = tf.sort_values("start_date")
    fig_food = px.bar(
        df_food, x="trip_name", y="food_cost_usd",
        labels={"trip_name":"Trip","food_cost_usd":"USD"},
        color="food_cost_usd", color_continuous_scale="Viridis",
    )
    if show_labels:
        fig_food.update_traces(text=df_food["food_cost_usd"].map(lambda v: f"${int(v):,}"),
                               textposition="outside", cliponaxis=False)
    fig_food.update_traces(hovertemplate="<b>%{x}</b><br>USD: %{y:,}<extra></extra>")
    fig_food.update_layout(xaxis_tickangle=-20)
    apply_common_layout(fig_food)
    st.plotly_chart(fig_food, use_container_width=True, config=PLOTLY_CONFIG)
    add_download(fig_food,"food_spend.png",key="dl_food")
else:
    st.info("Add meals to see food totals per trip.")

st.subheader("🏨 Accommodation spend per trip")
if "accommodation_cost_usd" in t.columns and len(t) and t["accommodation_cost_usd"].notna().any():
    df_ac = t.sort_values("start_date")
    fig_accom = px.bar(
        df_ac, x="trip_name", y="accommodation_cost_usd",
        labels={"trip_name":"Trip","accommodation_cost_usd":"USD"},
        color="accommodation_cost_usd", color_continuous_scale="Purples",
    )
    if show_labels:
        fig_accom.update_traces(text=df_ac["accommodation_cost_usd"].fillna(0).map(lambda v: f"${int(v):,}"),
                                textposition="outside", cliponaxis=False)
    fig_accom.update_traces(hovertemplate="<b>%{x}</b><br>USD: %{y:,}<extra></extra>")
    fig_accom.update_layout(xaxis_tickangle=-20)
    apply_common_layout(fig_accom)
    st.plotly_chart(fig_accom, use_container_width=True, config=PLOTLY_CONFIG)
    add_download(fig_accom,"accommodation.png",key="dl_accom")
else:
    st.info("Add trips with accommodation costs to see this chart.")

# =========================
#   FOOTER LINK
# =========================
st.markdown("---")
st.markdown("🌍 Check out more travel stories at [somewhere-else.org](https://somewhere-else.org)", unsafe_allow_html=True)