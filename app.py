import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path

# =========================
#   PAGE / THEME SETTINGS
# =========================
st.set_page_config(page_title="Travel Dashboard", page_icon="🌍", layout="wide")
st.title("🌍 Travel Dashboard")
st.caption("Trips, spend, cuisines — separate Transportation, Food, and Accommodation charts with filters, search, ratings, and PNG export")

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
    """Return PNG bytes if kaleido is available; otherwise None."""
    try:
        return fig.to_image(format="png", scale=scale)
    except Exception:
        return None

def add_download(fig, filename, key):
    png = fig_png_bytes(fig)
    if png:
        st.download_button("⬇️ Download PNG", data=png, file_name=filename, mime="image/png", key=key)
    else:
        st.caption("ℹ️ To enable PNG downloads, add `kaleido` to requirements and rerun.")

# -------------------------
#   LOAD DATA
# -------------------------
data_dir = Path(__file__).parent / "data"

st.sidebar.header("Upload your CSVs (optional)")
up_trips = st.sidebar.file_uploader("trips.csv", type=["csv"])
up_meals = st.sidebar.file_uploader("meals.csv", type=["csv"])

trips = read_csv_with_fallback(up_trips, data_dir / "trips.csv", parse_dates=["start_date", "end_date"])
meals = read_csv_with_fallback(up_meals, data_dir / "meals.csv", parse_dates=["date"])

# Basic schema
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
trips["days"] = (trips["end_date"] - trips["start_date"]).dt.days.clip(lower=1)
trips["cost_per_day"] = (pd.to_numeric(trips["total_cost_usd"], errors="coerce").fillna(0) / trips["days"]).round(2)
for col in ["total_cost_usd", "transportation_cost_usd", "accommodation_cost_usd"]:
    if col in trips.columns:
        trips[col] = pd.to_numeric(trips[col], errors="coerce").fillna(0).clip(lower=0)

# Compute food per trip from meals robustly
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

# For filters
trips["year"] = year_series(trips["start_date"])

# -------------------------
#   SIDEBAR FILTERS + SEARCH
# -------------------------
st.sidebar.header("Filters")
countries = sorted(trips["country"].dropna().unique().tolist())
years = sorted(trips["year"].dropna().unique().tolist())

sel_countries = st.sidebar.multiselect("Country", countries, default=countries)
sel_years = st.sidebar.multiselect("Year", years, default=years)
search = st.sidebar.text_input("Search trips/cities", placeholder="e.g., Tokyo, honeymoon, road trip")
show_labels = st.sidebar.checkbox("Show values on bars", value=True)
sort_by = st.sidebar.selectbox("Sort bars by", ["Start date", "Trip name", "Value"], index=0)

# Apply filters
mask = trips["country"].isin(sel_countries) & trips["year"].isin(sel_years)
t = trips.loc[mask].copy()

# Apply search
if search:
    s = search.strip().lower()
    cols = ["trip_name", "primary_city"] + (["notes"] if "notes" in t.columns else [])
    search_mask = False
    for c in cols:
        search_mask = search_mask | t[c].astype(str).str.lower().str.contains(s, na=False)
    t = t.loc[search_mask].copy()

if t.empty:
    st.info("No trips match the current filters/search. Adjust in the sidebar.")
    st.stop()

# Sorting helper
def sort_frame(df, value_col=None):
    if sort_by == "Start date":
        return df.sort_values("start_date")
    if sort_by == "Trip name":
        return df.sort_values("trip_name")
    if sort_by == "Value" and value_col is not None:
        return df.sort_values(value_col, ascending=False)
    return df

# -------------------------
#   METRIC CARDS
# -------------------------
c1, c2, c3, c4 = st.columns(4)
with c1:
    st.metric("Trips", f"{len(t)}")
with c2:
    st.metric("Countries", f"{t['country'].nunique()}")
with c3:
    st.metric("Total Spend (USD)", f"${int(t['total_cost_usd'].sum()):,}")
with c4:
    st.metric("Median Cost/Day", f"${t['cost_per_day'].median():,.2f}")

st.markdown("---")

# ===========================
#   MAP + TOTAL SPEND
# ===========================
col1, col2 = st.columns([1.25, 1])

