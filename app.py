# --- Travel Dashboard (Streamlit) ---
# Full app with compact PDF export (2 charts/page), poetic Executive Summary,
# Exec+Snapshots on first PDF page, centered "Trips by Region" donut (clean, percent-only),
# no watermark; legends hidden. Axis spacing fixes added to horizontal bars.

import os
import base64
from io import StringIO as _StringIO, BytesIO
from datetime import datetime
import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Travel Dashboard", page_icon="🌍", layout="wide")

# =========================
#   Global CSS / Layout
# =========================
st.markdown("""
<style>
:root { --safe-top: env(safe-area-inset-top, 0px); }
[data-testid="stAppViewContainer"], main[data-testid="block-container"] {
  padding-top: calc(24px + var(--safe-top)) !important;
}
[data-testid="stAppViewContainer"] > div:first-child { overflow: visible !important; }

/* Sidebar (navy) */
section[data-testid="stSidebar"], [data-testid="stSidebar"] {
  background-color: #0f2557 !important; color: #f5f7fa !important;
  border-right: 1px solid #0a1a34 !important; position: relative; z-index: 2;
}
[data-testid="stSidebar"] > div:first-child, [data-testid="stSidebar"] [data-testid="stSidebarContent"] {
  background-color: transparent !important; padding: 0.8rem !important;
}
[data-testid="stSidebar"] * { color: #f5f7fa !important; }
[data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3, [data-testid="stSidebar"] label { color: #e8ecf5 !important; }
[data-testid="stSidebar"] input, [data-testid="stSidebar"] textarea, [data-testid="stSidebar"] select {
  background: #0a1a34 !important; color: #f5f7fa !important; border: 1px solid #1c366a !important;
}
[data-testid="stSidebar"] [data-testid="stExpander"] > div {
  background: #142f66 !important; border: 1px solid #1c3d80 !important; border-radius: 10px !important;
}

/* Plotly bg transparent */
.js-plotly-plot .plotly .bg { fill: rgba(255,255,255,0.0) !important; }

/* Main glass look */
.block-container {
  background: rgba(255,255,255,0.60); backdrop-filter: blur(6px); -webkit-backdrop-filter: blur(6px);
  border-radius: 16px; padding: 1.2rem 1.4rem; box-shadow: 0 10px 30px rgba(0,0,0,0.08);
  position: relative; z-index: 1;
}

/* Topbar */
.topbar {
  position: sticky; top: 0; z-index: 1000;
  background: rgba(15,37,87,0.92); color: #fff; padding: 14px 18px; margin: 0 -1rem 1rem -1rem;
  border-bottom: 1px solid rgba(255,255,255,0.12); border-radius: 0 0 12px 12px;
  padding-top: calc(14px + var(--safe-top)) !important; box-sizing: border-box;
}
.topbar h1 { margin: 0; font-size: 1.6rem; line-height: 1.2; }
.topbar .sub { font-size: 0.95rem; opacity: 0.95; margin-top: 2px; }

/* Spacer */
#top-spacer { height: 36px; }
</style>
""", unsafe_allow_html=True)

# =========================
#   Background image
# =========================
def inject_background(img_bytes: bytes | None):
    if not img_bytes:
        st.markdown("""
<div id="app-bg" style="position:fixed; inset:0; z-index:0; pointer-events:none; overflow:hidden;
background:
  radial-gradient(circle at center, rgba(0,0,0,0.0) 62%, rgba(0,0,0,0.50) 100%),
  linear-gradient(180deg, #e9edf3 0%, #f6f7fb 100%);"></div>
""", unsafe_allow_html=True)
        return
    b64 = base64.b64encode(img_bytes).decode("ascii")
    st.markdown(f"""
<div id="app-bg" style="position:fixed; inset:0; z-index:0; pointer-events:none; overflow:hidden;">
  <img src="data:image/jpeg;base64,{b64}"
       style="width:100%; height:100%; object-fit:cover; filter:brightness(0.9) contrast(1.05);" />
  <div style="position:absolute; inset:0;
              background: radial-gradient(circle at center, rgba(0,0,0,0.0) 65%, rgba(0,0,0,0.55) 100%);">
  </div>
</div>
""", unsafe_allow_html=True)

bg_bytes = None
if os.path.exists("background.jpg"):
    try:
        with open("background.jpg", "rb") as f:
            bg_bytes = f.read()
    except Exception:
        bg_bytes = None
inject_background(bg_bytes)

# =========================
#   Export support (PNG/PDF)
# =========================
try:
    import kaleido  # noqa: F401
    KALEIDO_OK = True
except Exception:
    KALEIDO_OK = False

REPORTLAB_OK = False
try:
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.utils import ImageReader
    from reportlab.lib.colors import HexColor
    from reportlab.platypus import Paragraph, Frame
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_LEFT
    REPORTLAB_OK = True
except Exception:
    REPORTLAB_OK = False

PLOTLY_CONFIG = {"displaylogo": False, "modeBarButtonsToAdd": ["toImage"] if not KALEIDO_OK else []}

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

def df_to_csv_bytes(df: pd.DataFrame) -> bytes:
    buf = _StringIO(); df.to_csv(buf, index=False); return buf.getvalue().encode("utf-8")

def template_trips_bytes() -> bytes:
    df = pd.DataFrame([{
        "trip_id": 1, "trip_name": "Tokyo Spring Break",
        "start_date": "2023-03-15", "end_date": "2023-03-22",
        "primary_city": "Tokyo", "country": "Japan", "lat": 35.6895, "lon": 139.6917,
        "total_cost_usd": 2000, "transportation_cost_usd": 600, "accommodation_cost_usd": 800,
        "activities_cost_usd": 250, "food_cost_usd": 300, "internet_speed_mbps": 45,
    }])
    return df_to_csv_bytes(df)

def template_meals_bytes() -> bytes:
    df = pd.DataFrame([{
        "meal_id": 1, "trip_id": 1, "date": "2023-03-16",
        "cuisine": "Japanese", "restaurant": "Ichiran", "dish_name": "Tonkotsu Ramen",
        "rating_1_10": 9, "cost_usd": 12,
    }])
    return df_to_csv_bytes(df)

def next_int(series):
    s = pd.to_numeric(series, errors="coerce").dropna().astype(int)
    return (s.max() + 1) if len(s) else 1

def fmt_money(x, zero_str="$0"):
    try:
        x = float(x); return f"${x:,.0f}" if x else zero_str
    except Exception:
        return "—"

# =========================
#   Geocoder (optional)
# =========================
try:
    from geopy.geocoders import Nominatim
    from geopy.extra.rate_limiter import RateLimiter
    GEOCODER_OK = True
except Exception:
    GEOCODER_OK = False

@st.cache_data(show_spinner=False)
def geocode_city_country(city: str, country: str):
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

# =========================
#   Helpers / Empty DFs
# =========================
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
        "activities_cost_usd": pd.Series(dtype="float"),
        "food_cost_usd": pd.Series(dtype="float"),
        "internet_speed_mbps": pd.Series(dtype="float"),
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
    })

def year_series(dts):
    try: return dts.dt.year
    except Exception: return pd.to_datetime(dts, errors="coerce").dt.year

