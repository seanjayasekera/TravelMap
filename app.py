import streamlit as st
import pandas as pd
import plotly.express as px
from io import StringIO
from pathlib import Path
import numpy as np

# =========================
#   PAGE / THEME SETTINGS
# =========================
st.set_page_config(page_title="Travel Dashboard", page_icon="🌍", layout="wide")
st.title("🌍 Travel Dashboard")
st.caption("Add trips and meals directly in the app • Explore maps & costs • Share your dashboard")

# -------------------------
#   KALEIDO DETECTION & CONFIG
# -------------------------
try:
    import kaleido  # noqa: F401
    KALEIDO_OK = True
except Exception:
    KALEIDO_OK = False

PLOTLY_CONFIG = {
    "displaylogo": False,
    "modeBarButtonsToAdd": ["toImage"] if not KALEIDO_OK else [],
}

# -------------------------
#   HELPERS
# -------------------------
def read_csv_with_fallback(uploaded, default_path, **read_kwargs):
    if uploaded is not None:
        return pd.read_csv(uploaded, **read_kwargs)
    else:
        return pd.read_csv(default_path, **read_kwargs)

def year_series(dts):
    try:
        return dts.dt.year
    except Exception:
        return pd.to_datetime(dts, errors="coerce").dt.year

def apply_common_layout(fig, height=420):
    fig.update_layout(
        template="simple_white",
        height=height,
        margin=dict(t=30, r=10, l=10, b=10),
        coloraxis_showscale=False,
    )
    return fig

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

def to_csv_download_bytes(df: pd.DataFrame) -> bytes:
    buf = StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")

def next_int(series):
    """Return next positive integer not in series; handles empty/NaN."""
    s = pd.to_numeric(series, errors="coerce").dropna().astype(int)
    return (s.max() + 1) if len(s) else 1

# -------------------------
#   LOAD DATA
# -------------------------
data_dir = Path(__file__).parent / "data"

st.sidebar.header("Upload your CSVs (optional for you)")
up_trips = st.sidebar.file_uploader("trips.csv", type=["csv"])
up_meals = st.sidebar.file_uploader("meals.csv", type=["csv"])

trips = read_csv_with_fallback(up_trips, data_dir / "trips.csv", parse_dates=["start_date", "end_date"])
meals = read_csv_with_fallback(up_meals, data_dir / "meals.csv", parse_dates=["date"])

# Initialize session state copies (authoritative for this session)
if "trips_df" not in st.session_state:
    st.session_state.trips_df = trips.copy()
if "meals_df" not in st.session_state:
    st.session_state.meals_df = meals.copy()

trips = st.session_state.trips_df
meals = st.session_state.meals_df

# -------------------------
#   LIGHTWEIGHT SIDEBAR DIAGNOSTICS
# -------------------------
with st.sidebar.expander("Data check", expanded=False):
    st.write("**meals.csv columns:**")
    st.code(", ".join(map(str, meals.columns)))
    st.write("Contains `dish_name`? →", "✅ yes" if "dish_name" in meals.columns else "❌ no")
    st.write("Contains `rating_1_10`? →", "✅ yes" if "rating_1_10" in meals.columns else "❌ no")

# -------------------------
#   BASIC SCHEMA CHECKS
# -------------------------
required_trip_cols = {
    "trip_id","trip_name","start_date","end_date",
    "primary_city","country","lat","lon","total_cost_usd"
}
missing = required_trip_cols - set(trips.columns)
if missing:
    st.error(f"Missing columns in trips.csv: {missing}")
    st.stop()

# -------------------------
#   DERIVED COLUMNS
# -------------------------
# Coerce numeric columns safely
for col in ["lat", "lon", "total_cost_usd", "transportation_cost_usd", "accommodation_cost_usd"]:
    if col in trips.columns:
        trips[col] = pd.to_numeric(trips[col], errors="coerce")

trips["days"] = (pd.to_datetime(trips["end_date"], errors="coerce") - pd.to_datetime(trips["start_date"], errors="coerce")).dt.days.clip(lower=1)
trips["cost_per_day"] = (pd.to_numeric(trips["total_cost_usd"], errors="coerce").fillna(0) / trips["days"]).round(2)

# Compute food per trip from meals
if {"trip_id", "cost_usd"}.issubset(meals.columns):
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

# -------------------------
#   ➕ ADD / MANAGE DATA (no CSV knowledge needed)
# -------------------------
st.markdown("## ➕ Add / Manage Data")
tab_add_trip, tab_add_meal, tab_edit = st.tabs(["Add Trip", "Add Meal", "Edit Tables"])