with col1:
    st.subheader("🗺️ Where you've been")
    fig_map = px.scatter_geo(
        t,
        lat="lat", lon="lon",
        hover_name="trip_name",
        hover_data={
            "country": True,
            "total_cost_usd": True,
            "days": True,
            "lat": False, "lon": False
        },
        projection="natural earth",
    )
    fig_map.update_traces(marker=dict(color="red", size=9, line=dict(width=1, color="black")))
    fig_map.update_geos(
        showcountries=True, showframe=False,
        landcolor="lightgray", oceancolor="lightblue", showocean=True
    )
    fig_map.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=450, template="simple_white")
    st.plotly_chart(fig_map, use_container_width=True)
    add_download(fig_map, "map.png", key="dl_map")

with col2:
    st.subheader("💵 Total spend per trip")
    df_total = sort_frame(t, "total_cost_usd")
    fig_cost = px.bar(
        df_total,
        x="trip_name", y="total_cost_usd",
        labels={"trip_name": "Trip", "total_cost_usd": "USD"},
        color="total_cost_usd",
        color_continuous_scale="Tealgrn",
    )
    if show_labels:
        fig_cost.update_traces(text=df_total["total_cost_usd"].map(lambda v: f"${int(v):,}"), textposition="outside", cliponaxis=False)
    fig_cost.update_traces(hovertemplate="<b>%{x}</b><br>USD: %{y:,}<extra></extra>")
    fig_cost.update_layout(xaxis_tickangle=-20)
    apply_common_layout(fig_cost, height=450)
    st.plotly_chart(fig_cost, use_container_width=True)
    add_download(fig_cost, "total_spend.png", key="dl_total")

st.markdown("---")

# ===========================
#   COST PER DAY LEADERBOARD
# ===========================
st.subheader("🏆 Cost per day leaderboard")
df_cpd = t.sort_values("cost_per_day", ascending=True).copy()
fig_cpd = px.bar(
    df_cpd,
    x="cost_per_day", y="trip_name",
    orientation="h",
    labels={"cost_per_day": "USD per day", "trip_name": "Trip"},
    color="cost_per_day", color_continuous_scale="Blugrn",
)
if show_labels:
    fig_cpd.update_traces(text=df_cpd["cost_per_day"].map(lambda v: f"${v:,.2f}"), textposition="outside", cliponaxis=False)
fig_cpd.update_traces(hovertemplate="<b>%{y}</b><br>USD/day: %{x:,.2f}<extra></extra>")
median_cpd = float(df_cpd["cost_per_day"].median()) if len(df_cpd) else 0
fig_cpd.add_vline(x=median_cpd, line_dash="dash", line_width=2)
fig_cpd.add_annotation(x=median_cpd, y=-0.5, text=f"Median: ${median_cpd:,.2f}", showarrow=False, yshift=-20)
apply_common_layout(fig_cpd, height=520)
st.plotly_chart(fig_cpd, use_container_width=True)
add_download(fig_cpd, "cost_per_day.png", key="dl_cpd")

st.markdown("---")

# ======================================
#   ⭐ CUISINE RATINGS (RESTO SCORES)
# ======================================
st.subheader("⭐ Cuisine ratings (from meals.csv)")
if {"trip_id", "cuisine", "rating_1_5"}.issubset(meals.columns):
    # Filter meals to the *currently selected* trips
    meals_r = meals.copy()
    meals_r["rating_1_5"] = pd.to_numeric(meals_r["rating_1_5"], errors="coerce")
    meals_r = meals_r[meals_r["trip_id"].isin(t["trip_id"])]

    if meals_r.empty:
        st.info("No meals match the current filters. Add meals or widen your filters.")
    else:
        top_cuisines = (
            meals_r.dropna(subset=["cuisine", "rating_1_5"])
                   .groupby("cuisine", as_index=False)
                   .agg(avg_rating=("rating_1_5", "mean"), count=("rating_1_5", "size"))
                   .sort_values(["avg_rating","count"], ascending=[False, False])
        )
        c1, c2 = st.columns([1,1])
        with c1:
            st.dataframe(top_cuisines, use_container_width=True)
        with c2:
            fig_cuisine = px.bar(
                top_cuisines,
                x="cuisine", y="avg_rating",
                hover_data=["count"],
                labels={"avg_rating":"Avg Rating"},
                color="avg_rating",
                color_continuous_scale="Viridis",
                range_y=[0,5],
            )
            if show_labels:
                fig_cuisine.update_traces(text=top_cuisines["avg_rating"].map(lambda v: f"{v:.2f}"),
                                          textposition="outside", cliponaxis=False)
            fig_cuisine.update_layout(xaxis_tickangle=-30)
            apply_common_layout(fig_cuisine)
            st.plotly_chart(fig_cuisine, use_container_width=True)
            add_download(fig_cuisine, "cuisine_ratings.png", key="dl_cuisine")