# ---------- Region mapping & helpers ----------
REGION_MAP = {
    "Western Europe": {"France","Germany","Netherlands","Belgium","Luxembourg","Switzerland","Austria","United Kingdom","Ireland","Monaco","Liechtenstein"},
    "Southern Europe": {"Italy","Spain","Portugal","Greece","Croatia","Slovenia","Malta","Cyprus"},
    "Northern Europe": {"Denmark","Norway","Sweden","Finland","Iceland","Estonia","Latvia","Lithuania"},
    "Eastern Europe": {"Poland","Czechia","Czech Republic","Slovakia","Hungary","Romania","Bulgaria","Ukraine","Moldova","Belarus"},
    "Southeast Asia": {"Thailand","Vietnam","Cambodia","Laos","Myanmar","Malaysia","Singapore","Indonesia","Philippines","Brunei","Timor-Leste"},
    "East Asia": {"Japan","China","South Korea","North Korea","Taiwan","Mongolia","Hong Kong","Macau"},
    "South Asia": {"India","Pakistan","Bangladesh","Sri Lanka","Nepal","Bhutan","Maldives"},
    "Middle East": {"United Arab Emirates","Saudi Arabia","Qatar","Bahrain","Kuwait","Oman","Jordan","Lebanon","Israel","Palestine","Iran","Iraq","Turkey"},
    "Africa": {"Morocco","Egypt","Kenya","Tanzania","South Africa","Namibia","Ethiopia","Ghana","Nigeria","Rwanda","Uganda","Botswana","Zambia","Tunisia"},
    "North America": {"United States","USA","Canada","Mexico"},
    "Central America & Caribbean": {"Costa Rica","Panama","Guatemala","Belize","Honduras","Nicaragua","El Salvador","Cuba","Jamaica","Dominican Republic","Bahamas","Barbados","Trinidad and Tobago"},
    "South America": {"Brazil","Argentina","Chile","Peru","Colombia","Ecuador","Uruguay","Paraguay","Bolivia","Venezuela"},
    "Oceania": {"Australia","New Zealand","Fiji","Samoa","Tonga","Vanuatu"},
}

def detect_regions(countries: list[str]) -> list[str]:
    counts = {}
    for c in countries:
        for region, members in REGION_MAP.items():
            if str(c) in members:
                counts[region] = counts.get(region, 0) + 1
    if not counts:
        return []
    return [r for r, _ in sorted(counts.items(), key=lambda x: (-x[1], x[0]))]

def to_list_text(items: list[str], max_items=3) -> str:
    items = [str(i) for i in items if str(i).strip()]
    if not items:
        return ""
    items = items[:max_items]
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return f"{', '.join(items[:-1])}, and {items[-1]}"

def region_counts_df(trips_df: pd.DataFrame) -> pd.DataFrame:
    if trips_df is None or trips_df.empty or "country" not in trips_df.columns:
        return pd.DataFrame(columns=["region","count"])
    rows = []
    for ctry in trips_df["country"].dropna():
        placed = False
        for region, members in REGION_MAP.items():
            if str(ctry) in members:
                rows.append(region); placed = True; break
        if not placed:
            rows.append("Other")
    if not rows:
        return pd.DataFrame(columns=["region","count"])
    s = pd.Series(rows).value_counts().reset_index()
    s.columns = ["region","count"]
    return s

# =========================
#   Sidebar
# =========================
with st.sidebar.expander("ℹ️ How to use this app"):
    st.write("""
    1. Download the sample CSVs below.
    2. Open them in Excel or Google Sheets.
    3. Replace the example row with your own data.
    4. Upload the updated files in the Upload section.
    5. Or, skip CSVs and use Add Trip / Add Meal to enter data directly.
    """)

st.sidebar.header("Upload your data (optional)")
up_trips = st.sidebar.file_uploader("Upload trips.csv", type=["csv"], key="uploader_trips")
up_meals = st.sidebar.file_uploader("Upload meals.csv", type=["csv"], key="uploader_meals")

st.sidebar.header("Map options")
color_by_speed = st.sidebar.checkbox("Color markers by internet speed", value=False)

st.sidebar.header("Download Templates")
st.sidebar.download_button("Download trips.csv template", data=template_trips_bytes(), file_name="trips.csv", mime="text/csv", key="tmpl_trips")
st.sidebar.download_button("Download meals.csv template", data=template_meals_bytes(), file_name="meals.csv", mime="text/csv", key="tmpl_meals")

# Clear
col_clear1, col_clear2 = st.sidebar.columns(2)
with col_clear1:
    if st.button("Clear trips", use_container_width=True):
        st.session_state.trips_df = empty_trips_df()
        st.sidebar.success("Trips cleared.")
with col_clear2:
    if st.button("Clear meals", use_container_width=True):
        st.session_state.meals_df = empty_meals_df()
        st.sidebar.success("Meals cleared.")

# Init session dataframes
if "trips_df" not in st.session_state: st.session_state.trips_df = empty_trips_df()
if "meals_df" not in st.session_state: st.session_state.meals_df = empty_meals_df()

# Load uploads
if up_trips is not None:
    try:
        trips_loaded = pd.read_csv(up_trips, parse_dates=["start_date", "end_date"])
    except Exception:
        trips_loaded = pd.read_csv(up_trips)
        for c in ["start_date", "end_date"]:
            if c in trips_loaded.columns:
                trips_loaded[c] = pd.to_datetime(trips_loaded[c], errors="coerce")
    st.session_state.trips_df = trips_loaded
    st.sidebar.success(f"Loaded {len(trips_loaded)} trip(s).")

if up_meals is not None:
    try:
        meals_loaded = pd.read_csv(up_meals, parse_dates=["date"])
    except Exception:
        meals_loaded = pd.read_csv(up_meals)
        if "date" in meals_loaded.columns:
            meals_loaded["date"] = pd.to_datetime(meals_loaded["date"], errors="coerce")
    st.session_state.meals_df = meals_loaded
    st.sidebar.success(f"Loaded {len(meals_loaded)} meal(s).")

trips = st.session_state.trips_df.copy()
meals = st.session_state.meals_df.copy()

# Ensure columns
required_trip_cols = {"trip_id","trip_name","start_date","end_date","primary_city","country","lat","lon","total_cost_usd"}
missing = required_trip_cols - set(trips.columns)
if missing:
    templ = empty_trips_df()
    for col in missing: trips[col] = templ[col]

for col in ["internet_speed_mbps", "activities_cost_usd", "food_cost_usd","transportation_cost_usd", "accommodation_cost_usd"]:
    if col not in trips.columns: trips[col] = pd.Series(dtype="float")

# Derived columns
for col in ["lat","lon","total_cost_usd","transportation_cost_usd","accommodation_cost_usd","activities_cost_usd","food_cost_usd","internet_speed_mbps"]:
    if col in trips.columns: trips[col] = pd.to_numeric(trips[col], errors="coerce")
trips["start_date"] = pd.to_datetime(trips["start_date"], errors="coerce")
trips["end_date"] = pd.to_datetime(trips["end_date"], errors="coerce")
trips["days"] = ((trips["end_date"] - trips["start_date"]).dt.days.clip(lower=1) if len(trips) else pd.Series(dtype="Int64"))
trips["cost_per_day"] = (pd.to_numeric(trips.get("total_cost_usd", pd.Series(dtype="float")), errors="coerce").fillna(0) / trips["days"].replace({0:1})).round(2)

# Food from meals
if {"trip_id","cost_usd"}.issubset(meals.columns) and len(meals):
    meals = meals.copy()
    meals["cost_usd"] = pd.to_numeric(meals["cost_usd"], errors="coerce").fillna(0)
    meals["trip_id"] = pd.to_numeric(meals["trip_id"], errors="coerce").astype("Int64")
    food_from_meals = meals.groupby("trip_id", dropna=False)["cost_usd"].sum().rename("food_cost_usd_from_meals")
    trips = trips.merge(food_from_meals, how="left", left_on="trip_id", right_index=True)
else:
    trips["food_cost_usd_from_meals"] = pd.Series(dtype="float")

trips["food_cost_usd"] = pd.to_numeric(trips.get("food_cost_usd"), errors="coerce")
trips["food_cost_usd_final"] = (trips["food_cost_usd_from_meals"].where(trips["food_cost_usd_from_meals"].notna(), trips["food_cost_usd"])).fillna(0).clip(lower=0)
trips["year"] = year_series(pd.to_datetime(trips["start_date"], errors="coerce"))

st.session_state.trips_df = trips
st.session_state.meals_df = meals

# =========================
#   Header
# =========================
st.markdown('<div id="top-spacer"></div>', unsafe_allow_html=True)
st.markdown("""
<div class="topbar">
  <h1>🌍 Travel Dashboard</h1>
  <div class="sub">Track trips, meals, and costs • somewhere-else.org</div>
</div>
""", unsafe_allow_html=True)