with tab_add_trip:
    st.write("Add a new trip. Fields with * are required.")
    with st.form("form_add_trip", clear_on_submit=True):
        colA, colB = st.columns(2)
        with colA:
            trip_name = st.text_input("Trip name *", placeholder="Tokyo Spring Break")
            primary_city = st.text_input("Primary city *", placeholder="Tokyo")
            country = st.text_input("Country *", placeholder="Japan")
            start_date = st.date_input("Start date *")
            total_cost_usd = st.number_input("Total cost (USD) *", min_value=0.0, step=10.0)
            transportation_cost_usd = st.number_input("Transportation cost (USD)", min_value=0.0, step=5.0, value=0.0)
        with colB:
            end_date = st.date_input("End date *")
            lat = st.number_input("Latitude *", min_value=-90.0, max_value=90.0, step=0.0001, format="%.6f")
            lon = st.number_input("Longitude *", min_value=-180.0, max_value=180.0, step=0.0001, format="%.6f")
            accommodation_cost_usd = st.number_input("Accommodation cost (USD)", min_value=0.0, step=5.0, value=0.0)
            notes = st.text_input("Notes (optional)", placeholder="Cherry blossom season!")
        submitted = st.form_submit_button("Add trip")
    if submitted:
        # Basic validation
        if not trip_name or not primary_city or not country or start_date is None or end_date is None:
            st.error("Please fill all required fields (marked with *).")
        elif pd.to_datetime(end_date) < pd.to_datetime(start_date):
            st.error("End date cannot be before start date.")
        else:
            new_id = next_int(trips["trip_id"]) if "trip_id" in trips.columns else 1
            new_row = {
                "trip_id": new_id,
                "trip_name": trip_name,
                "start_date": pd.to_datetime(start_date),
                "end_date": pd.to_datetime(end_date),
                "primary_city": primary_city,
                "country": country,
                "lat": float(lat),
                "lon": float(lon),
                "total_cost_usd": float(total_cost_usd),
                "transportation_cost_usd": float(transportation_cost_usd),
                "accommodation_cost_usd": float(accommodation_cost_usd),
                "notes": notes,
            }
            st.session_state.trips_df = pd.concat([trips, pd.DataFrame([new_row])], ignore_index=True)
            st.success(f"Trip “{trip_name}” added!")

with tab_add_meal:
    st.write("Add a meal for one of the trips in view.")
    if trips.empty:
        st.info("Add a trip first.")
    else:
        with st.form("form_add_meal", clear_on_submit=True):
            colA, colB, colC = st.columns(3)
            with colA:
                # Friendly chooser shows "Trip Name (ID)"
                trip_options = trips.sort_values("start_date")[["trip_id", "trip_name"]].copy()
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
                notes_meal = st.text_input("Notes (optional)", placeholder="Late-night bowl after Shibuya.")
            submitted_meal = st.form_submit_button("Add meal")
        if submitted_meal:
            if not cuisine or date is None or cost_usd is None:
                st.error("Please complete all required fields.")
            else:
                # Parse selected trip_id back out
                # label is "Trip Name (ID)"
                try:
                    sel = trip_options.iloc[[trip_options["label"].tolist().index(trip_choice)]].iloc[0]
                    use_trip_id = int(sel["trip_id"])
                except Exception:
                    st.error("Could not read the selected trip. Please try again.")
                    use_trip_id = None
                if use_trip_id is not None:
                    new_meal_id = next_int(meals["meal_id"]) if "meal_id" in meals.columns else 1
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
                    st.session_state.meals_df = pd.concat([meals, pd.DataFrame([new_row])], ignore_index=True)
                    st.success(f"Meal “{dish_name or cuisine}” added to trip ID {use_trip_id}!")

with tab_edit:
    st.write("You can make quick edits below (affects this session only).")
    st.caption("Tip: use the Download buttons to save updated CSVs and commit them to your repo.")
    e1, e2 = st.columns(2)
    with e1:
        st.write("**Trips (editable)**")
        st.session_state.trips_df = st.data_editor(
            st.session_state.trips_df, use_container_width=True, num_rows="dynamic", key="edit_trips"
        )
        st.download_button(
            "⬇️ Download updated trips.csv",
            data=to_csv_download_bytes(st.session_state.trips_df),
            file_name="trips.csv",
            mime="text/csv",
            key="dl_trips_csv",
        )
    with e2:
        st.write("**Meals (editable)**")
        # Ensure date shows as date-only in editor
        meals_show = st.session_state.meals_df.copy()
        if "date" in meals_show.columns:
            meals_show["date"] = pd.to_datetime(meals_show["date"], errors="coerce").dt.date
        st.session_state.meals_df = st.data_editor(
            meals_show, use_container_width=True, num_rows="dynamic", key="edit_meals"
        )
        # Convert back to datetime for downstream calcs
        if "date" in st.session_state.meals_df.columns:
            st.session_state.meals_df["date"] = pd.to_datetime(st.session_state.meals_df["date"], errors="coerce")
        st.download_button(
            "⬇️ Download updated meals.csv",
            data=to_csv_download_bytes(st.session_state.meals_df),
            file_name="meals.csv",
            mime="text/csv",
            key="dl_meals_csv",
        )