else:
    st.info("Your meals.csv needs columns: 'trip_id', 'cuisine', and 'rating_1_5' for cuisine ratings.")

st.markdown("---")

# ======================================
#   TRANSPORT / FOOD / ACCOM SEPARATE BARS
# ======================================

# 🚗 Transportation
st.subheader("🚗 Transportation spend per trip")
if "transportation_cost_usd" in t.columns:
    df_tr = sort_frame(t, "transportation_cost_usd")
    fig_transport = px.bar(
        df_tr,
        x="trip_name", y="transportation_cost_usd",
        labels={"trip_name": "Trip", "transportation_cost_usd": "USD"},
        color="transportation_cost_usd", color_continuous_scale="Tealgrn",
    )
    if show_labels:
        fig_transport.update_traces(text=df_tr["transportation_cost_usd"].map(lambda v: f"${int(v):,}"),
                                    textposition="outside", cliponaxis=False)
    fig_transport.update_traces(hovertemplate="<b>%{x}</b><br>USD: %{y:,}<extra></extra>")
    fig_transport.update_layout(xaxis_tickangle=-20)
    apply_common_layout(fig_transport)
    st.plotly_chart(fig_transport, use_container_width=True)
    add_download(fig_transport, "transportation.png", key="dl_transport")
else:
    st.info("Add a 'transportation_cost_usd' column to trips.csv to see this chart.")

# 🍜 Food (computed)
st.subheader("🍜 Food spend per trip")
if {"trip_id", "cost_usd"}.issubset(meals.columns):
    meals_f = meals.copy()
    meals_f["cost_usd"] = pd.to_numeric(meals_f["cost_usd"], errors="coerce").fillna(0)
    meals_f["trip_id"] = pd.to_numeric(meals_f["trip_id"], errors="coerce").astype("Int64")
    food_by_trip_f = meals_f.groupby("trip_id", dropna=False)["cost_usd"].sum().rename("food_cost_usd")

    tf = t.drop(columns=[c for c in t.columns if c.startswith("food_cost_usd")], errors="ignore")
    tf = tf.merge(food_by_trip_f, how="left", left_on="trip_id", right_index=True)
    tf["food_cost_usd"] = pd.to_numeric(tf["food_cost_usd"], errors="coerce").fillna(0)

    df_food = sort_frame(tf, "food_cost_usd")
    fig_food = px.bar(
        df_food,
        x="trip_name", y="food_cost_usd",
        labels={"trip_name": "Trip", "food_cost_usd": "USD"},
        color="food_cost_usd", color_continuous_scale="Viridis",
    )
    if show_labels:
        fig_food.update_traces(text=df_food["food_cost_usd"].map(lambda v: f"${int(v):,}"),
                               textposition="outside", cliponaxis=False)
    fig_food.update_traces(hovertemplate="<b>%{x}</b><br>USD: %{y:,}<extra></extra>")
    fig_food.update_layout(xaxis_tickangle=-20)
    apply_common_layout(fig_food)
    st.plotly_chart(fig_food, use_container_width=True)
    add_download(fig_food, "food.png", key="dl_food")
else:
    st.info("Your meals.csv needs 'trip_id' and 'cost_usd' to compute food totals.")

# 🏨 Accommodation
st.subheader("🏨 Accommodation spend per trip")
if "accommodation_cost_usd" in t.columns:
    df_ac = sort_frame(t, "accommodation_cost_usd")
    fig_accom = px.bar(
        df_ac,
        x="trip_name", y="accommodation_cost_usd",
        labels={"trip_name": "Trip", "accommodation_cost_usd": "USD"},
        color="accommodation_cost_usd", color_continuous_scale="Purples",
    )
    if show_labels:
        fig_accom.update_traces(text=df_ac["accommodation_cost_usd"].map(lambda v: f"${int(v):,}"),
                                textposition="outside", cliponaxis=False)
    fig_accom.update_traces(hovertemplate="<b>%{x}</b><br>USD: %{y:,}<extra></extra>")
    fig_accom.update_layout(xaxis_tickangle=-20)
    apply_common_layout(fig_accom)
    st.plotly_chart(fig_accom, use_container_width=True)
    add_download(fig_accom, "accommodation.png", key="dl_accom")
else:
    st.info("Add an 'accommodation_cost_usd' column to trips.csv to see this chart.")

st.caption("Use the sidebar to filter by country/year and search trips. PNG downloads require `kaleido`.")