# =========================
#   Add / Manage Data
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
            total_cost_usd = st.number_input("Total cost *", min_value=0.0, step=10.0)
            transportation_cost_usd = st.number_input("Transportation cost", min_value=0.0, step=5.0, value=0.0)
            accommodation_cost_usd = st.number_input("Accommodation cost", min_value=0.0, step=5.0, value=0.0)

        meal_col, act_col = st.columns(2)
        with meal_col:
            meal_cost_total_usd = st.number_input("Meal cost (trip total)", min_value=0.0, step=5.0, value=0.0)
        with act_col:
            activities_cost_usd = st.number_input("Activities cost", min_value=0.0, step=5.0, value=0.0)

        d1, d2 = st.columns(2)
        with d1: start_date = st.date_input("Start date *")
        with d2: end_date = st.date_input("End date *")

        auto_coords = st.checkbox("Auto-fill coordinates from city & country", value=True)
        submitted = st.form_submit_button("Add trip")

    if submitted:
        if not trip_name or not primary_city or not country or start_date is None or end_date is None:
            st.error("Please fill all required fields (marked with *).")
        elif pd.to_datetime(end_date) < pd.to_datetime(start_date):
            st.error("End date cannot be before start date.")
        else:
            lat_val, lon_val = (0.0, 0.0)
            if auto_coords and GEOCODER_OK:
                coords = geocode_city_country(primary_city, country)
                if coords: lat_val, lon_val = coords
                else: st.warning("Couldn’t auto-find coordinates. Using (0.0, 0.0).")
            elif auto_coords and not GEOCODER_OK:
                st.info("To enable auto-fill, add `geopy>=2.4` to requirements.txt.")
            cur = st.session_state.trips_df
            new_id = next_int(cur["trip_id"]) if "trip_id" in cur.columns else 1
            new_row = {
                "trip_id": new_id, "trip_name": trip_name,
                "start_date": pd.to_datetime(start_date), "end_date": pd.to_datetime(end_date),
                "primary_city": primary_city, "country": country, "lat": float(lat_val), "lon": float(lon_val),
                "total_cost_usd": float(total_cost_usd), "transportation_cost_usd": float(transportation_cost_usd),
                "accommodation_cost_usd": float(accommodation_cost_usd), "activities_cost_usd": float(activities_cost_usd),
                "food_cost_usd": float(meal_cost_total_usd),
            }
            st.session_state.trips_df = pd.concat([cur, pd.DataFrame([new_row])], ignore_index=True)
            st.success(f'Trip "{trip_name}" added!')

with tab_add_meal:
    st.write("Add a meal for one of the trips in view.")
    if st.session_state.trips_df.empty:
        st.info("Add a trip first.")
    else:
        with st.form("form_add_meal", clear_on_submit=True):
            colA, colB, colC = st.columns(3)
            with colA:
                trip_options = st.session_state.trips_df.sort_values("start_date")[["trip_id","trip_name"]].copy()
                trip_options["label"] = trip_options["trip_name"] + " (" + trip_options["trip_id"].astype(str) + ")"
                trip_choice = st.selectbox("Trip *", trip_options["label"].tolist())
                cuisine = st.text_input("Cuisine *", placeholder="Japanese")
                restaurant = st.text_input("Restaurant", placeholder="Ichiran")
            with colB:
                dish_name = st.text_input("Dish name", placeholder="Tonkotsu Ramen")
                cost_usd = st.number_input("Cost *", min_value=0.0, step=1.0)
                rating_1_10 = st.slider("Rating (1–10) *", 1, 10, 8)
            with colC:
                date = st.date_input("Meal date *")
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
                        "meal_id": new_meal_id, "trip_id": use_trip_id, "cuisine": cuisine,
                        "restaurant": restaurant, "dish_name": dish_name,
                        "cost_usd": float(cost_usd), "rating_1_10": int(rating_1_10),
                        "date": pd.to_datetime(date),
                    }
                    st.session_state.meals_df = pd.concat([cur, pd.DataFrame([new_row])], ignore_index=True)
                    st.success(f'Meal "{dish_name or cuisine}" added to trip "{sel["trip_name"]}"!')

with tab_edit:
    st.write("You can make quick edits below (affects this session only).")
    st.caption("Download buttons will save updated CSVs you can commit to your repo.")
    e1, e2 = st.columns(2)
    with e1:
        st.write("**Trips (editable)**")
        st.session_state.trips_df = st.data_editor(st.session_state.trips_df, use_container_width=True, num_rows="dynamic", key="edit_trips")
        if GEOCODER_OK and st.button("Auto-fill missing coordinates for existing trips"):
            df = st.session_state.trips_df.copy()
            miss = df["lat"].isna() | df["lon"].isna(); filled = 0
            for idx, row in df.loc[miss].iterrows():
                city = str(row.get("primary_city") or "").strip()
                country = str(row.get("country") or "").strip()
                coords = geocode_city_country(city, country)
                if coords: df.at[idx, "lat"], df.at[idx, "lon"] = coords; filled += 1
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

# Refresh and re-derive
trips = st.session_state.trips_df.copy()
meals = st.session_state.meals_df.copy()
for col in ["lat","lon","total_cost_usd","transportation_cost_usd","accommodation_cost_usd","activities_cost_usd","food_cost_usd","internet_speed_mbps"]:
    if col in trips.columns: trips[col] = pd.to_numeric(trips[col], errors="coerce")
trips["start_date"] = pd.to_datetime(trips["start_date"], errors="coerce")
trips["end_date"] = pd.to_datetime(trips["end_date"], errors="coerce")
trips["days"] = ((trips["end_date"] - trips["start_date"]).dt.days.clip(lower=1) if len(trips) else pd.Series(dtype="Int64"))
trips["cost_per_day"] = (pd.to_numeric(trips.get("total_cost_usd", pd.Series(dtype="float")), errors="coerce").fillna(0) / trips["days"].replace({0:1})).round(2)

if {"trip_id","cost_usd"}.issubset(meals.columns) and len(meals):
    meals["cost_usd"] = pd.to_numeric(meals["cost_usd"], errors="coerce").fillna(0)
    meals["trip_id"] = pd.to_numeric(meals["trip_id"], errors="coerce").astype("Int64")
    food_from_meals = meals.groupby("trip_id", dropna=False)["cost_usd"].sum().rename("food_cost_usd_from_meals")
    trips = trips.drop(columns=["food_cost_usd_from_meals"], errors="ignore").merge(food_from_meals, how="left", left_on="trip_id", right_index=True)
else:
    trips["food_cost_usd_from_meals"] = trips.get("food_cost_usd_from_meals", pd.Series(dtype="float"))

trips["food_cost_usd"] = pd.to_numeric(trips.get("food_cost_usd"), errors="coerce")
trips["food_cost_usd_final"] = (trips["food_cost_usd_from_meals"].where(trips["food_cost_usd_from_meals"].notna(), trips["food_cost_usd"])).fillna(0).clip(lower=0)
trips["year"] = year_series(pd.to_datetime(trips["start_date"], errors="coerce"))

st.session_state.trips_df = trips
st.session_state.meals_df = meals

# =========================
#   Filters & metrics
# =========================
st.markdown("---")
st.sidebar.header("Filters")
countries = sorted(trips["country"].dropna().unique().tolist()) if len(trips) else []
years = sorted(trips["year"].dropna().unique().tolist()) if len(trips) else []
sel_countries = st.sidebar.multiselect("Country", countries, default=countries)
sel_years = st.sidebar.multiselect("Year", years, default=years)
search = st.sidebar.text_input("Search trips/cities", placeholder="e.g., Tokyo")
show_labels = st.sidebar.checkbox("Show values on bars", value=True)
sort_by = st.sidebar.selectbox("Sort bars by", ["Start date", "Trip name", "Value"], index=0)