# Refresh local working copies after edits/additions
trips = st.session_state.trips_df.copy()
meals = st.session_state.meals_df.copy()

# Recompute derived columns with updated data
for col in ["lat", "lon", "total_cost_usd", "transportation_cost_usd", "accommodation_cost_usd"]:
    if col in trips.columns:
        trips[col] = pd.to_numeric(trips[col], errors="coerce")

trips["days"] = (pd.to_datetime(trips["end_date"], errors="coerce") - pd.to_datetime(trips["start_date"], errors="coerce")).dt.days.clip(lower=1)
trips["cost_per_day"] = (pd.to_numeric(trips["total_cost_usd"], errors="coerce").fillna(0) / trips["days"]).round(2)

if {"trip_id", "cost_usd"}.issubset(meals.columns):
    meals["cost_usd"] = pd.to_numeric(meals["cost_usd"], errors="coerce").fillna(0)
    meals["trip_id"] = pd.to_numeric(meals["trip_id"], errors="coerce").astype("Int64")
    food_by_trip = meals.groupby("trip_id", dropna=False)["cost_usd"].sum().rename("food_cost_usd")
    trips = trips.drop(columns=[c for c in trips.columns if c.startswith("food_cost_usd")], errors="ignore")
    trips = trips.merge(food_by_trip, how="left", left_on="trip_id", right_index=True)
trips["food_cost_usd"] = pd.to_numeric(trips["food_cost_usd"], errors="coerce").fillna(0).clip(lower=0)
trips["year"] = year_series(pd.to_datetime(trips["start_date"], errors="coerce"))

# -------------------------
#   FILTERS
# -------------------------
st.markdown("---")
st.sidebar.header("Filters")
countries = sorted(trips["country"].dropna().unique().tolist())
years = sorted(trips["year"].dropna().unique().tolist())

sel_countries = st.sidebar.multiselect("Country", countries, default=countries)
sel_years = st.sidebar.multiselect("Year", years, default=years)
search = st.sidebar.text_input("Search trips/cities", placeholder="e.g., Tokyo")
show_labels = st.sidebar.checkbox("Show values on bars", value=True)
sort_by = st.sidebar.selectbox("Sort bars by", ["Start date", "Trip name", "Value"], index=0)

mask = trips["country"].isin(sel_countries) & trips["year"].isin(sel_years)
t = trips.loc[mask].copy()

if search:
    s = search.strip().lower()
    cols = ["trip_name", "primary_city"] + (["notes"] if "notes" in t.columns else [])
    search_mask = False
    for c in cols:
        search_mask = search_mask | t[c].astype(str).str.lower().str.contains(s, na=False)
    t = t.loc[search_mask].copy()

if t.empty:
    st.info("No trips match the current filters/search.")
    st.stop()

def sort_frame(df, value_col=None):
    if sort_by == "Start date":
        return df.sort_values("start_date")
    if sort_by == "Trip name":
        return df.sort_values("trip_name")
    if sort_by == "Value" and value_col is not None:
        return df.sort_values(value_col, ascending=False)
    return df

# -------------------------
#   METRICS
# -------------------------
c1, c2, c3, c4 = st.columns(4)
with c1: st.metric("Trips", f"{len(t)}")
with c2: st.metric("Countries", f"{t['country'].nunique()}")
with c3: st.metric("Total Spend (USD)", f"${int(pd.to_numeric(t['total_cost_usd'], errors='coerce').fillna(0).sum()):,}")
with c4: st.metric("Median Cost/Day", f"${t['cost_per_day'].median():,.2f}")

st.markdown("---")

# -------------------------
#   MAP + TOTAL SPEND
# -------------------------
col1, col2 = st.columns([1.25, 1])
with col1:
    st.subheader("🗺️ Where you've been")
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

with col2:
    st.subheader("💵 Total spend per trip")
    df_total = sort_frame(t, "total_cost_usd")
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

st.markdown("---")