mask = trips["country"].isin(sel_countries) & trips["year"].isin(sel_years) if len(trips) else pd.Series([], dtype=bool)
t = trips.loc[mask].copy() if len(trips) else trips
if len(t) and search:
    s = search.strip()
    search_mask = pd.Series(False, index=t.index)
    for c in ["trip_name","primary_city"]:
        search_mask |= t[c].astype(str).str.contains(s, case=False, na=False)
    t = t.loc[search_mask].copy()

total_spend = t["total_cost_usd"].sum() if len(t) else 0
total_days = t["days"].sum() if len(t) else 0
avg_cpd_weighted = (total_spend / total_days) if total_days and total_spend else 0
med_cpd = t["cost_per_day"].median() if len(t) else 0
avg_speed = t["internet_speed_mbps"].dropna().mean() if "internet_speed_mbps" in t.columns and len(t) else float("nan")
speed_series = t["internet_speed_mbps"].dropna() if "internet_speed_mbps" in t.columns else pd.Series(dtype="float")
pct_good = ((speed_series >= 25).mean()*100) if len(speed_series) else float("nan")

c1, c2, c3, c4, c5, c6 = st.columns(6)
with c1: st.metric("Trips", f"{len(t)}")
with c2: st.metric("Countries", f"{t['country'].nunique() if len(t) else 0}")
with c3: st.metric("Total Spend", f"${total_spend:,.0f}")
with c4: st.metric("Median Cost/Day", f"${med_cpd:,.2f}")
with c5: st.metric("Avg Internet Speed", f"{avg_speed:.1f} Mbps" if pd.notnull(avg_speed) else "—")
with c6: st.metric("Trips ≥25 Mbps", f"{pct_good:.0f}%" if pd.notnull(pct_good) else "—")

if len(t):
    min_d = pd.to_datetime(t["start_date"], errors="coerce").min()
    max_d = pd.to_datetime(t["end_date"], errors="coerce").max()
    date_range_str = f"Coverage: {min_d.strftime('%Y-%m-%d')} → {max_d.strftime('%Y-%m-%d')}" if pd.notnull(min_d) and pd.notnull(max_d) else ""
else:
    date_range_str = ""

filters_summary = []
if sel_countries and len(sel_countries) < max(1, len(countries)):
    filters_summary.append("Countries: " + (", ".join(sel_countries) if len(sel_countries) <= 5 else f"{len(sel_countries)} selected"))
if sel_years and len(sel_years) < max(1, len(years)):
    filters_summary.append("Years: " + ", ".join(map(str, sel_years)))
if search.strip():
    filters_summary.append(f'Search: "{search.strip()}"')
if not filters_summary:
    filters_summary = ["No filters applied"]

top_spend = (t.sort_values("total_cost_usd", ascending=False)["trip_name"].head(3).tolist() if len(t) else [])
top_line = f"Top by total spend: {', '.join(top_spend)}" if top_spend else "Add trips to see top destinations"

# -------------------------
#   Poetic Executive summary
# -------------------------
def build_poetic_story(trips_df: pd.DataFrame, meals_df: pd.DataFrame) -> str:
    if trips_df is None or len(trips_df) == 0:
        return "No trips yet. Add your first trip to begin the story."

    cities = [str(c) for c in trips_df["primary_city"].dropna().tolist()]
    countries_list = [str(c) for c in trips_df["country"].dropna().tolist()]
    regions = detect_regions(countries_list)
    main_region = regions[0] if regions else ""
    city_sample = to_list_text(pd.Series(cities).dropna().unique().tolist(), max_items=3)
    country_sample = to_list_text(pd.Series(countries_list).dropna().unique().tolist(), max_items=3)

    cpd_median = trips_df["cost_per_day"].median()
    avg_speed_ = trips_df["internet_speed_mbps"].dropna().mean() if "internet_speed_mbps" in trips_df.columns else float("nan")

    best_food_trip = None
    if meals_df is not None and len(meals_df) and "rating_1_10" in meals_df.columns:
        m = meals_df.dropna(subset=["rating_1_10"]).copy()
        if len(m):
            m = m.groupby("trip_id", as_index=False)["rating_1_10"].mean().rename(columns={"rating_1_10":"avg_rating"})
            m = m.merge(trips_df[["trip_id","trip_name"]], on="trip_id", how="left")
            m = m.sort_values("avg_rating", ascending=False)
            if len(m):
                best_food_trip = f"{m.iloc[0]['trip_name']} ({m.iloc[0]['avg_rating']:.1f}/10)"

    sd_min = pd.to_datetime(trips_df["start_date"], errors="coerce").min()
    ed_max = pd.to_datetime(trips_df["end_date"], errors="coerce").max()
    time_window = ""
    if pd.notnull(sd_min) and pd.notnull(ed_max):
        if sd_min.year == ed_max.year:
            time_window = f"in {sd_min.strftime('%Y')}"
        else:
            time_window = f"from {sd_min.strftime('%Y')} to {ed_max.strftime('%Y')}"

    lines = []
    if main_region:
        lines.append(f"Your path arcs across <b>{main_region}</b> — ")
    else:
        lines.append("Your path arcs across the map — ")

    if city_sample:
        lines.append(f"lingering in <b>{city_sample}</b>, ")
    if country_sample:
        lines.append(f"wandering through <b>{country_sample}</b>, ")
    if time_window:
        lines.append(f"{time_window}. ")
    else:
        lines.append("in recent travels. ")

    lines.append("Between train stations and café tables, the days gathered their own rhythm. ")

    if pd.notnull(cpd_median):
        lines.append(f"On average, each day balanced out to about <b>${cpd_median:,.2f}</b>. ")

    if pd.notnull(avg_speed_):
        lines.append(f"Connections held at roughly <b>{avg_speed_:.1f} Mbps</b>, enough to send notes home and keep work aloft. ")

    if best_food_trip:
        lines.append(f"Along the way, flavors sang — with <b>{best_food_trip}</b> tasting most like a memory you’ll revisit. ")

    lines.append("What remains are scenes: streetlights blinking awake, small kindnesses in unfamiliar places, and a map dotted with places that now know your name.")
    return "".join(lines)

def build_exec_summary(trips_df: pd.DataFrame, meals_df: pd.DataFrame) -> str:
    return build_poetic_story(trips_df, meals_df)

cover_info = {
    "title": "Travel Dashboard Report",
    "subtitle": "Trips, meals, costs & connectivity at a glance",
    "daterange": date_range_str,
    "metrics": {
        "Trips": f"{len(t)}",
        "Countries": f"{t['country'].nunique() if len(t) else 0}",
        "Total Spend": f"${total_spend:,.0f}",
        "Median Cost/Day": f"${med_cpd:,.2f}",
        "Avg Internet Speed": f"{avg_speed:.1f} Mbps" if pd.notnull(avg_speed) else "—",
        "Trips ≥25 Mbps": f"{pct_good:.0f}%" if pd.notnull(pct_good) else "—",
    },
    "overview_lines": [*filters_summary, top_line],
    "exec_summary": build_exec_summary(t, meals),
}

# =========================
#   Charts (legends OFF)
# =========================
def _hide_legends(fig):
    fig.update_layout(showlegend=False)
    try:
        fig.update_coloraxes(showscale=False)
    except Exception:
        pass
    return fig

report_sections = []

col1, col2 = st.columns([1.25, 1])
with col1:
    st.subheader("🗺️ Where you've been")
    if len(t):
        hover_data = {"country": True, "total_cost_usd": True, "days": True, "lat": False, "lon": False}
        if "internet_speed_mbps" in t.columns: hover_data["internet_speed_mbps"] = True
        if color_by_speed and "internet_speed_mbps" in t.columns and t["internet_speed_mbps"].notna().any():
            fig_map = px.scatter_geo(t, lat="lat", lon="lon", hover_name="trip_name", hover_data=hover_data,
                                     projection="natural earth", color="internet_speed_mbps",
                                     color_continuous_scale="RdYlGn",
                                     range_color=[0, max(50, t["internet_speed_mbps"].max(skipna=True))])
            fig_map.update_traces(marker=dict(size=9, line=dict(width=1, color="black")))
            fig_map.update_coloraxes(colorbar_title="Mbps")
        else:
            fig_map = px.scatter_geo(t, lat="lat", lon="lon", hover_name="trip_name", hover_data=hover_data,
                                     projection="natural earth")
            fig_map.update_traces(marker=dict(color="red", size=9, line=dict(width=1, color="black")))
        fig_map.update_geos(showcountries=True, showframe=False, landcolor="lightgray", oceancolor="lightblue", showocean=True)
        fig_map.update_layout(margin=dict(l=0,r=0,t=0,b=0), height=450, template="simple_white")
        _hide_legends(fig_map)
        st.plotly_chart(fig_map, use_container_width=True, config=PLOTLY_CONFIG)
        add_download(fig_map, "map.png", key="dl_map")
        report_sections.append(("Where you've been", fig_map))
    else:
        st.info("No trips yet. Add your first trip in Add / Manage Data → Add Trip.")

with col2:
    st.subheader("💵 Total spend per trip")
    if len(t):
        if sort_by == "Start date": df_total = t.sort_values("start_date")
        elif sort_by == "Trip name": df_total = t.sort_values("trip_name")
        else: df_total = t.sort_values("total_cost_usd", ascending=False)
        fig_cost = px.bar(df_total, x="trip_name", y="total_cost_usd",
                          labels={"trip_name": "Trip", "total_cost_usd": "Amount"},
                          color="total_cost_usd", color_continuous_scale="Tealgrn")
        if show_labels:
            fig_cost.update_traces(text=df_total["total_cost_usd"].map(lambda v: f"${v:,.0f}"), textposition="outside", cliponaxis=False)
        fig_cost.update_traces(hovertemplate="<b>%{x}</b><br>%{y:,.0f}<extra></extra>")
        fig_cost.update_layout(xaxis_tickangle=-20, margin=dict(t=30))
        _hide_legends(fig_cost)
        st.plotly_chart(fig_cost, use_container_width=True, config=PLOTLY_CONFIG)
        add_download(fig_cost, "total_spend.png", key="dl_total")
        report_sections.append(("Total spend per trip", fig_cost))
    else:
        st.info("Add some trips to see spending charts.")

st.markdown("---")

st.subheader("🏆 Cost per day leaderboard")
if len(t):
    df_cpd = t.sort_values("cost_per_day", ascending=True).copy()
    fig_cpd = px.bar(df_cpd, x="cost_per_day", y="trip_name", orientation="h",
                     labels={"cost_per_day": "Per day", "trip_name": "Trip"},
                     color="cost_per_day", color_continuous_scale="Blugrn")
    if show_labels:
        fig_cpd.update_traces(text=df_cpd["cost_per_day"].map(lambda v: f"${v:,.2f}"), textposition="outside", cliponaxis=False)
    fig_cpd.update_traces(hovertemplate="<b>%{y}</b><br>%{x:,.2f}<extra></extra>")
    # Y-axis clipping & title spacing
    fig_cpd.update_layout(
        xaxis_title_standoff=16,
        yaxis_title_standoff=24,
        xaxis_title_font=dict(size=12),
        yaxis_title_font=dict(size=12),
        margin=dict(l=150, r=30, t=35, b=40),
    )
    fig_cpd.update_xaxes(automargin=True)
    fig_cpd.update_yaxes(automargin=True)
    _hide_legends(fig_cpd)
    st.plotly_chart(fig_cpd, use_container_width=True, config=PLOTLY_CONFIG)
    add_download(fig_cpd, "cost_per_day.png", key="dl_cpd")
    report_sections.append(("Cost per day leaderboard", fig_cpd))
else:
    st.info("Add some trips to see the cost-per-day leaderboard.")

st.markdown("---")