# -------------------------
#   COST PER DAY
# -------------------------
st.subheader("🏆 Cost per day leaderboard")
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
median_cpd = float(df_cpd["cost_per_day"].median()) if len(df_cpd) else 0
fig_cpd.add_vline(x=median_cpd, line_dash="dash", line_width=2)
fig_cpd.add_annotation(x=median_cpd, y=-0.5, text=f"Median: ${median_cpd:,.2f}", showarrow=False, yshift=-20)
apply_common_layout(fig_cpd, height=520)
st.plotly_chart(fig_cpd, use_container_width=True, config=PLOTLY_CONFIG)
add_download(fig_cpd, "cost_per_day.png", key="dl_cpd")

st.markdown("---")

# -------------------------
#   FOOD RATINGS
# -------------------------
st.subheader("🍴 Food Ratings")
if {"trip_id","cuisine","rating_1_10"}.issubset(meals.columns):
    meals_r = meals.copy()
    meals_r["rating_1_10"] = pd.to_numeric(meals_r["rating_1_10"], errors="coerce")
    if "date" in meals_r.columns:
        meals_r["date_str"] = pd.to_datetime(meals_r["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    meals_r = meals_r[meals_r["trip_id"].isin(t["trip_id"])]
    # Bring in trip_name for display
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
    st.info("Your meals.csv needs columns: 'trip_id','cuisine','rating_1_10'.")

st.markdown("---")

# -------------------------
#   TRANSPORT / FOOD / ACCOM
# -------------------------
st.subheader("🚗 Transportation spend per trip")
if "transportation_cost_usd" in t.columns:
    df_tr = sort_frame(t,"transportation_cost_usd")
    fig_transport = px.bar(
        df_tr, x="trip_name", y="transportation_cost_usd",
        labels={"trip_name":"Trip","transportation_cost_usd":"USD"},
        color="transportation_cost_usd", color_continuous_scale="Tealgrn",
    )
    if show_labels:
        fig_transport.update_traces(text=df_tr["transportation_cost_usd"].map(lambda v: f"${int(v):,}"),
                                    textposition="outside", cliponaxis=False)
    fig_transport.update_traces(hovertemplate="<b>%{x}</b><br>USD: %{y:,}<extra></extra>")
    fig_transport.update_layout(xaxis_tickangle=-20)
    apply_common_layout(fig_transport)
    st.plotly_chart(fig_transport, use_container_width=True, config=PLOTLY_CONFIG)
    add_download(fig_transport,"transportation.png",key="dl_transport")

st.subheader("🍜 Food spend per trip")
if {"trip_id","cost_usd"}.issubset(meals.columns):
    meals_f = meals.copy()
    meals_f["cost_usd"] = pd.to_numeric(meals_f["cost_usd"], errors="coerce").fillna(0)
    meals_f["trip_id"] = pd.to_numeric(meals_f["trip_id"], errors="coerce").astype("Int64")
    food_by_trip_f = meals_f.groupby("trip_id", dropna=False)["cost_usd"].sum().rename("food_cost_usd")

    tf = t.drop(columns=[c for c in t.columns if c.startswith("food_cost_usd")], errors="ignore")
    tf = tf.merge(food_by_trip_f, how="left", left_on="trip_id", right_index=True)
    tf["food_cost_usd"] = pd.to_numeric(tf["food_cost_usd"], errors="coerce").fillna(0)

    df_food = sort_frame(tf,"food_cost_usd")
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

st.subheader("🏨 Accommodation spend per trip")
if "accommodation_cost_usd" in t.columns:
    df_ac = sort_frame(t,"accommodation_cost_usd")
    fig_accom = px.bar(
        df_ac, x="trip_name", y="accommodation_cost_usd",
        labels={"trip_name":"Trip","accommodation_cost_usd":"USD"},
        color="accommodation_cost_usd", color_continuous_scale="Purples",
    )
    if show_labels:
        fig_accom.update_traces(text=df_ac["accommodation_cost_usd"].map(lambda v: f"${int(v):,}"),
                                textposition="outside", cliponaxis=False)
    fig_accom.update_traces(hovertemplate="<b>%{x}</b><br>USD: %{y:,}<extra></extra>")
    fig_accom.update_layout(xaxis_tickangle=-20)
    apply_common_layout(fig_accom)
    st.plotly_chart(fig_accom, use_container_width=True, config=PLOTLY_CONFIG)
    add_download(fig_accom,"accommodation.png",key="dl_accom")

st.caption("To persist new entries for everyone, download the updated CSVs above and commit them to your repo. We can also wire a real backend (Google Sheets / Supabase) later for automatic saving.")