# Food Ratings (table + cuisine + avg per trip)
st.subheader("🍴 Food Ratings")
if {"trip_id","cuisine","rating_1_10"}.issubset(meals.columns) and len(meals) and len(t):
    meals_r = meals.copy()
    if "date" in meals_r.columns:
        meals_r["date_str"] = pd.to_datetime(meals_r["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    meals_r = meals_r[meals_r["trip_id"].isin(t["trip_id"])]
    meals_r = meals_r.merge(t[["trip_id", "trip_name"]], how="left", on="trip_id")

    if meals_r.empty:
        st.info("No meals match the current filters.")
    else:
        display_cols = ["trip_name","date_str","cuisine","restaurant","dish_name","rating_1_10","cost_usd"]
        display_cols = [c for c in display_cols if c in meals_r.columns]
        display_names = {"trip_name":"Trip","date_str":"Date","cuisine":"Cuisine","restaurant":"Restaurant","dish_name":"Dish Name","rating_1_10":"Rating","cost_usd":"Cost"}
        table_df = meals_r[display_cols].sort_values(["trip_name","date_str"]).reset_index(drop=True).rename(columns=display_names)
        if "Cost" in table_df.columns:
            table_df["Cost"] = pd.to_numeric(table_df["Cost"], errors="coerce").map(lambda v: f"${v:,.2f}" if pd.notnull(v) else "")
        try:
            st.dataframe(table_df, use_container_width=True, hide_index=True)
        except TypeError:
            st.dataframe(table_df, use_container_width=True)

        top_cuisines = (meals_r.dropna(subset=["cuisine","rating_1_10"])
                        .groupby("cuisine", as_index=False)
                        .agg(avg_rating=("rating_1_10","mean"), count=("rating_1_10","size"))
                        .sort_values(["avg_rating","count"], ascending=[False,False]))
        fig_cuisine = px.bar(top_cuisines, x="cuisine", y="avg_rating", hover_data=["count"],
                             labels={"avg_rating":"Avg Rating"}, color="avg_rating",
                             color_continuous_scale="Viridis", range_y=[0,10])
        if show_labels:
            fig_cuisine.update_traces(text=top_cuisines["avg_rating"].map(lambda v: f"{v:.1f}"), textposition="outside", cliponaxis=False)
        fig_cuisine.update_layout(xaxis_tickangle=-30, margin=dict(t=30))
        _hide_legends(fig_cuisine)
        st.plotly_chart(fig_cuisine, use_container_width=True, config=PLOTLY_CONFIG)
        add_download(fig_cuisine, "food_ratings_cuisines.png", key="dl_cuisine")
        report_sections.append(("Food ratings — avg by cuisine", fig_cuisine))

        avg_by_trip = (meals_r.dropna(subset=["rating_1_10"])
                       .groupby(["trip_id","trip_name"], as_index=False)
                       .agg(avg_rating=("rating_1_10","mean"), count=("rating_1_10","size"))
                       .sort_values(["avg_rating","count"], ascending=[False, False]))
        if len(avg_by_trip):
            st.write("**Average food rating per trip**")
            fig_trip_rating = px.bar(avg_by_trip, x="trip_name", y="avg_rating", hover_data=["count"],
                                     labels={"trip_name":"Trip","avg_rating":"Avg Rating"},
                                     color="avg_rating", color_continuous_scale="Bluered", range_y=[0,10])
            fig_trip_rating.update_traces(
                customdata=avg_by_trip[["count"]].to_numpy(),
                hovertemplate="<b>%{x}</b><br>Avg rating: %{y:.2f}/10<br>Meals counted: %{customdata[0]}<extra></extra>"
            )
            if show_labels:
                fig_trip_rating.update_traces(text=avg_by_trip["avg_rating"].map(lambda v: f"{v:.1f}"), textposition="outside", cliponaxis=False)
            fig_trip_rating.update_layout(xaxis_tickangle=-20, margin=dict(t=30))
            _hide_legends(fig_trip_rating)
            st.plotly_chart(fig_trip_rating, use_container_width=True, config=PLOTLY_CONFIG)
            add_download(fig_trip_rating, "avg_food_rating_per_trip.png", key="dl_trip_rating")
            report_sections.append(("Average food rating per trip", fig_trip_rating))
        else:
            st.info("No meal ratings yet to compute averages per trip.")
else:
    st.info("Add meals (and at least one trip) to see Food Ratings.")

st.markdown("---")

# Cost categories
st.subheader("🚗 Transportation spend per trip")
if "transportation_cost_usd" in t.columns and len(t) and t["transportation_cost_usd"].notna().any():
    df_tr = t.sort_values("start_date")
    fig_transport = px.bar(df_tr, x="trip_name", y="transportation_cost_usd",
                           labels={"trip_name":"Trip","transportation_cost_usd":"Amount"},
                           color="transportation_cost_usd", color_continuous_scale="Tealgrn")
    if show_labels:
        fig_transport.update_traces(text=df_tr["transportation_cost_usd"].fillna(0).map(lambda v: f"${v:,.0f}"), textposition="outside", cliponaxis=False)
    fig_transport.update_traces(hovertemplate="<b>%{x}</b><br>%{y:,.0f}<extra></extra>")
    fig_transport.update_layout(xaxis_tickangle=-20, margin=dict(t=30))
    _hide_legends(fig_transport)
    st.plotly_chart(fig_transport, use_container_width=True, config=PLOTLY_CONFIG)
    add_download(fig_transport, "transportation.png", key="dl_transport")
    report_sections.append(("Transportation spend per trip", fig_transport))
else:
    st.info("Add trips with transportation costs to see this chart.")

st.subheader("🍜 Food spend per trip")
if "food_cost_usd_final" in t.columns and len(t):
    df_food = t.sort_values("start_date")
    fig_food = px.bar(df_food, x="trip_name", y="food_cost_usd_final",
                      labels={"trip_name":"Trip","food_cost_usd_final":"Amount"},
                      color="food_cost_usd_final", color_continuous_scale="Viridis")
    if show_labels:
        fig_food.update_traces(text=df_food["food_cost_usd_final"].map(lambda v: f"${v:,.0f}"), textposition="outside", cliponaxis=False)
    fig_food.update_traces(hovertemplate="<b>%{x}</b><br>%{y:,.0f}<extra></extra>")
    fig_food.update_layout(xaxis_tickangle=-20, margin=dict(t=30))
    _hide_legends(fig_food)
    st.plotly_chart(fig_food, use_container_width=True, config=PLOTLY_CONFIG)
    add_download(fig_food, "food_spend.png", key="dl_food")
    report_sections.append(("Food spend per trip", fig_food))
else:
    st.info("Add meals or a manual trip meal cost to see food totals per trip.")

st.subheader("🏨 Accommodation spend per trip")
if "accommodation_cost_usd" in t.columns and len(t) and t["accommodation_cost_usd"].notna().any():
    df_ac = t.sort_values("start_date")
    fig_accom = px.bar(df_ac, x="trip_name", y="accommodation_cost_usd",
                       labels={"trip_name":"Trip","accommodation_cost_usd":"Amount"},
                       color="accommodation_cost_usd", color_continuous_scale="Purples")
    if show_labels:
        fig_accom.update_traces(text=df_ac["accommodation_cost_usd"].fillna(0).map(lambda v: f"${v:,.0f}"), textposition="outside", cliponaxis=False)
    fig_accom.update_traces(hovertemplate="<b>%{x}</b><br>%{y:,.0f}<extra></extra>")
    fig_accom.update_layout(xaxis_tickangle=-20, margin=dict(t=30))
    _hide_legends(fig_accom)
    st.plotly_chart(fig_accom, use_container_width=True, config=PLOTLY_CONFIG)
    add_download(fig_accom, "accommodation.png", key="dl_accom")
    report_sections.append(("Accommodation spend per trip", fig_accom))
else:
    st.info("Add trips with accommodation costs to see this chart.")

st.subheader("🎟️ Activities spend per trip")
if "activities_cost_usd" in t.columns and len(t) and t["activities_cost_usd"].notna().any():
    df_act = t.sort_values("start_date")
    fig_activities = px.bar(df_act, x="trip_name", y="activities_cost_usd",
                            labels={"trip_name":"Trip","activities_cost_usd":"Amount"},
                            color="activities_cost_usd", color_continuous_scale="Sunset")
    if show_labels:
        fig_activities.update_traces(text=df_act["activities_cost_usd"].fillna(0).map(lambda v: f"${v:,.0f}"), textposition="outside", cliponaxis=False)
    fig_activities.update_traces(hovertemplate="<b>%{x}</b><br>%{y:,.0f}<extra></extra>")
    fig_activities.update_layout(xaxis_tickangle=-20, margin=dict(t=30))
    _hide_legends(fig_activities)
    st.plotly_chart(fig_activities, use_container_width=True, config=PLOTLY_CONFIG)
    add_download(fig_activities, "activities_spend.png", key="dl_activities")
    report_sections.append(("Activities spend per trip", fig_activities))
else:
    st.info("Add trips with activities costs to see this chart.")

st.markdown("---")

# =========================
#   Digital Nomad Insights
# =========================
st.subheader("💻 Digital Nomad Insights")
st.caption("Add Mbps for each trip below (optional). As a rough guide: 15–25 Mbps = decent calls, 50+ Mbps = great.")

if len(t):
    with st.form("form_set_speed"):
        colx, coly = st.columns([2, 1])
        with colx:
            trip_choices = t.sort_values("start_date")[["trip_id","trip_name"]].copy()
            trip_choices["label"] = trip_choices["trip_name"] + " (" + trip_choices["trip_id"].astype(str) + ")"
            sel_label = st.selectbox("Select trip to set internet speed", trip_choices["label"].tolist())
        with coly:
            new_speed = st.number_input("Average Internet Speed (Mbps)", min_value=0.0, step=1.0, value=0.0)
        do_set = st.form_submit_button("Save speed")
    if do_set:
        try:
            row = trip_choices.iloc[[trip_choices["label"].tolist().index(sel_label)]].iloc[0]
            tid = int(row["trip_id"])
            idx = st.session_state.trips_df.index[st.session_state.trips_df["trip_id"] == tid]
            if len(idx):
                st.session_state.trips_df.loc[idx, "internet_speed_mbps"] = float(new_speed)
                st.success(f'Saved {new_speed:.1f} Mbps for trip "{row["trip_name"]}".')
            else:
                st.warning("Could not locate that trip in the current table.")
        except Exception:
            st.error("Failed to save speed. Please try again.")

t = st.session_state.trips_df.copy()
if len(t):
    t["start_date"] = pd.to_datetime(t["start_date"], errors="coerce")
    t["end_date"] = pd.to_datetime(t["end_date"], errors="coerce")

if len(t) and "internet_speed_mbps" in t.columns and t["internet_speed_mbps"].notna().any():
    spd_all = t["internet_speed_mbps"].dropna()
    colA, colB, colC, colD = st.columns(4)
    with colA: st.metric("Avg Speed", f"{spd_all.mean():.1f} Mbps")
    with colB: st.metric("Fastest Trip", f"{spd_all.max():.1f} Mbps")
    with colC: st.metric("Slowest Trip", f"{spd_all.min():.1f} Mbps")
    with colD: st.metric("Trips ≥50 Mbps", f"{(spd_all >= 50).sum()}")

    st.write("**Average Internet Speed by Trip**")
    df_net = t.dropna(subset=["internet_speed_mbps"]).sort_values("internet_speed_mbps", ascending=False)
    fig_net = px.bar(df_net, x="internet_speed_mbps", y="trip_name", orientation="h",
                     labels={"internet_speed_mbps":"Mbps","trip_name":"Trip"},
                     color="internet_speed_mbps", color_continuous_scale="RdYlGn")
    fig_net.update_traces(hovertemplate="<b>%{y}</b><br>%{x:.1f} Mbps<extra></extra>")
    # Y-axis clipping & title spacing
    fig_net.update_layout(
        xaxis_title_standoff=16,
        yaxis_title_standoff=24,
        xaxis_title_font=dict(size=12),
        yaxis_title_font=dict(size=12),
        margin=dict(l=150, r=30, t=35, b=40),
    )
    fig_net.update_xaxes(automargin=True)
    fig_net.update_yaxes(automargin=True)
    fig_net.update_traces(cliponaxis=False)
    _hide_legends(fig_net)
    st.plotly_chart(fig_net, use_container_width=True, config=PLOTLY_CONFIG)
    add_download(fig_net, "internet_speed.png", key="dl_net_dn")
    report_sections.append(("Average Internet Speed by Trip", fig_net))

    st.write("**Average internet speed by country**")
    country_speed = (t.dropna(subset=["country","internet_speed_mbps"])
                       .groupby("country", as_index=False)["internet_speed_mbps"].mean()
                       .rename(columns={"internet_speed_mbps":"avg_speed_mbps"})
                       .sort_values("avg_speed_mbps", ascending=False))
    if len(country_speed):
        fig_country = px.bar(country_speed, x="country", y="avg_speed_mbps",
                             labels={"country":"Country","avg_speed_mbps":"Avg Mbps"},
                             color="avg_speed_mbps", color_continuous_scale="RdYlGn")
        fig_country.update_layout(margin=dict(t=30))
        _hide_legends(fig_country)
        st.plotly_chart(fig_country, use_container_width=True, config=PLOTLY_CONFIG)
        add_download(fig_country, "country_avg_speed.png", key="dl_country_speed")
        report_sections.append(("Average internet speed by country", fig_country))

    st.markdown("**Workability Score**  \nA simple indicator that blends internet speed (faster is better) and affordability (lower cost/day is better) into one score.")
    st.caption("We normalize each trip’s internet speed and affordability (1 / cost per day), then combine them.  \nScore = 100 × (0.6 × speed_norm + 0.4 × affordability_norm).")

    st.write("**Top 5 remote-work destinations (workability score)**")
    score_df = t.dropna(subset=["internet_speed_mbps", "cost_per_day"]).copy()
    if len(score_df) >= 1:
        sp_min, sp_max = score_df["internet_speed_mbps"].min(), score_df["internet_speed_mbps"].max()
        score_df["speed_norm"] = (score_df["internet_speed_mbps"] - sp_min) / (sp_max - sp_min) if sp_max > sp_min else 1.0
        score_df["inv_cost"] = 1.0 / score_df["cost_per_day"].replace(0, pd.NA)
        score_df["inv_cost"] = score_df["inv_cost"].fillna(score_df["inv_cost"].max() if score_df["inv_cost"].notna().any() else 1.0)
        cmin, cmax = score_df["inv_cost"].min(), score_df["inv_cost"].max()
        score_df["afford_norm"] = (score_df["inv_cost"] - cmin) / (cmax - cmin) if cmax > cmin else 1.0
        score_df["workability_score"] = 100 * (0.6 * score_df["speed_norm"] + 0.4 * score_df["afford_norm"])
        top5 = score_df.sort_values("workability_score", ascending=False).head(5)
        fig_work = px.bar(top5, x="workability_score", y="trip_name", orientation="h",
                          labels={"workability_score":"Score","trip_name":"Trip"},
                          color="workability_score", color_continuous_scale="RdYlGn")
        # Y-axis clipping & title spacing
        fig_work.update_layout(
            xaxis_title_standoff=16,
            yaxis_title_standoff=24,
            xaxis_title_font=dict(size=12),
            yaxis_title_font=dict(size=12),
            margin=dict(l=150, r=30, t=35, b=40),
        )
        fig_work.update_xaxes(automargin=True)
        fig_work.update_yaxes(automargin=True)
        fig_work.update_traces(cliponaxis=False)
        _hide_legends(fig_work)
        st.plotly_chart(fig_work, use_container_width=True, config=PLOTLY_CONFIG)
        add_download(fig_work, "top_remote_work_destinations.png", key="dl_workability")
        report_sections.append(("Top 5 remote-work destinations (workability score)", fig_work))
else:
    st.info("Add trips (and optionally internet speeds) to see Digital Nomad Insights.")

st.markdown("---")

# =========================
#   Narrative builders
# =========================
def make_single_trip_summary(trip_row: pd.Series, meals_df: pd.DataFrame, norm_basis: pd.DataFrame) -> str:
    name = str(trip_row.get("trip_name", "") or "").strip() or "Unnamed Trip"
    city = str(trip_row.get("primary_city", "") or "").strip()
    country = str(trip_row.get("country", "") or "").strip()
    sd = pd.to_datetime(trip_row.get("start_date"), errors="coerce")
    ed = pd.to_datetime(trip_row.get("end_date"), errors="coerce")
    days = int(trip_row.get("days") or ((ed - sd).days if pd.notnull(sd) and pd.notnull(ed) else 1) or 1)

    total = trip_row.get("total_cost_usd", 0) or 0
    cpd = trip_row.get("cost_per_day", 0) or 0
    tr = trip_row.get("transportation_cost_usd", 0) or 0
    ac = trip_row.get("accommodation_cost_usd", 0) or 0
    fo = trip_row.get("food_cost_usd_final", 0) or 0
    act = trip_row.get("activities_cost_usd", 0) or 0

    spd = trip_row.get("internet_speed_mbps")
    spd_txt = f"{float(spd):.0f} Mbps" if pd.notnull(spd) else "not recorded"

    date_str = ""
    if pd.notnull(sd) and pd.notnull(ed):
        if sd.year == ed.year and sd.month == ed.month:
            date_str = f"in {sd.strftime('%B %Y')}"
        else:
            date_str = f"from {sd.strftime('%b %d, %Y')} to {ed.strftime('%b %d, %Y')}"
    parts = []
    parts.append(f"On “{name}” — {city}, {country} — you traveled {date_str or 'recently'} for {days} day{'s' if days!=1 else ''}. ")
    parts.append(f"You spent {fmt_money(total)} total (≈ ${cpd:,.2f}/day) across transportation ({fmt_money(tr)}), accommodation ({fmt_money(ac)}), food ({fmt_money(fo)}), and activities ({fmt_money(act)}). ")
    parts.append(f"Internet averaged {spd_txt}, keeping you connected between moments worth keeping. ")
    return "".join(parts)

def make_multi_trip_snapshots(trips_df: pd.DataFrame, meals_df: pd.DataFrame) -> str:
    lines = []
    for _, r in trips_df.sort_values("start_date").iterrows():
        name = str(r.get("trip_name", "") or "").strip() or "Unnamed Trip"
        city = str(r.get("primary_city", "") or "").strip()
        country = str(r.get("country", "") or "").strip()
        days = int(r.get("days") or 1)
        total = r.get("total_cost_usd", 0) or 0
        cpd = r.get("cost_per_day", 0) or 0
        spd = r.get("internet_speed_mbps")
        spd_txt = f"{float(spd):.0f} Mbps" if pd.notnull(spd) else "—"
        lines.append(
            f"&bull; <b>{name}</b> — {city}, {country} ({days} days): {fmt_money(total)} total, ${cpd:,.0f}/day; internet {spd_txt}."
        )
    return "<br/>".join(lines) if lines else "Add trips to see snapshots."

# =========================
#   PDF Export (mini donut on page 1)
# =========================
def build_pdf_report(fig_sections, cover, summary_pages=None, mini_chart_png=None):
    if not (KALEIDO_OK and REPORTLAB_OK):
        return None

    buf = BytesIO()

    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.utils import ImageReader
    from reportlab.lib.colors import HexColor
    from reportlab.platypus import Paragraph, Frame
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_LEFT

    c = rl_canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    margin = 24
    navy = HexColor("#0F2557")
    light_navy = HexColor("#142F66")
    body_style = ParagraphStyle("Body", fontName="Helvetica", fontSize=10.5, leading=14,
                                alignment=TA_LEFT, textColor=HexColor("#111111"))

    # Header banner
    banner_h = 96
    c.setFillColor(navy); c.rect(0, height - banner_h, width, banner_h, fill=1, stroke=0)
    c.setFillColor(HexColor("#FFFFFF")); c.setFont("Helvetica-Bold", 22)
    c.drawString(margin, height - banner_h + 58, cover.get("title", "Travel Dashboard Report"))
    c.setFont("Helvetica", 11)
    subline = cover.get("subtitle", ""); dr = cover.get("daterange", "")
    if subline: c.drawString(margin, height - banner_h + 38, subline)
    if dr: c.drawString(margin, height - banner_h + 22, dr)

    # KPI chips
    chips = cover.get("metrics", {})
    chip_w = (width - 2*margin - 16) / 3.0
    chip_h = 38
    rows_y = [height - banner_h - 16 - chip_h, height - banner_h - 16 - 2*(chip_h + 8)]
    labels = list(chips.keys()); values = [chips[k] for k in labels]
    def _chip(x, y, w, h, label, value):
        c.setFillColor(light_navy); c.roundRect(x, y, w, h, 7, fill=1, stroke=0)
        c.setFillColor(HexColor("#DDE4F2")); c.setFont("Helvetica", 8); c.drawString(x+8, y+h-12, label)
        c.setFillColor(HexColor("#FFFFFF")); c.setFont("Helvetica-Bold", 14); c.drawString(x+8, y+h-28, str(value))
    for i, (lab, val) in enumerate(zip(labels, values)):
        r = 0 if i < 3 else 1; col = i % 3
        x = margin + col * (chip_w + 8); y = rows_y[r]; _chip(x, y, chip_w, chip_h, lab, val)

    # Overview box
    box_y = rows_y[1] - 92 if len(labels) > 3 else rows_y[0] - 92
    c.setFillColor(light_navy); c.roundRect(margin, box_y, width - 2*margin, 84, 8, fill=1, stroke=0)
    c.setFillColor(HexColor("#FFFFFF")); c.setFont("Helvetica-Bold", 12)
    c.drawString(margin + 10, box_y + 62, "Overview")
    c.setFont("Helvetica", 9)
    y = box_y + 46
    for line in cover.get("overview_lines", [])[:5]:
        c.drawString(margin + 10, y, "• " + line); y -= 14

    # Executive Summary + first summary on same page
    exec_text = cover.get("exec_summary", "").strip()
    c.setFillColor(navy); c.setFont("Helvetica-Bold", 12)
    y_title_exec = box_y - 14
    c.drawString(margin, y_title_exec, "Executive Summary")

    top_of_text = y_title_exec - 12
    remaining_h = top_of_text - margin
    exec_h = remaining_h * 0.60
    summ_h = remaining_h - exec_h - 6

    exec_frame = Frame(margin, margin + summ_h + 6, width - 2*margin, exec_h, showBoundary=0)
    if exec_text:
        exec_para = Paragraph(exec_text, style=body_style)
        exec_frame.addFromList([exec_para], c)

    if mini_chart_png:
        img = ImageReader(BytesIO(mini_chart_png))
        target_w, target_h = 170, 170
        x = margin + (width - 2*margin - target_w) / 2.0
        y = margin + summ_h + 14
        c.setFillColor(navy); c.setFont("Helvetica-Bold", 10)
        c.drawCentredString(margin + (width - 2*margin)/2.0, y + target_h + 12, "Trips by Region")
        c.drawImage(img, x, y, width=target_w, height=target_h, preserveAspectRatio=True, mask='auto')

    if summary_pages and len(summary_pages) >= 1:
        first_summary = summary_pages[0]
        c.setFillColor(navy); c.setFont("Helvetica-Bold", 12)
        c.drawString(margin, margin + summ_h + 6 - 16, first_summary.get("title", "Summary"))
        summary_frame = Frame(margin, margin, width - 2*margin, summ_h - 20, showBoundary=0)
        summary_para = Paragraph(first_summary.get("paragraph", ""), style=body_style)
        summary_frame.addFromList([summary_para], c)

    c.showPage()

    # Additional summaries
    if summary_pages and len(summary_pages) > 1:
        for sec in summary_pages[1:]:
            c.setFillColor(navy); c.setFont("Helvetica-Bold", 13)
            c.drawString(margin, height - margin - 10, sec.get("title", "Summary"))
            frame = Frame(margin, margin, width - 2*margin, height - 2*margin - 22, showBoundary=0)
            frame.addFromList([Paragraph(sec.get("paragraph",""), style=body_style)], c)
            c.showPage()

    # Chart pages: 2 per page
    title_h = 12
    gap_y = 10
    usable_h = height - 2*margin
    slot_h = (usable_h - gap_y) / 2.0
    max_w = width - 2*margin

    def draw_chart_block(title, fig, y_top):
        c.setFillColor(navy); c.setFont("Helvetica-Bold", 11)
        c.drawString(margin, y_top - title_h, title)
        png = fig_png_bytes(fig, scale=2)
        if not png: return
        img = ImageReader(BytesIO(png))
        iw, ih = img.getSize()
        available_h = slot_h - (title_h + 6)
        scale = min(max_w / iw, available_h / ih)
        draw_w, draw_h = iw * scale, ih * scale
        c.drawImage(img, margin, y_top - title_h - 6 - draw_h, width=draw_w, height=draw_h,
                    preserveAspectRatio=True, mask='auto')

    i = 0
    while i < len(fig_sections):
        y_top_first = height - margin
        title1, fig1 = fig_sections[i]
        draw_chart_block(title1, fig1, y_top_first)

        if i + 1 < len(fig_sections):
            y_top_second = height - margin - slot_h - gap_y
            title2, fig2 = fig_sections[i + 1]
            draw_chart_block(title2, fig2, y_top_second)
            i += 2
        else:
            i += 1
        c.showPage()

    c.save(); buf.seek(0); return buf.getvalue()

# =========================
#   PDF Export
# =========================
st.subheader("📄 Export")
summary_pages = []
if len(t) == 1:
    summary_text = make_single_trip_summary(t.iloc[0], meals, t)
    summary_pages.append({"title": "Trip Summary", "paragraph": summary_text})
elif len(t) > 1:
    snapshots_text = make_multi_trip_snapshots(t, meals)
    summary_pages.append({"title": "Trip Snapshots", "paragraph": snapshots_text})

# Mini donut for page 1 (clean look)
mini_chart_png = None
try:
    rc = region_counts_df(t)
    if len(rc):
        palette = ["#b9935a", "#d9c2a3", "#8c6e48", "#c7aa79", "#a67c52", "#e0ceb0", "#70543a", "#c9ab85"]
        fig_region = px.pie(rc, names="region", values="count", hole=0.55,
                            template="simple_white", color_discrete_sequence=palette)
        fig_region.update_traces(
            textinfo="percent",
            insidetextorientation="radial",
            hovertemplate="%{label}: %{value} trip(s) — %{percent}<extra></extra>",
            pull=0.01,
        )
        fig_region.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=260, width=260, showlegend=False)
        mini_chart_png = fig_png_bytes(fig_region, scale=2)
except Exception:
    mini_chart_png = None

if not KALEIDO_OK:
    st.info("To enable PNG/PDF exports, ensure `kaleido` is installed in requirements.txt.")
elif not REPORTLAB_OK:
    st.info("To enable PDF export with styled summaries, add `reportlab>=3.6.12` to requirements.txt.")
elif len(report_sections) == 0:
    st.info("Add some data to generate charts before exporting a PDF report.")
else:
    pdf_bytes = build_pdf_report(report_sections, cover_info, summary_pages=summary_pages, mini_chart_png=mini_chart_png)
    if pdf_bytes:
        st.download_button(
            "📄 Download PDF Report",
            data=pdf_bytes,
            file_name=f"travel_dashboard_report_{datetime.now().strftime('%Y%m%d')}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
    else:
        st.warning("Could not build PDF report. Check `kaleido` and `reportlab` are installed and try again.")

# =========================
#   Footer
# =========================
st.markdown("---")
st.markdown("🌍 Thanks for exploring the Travel Dashboard!  \n_All amounts are in USD._")