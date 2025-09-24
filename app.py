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

# -------------------------
#   LOAD DATA
# -------------------------
data_dir = Path(__file__).parent / "data"

st.sidebar.header("Upload your CSVs (optional)")
up_trips = st.sidebar.file_uploader("trips.csv", type=["csv"])
up_meals = st.sidebar.file_uploader("meals.csv", type=["csv"])

trips = read_csv_with_fallback(up_trips, data_dir / "trips.csv", parse_dates=["start_date", "end_date"])
meals = read_csv_with_fallback(up_meals, data_dir / "meals.csv", parse_dates=["date"])

# -------------------------
#   QUICK DIAGNOSTICS
# -------------------------
with st.sidebar.expander("Data check", expanded=False):
    st.write("**meals.csv columns:**", list(meals.columns))
    st.write("Contains `dish_name`? →", "✅ yes" if "dish_name" in meals.columns else "❌ no")
    st.write("Contains `rating_1_10`? →", "✅ yes" if "rating_1_10" in meals.columns else "❌ no")
    try:
        st.dataframe(meals.head(), use_container_width=True)
    except Exception as e:
        st.write("Couldn't display preview:", e)

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
trips["year"] = year_series(trips["start_date"])

# -------------------------
#   FILTERS
# -------------------------
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
with c3: st.metric("Total Spend (USD)", f"${int(t['total_cost_usd'].sum()):,}")
with c4: st.metric("Median Cost/Day", f"${t['cost_per_day'].median():,.2f}")

st.markdown("---")

# -------------------------
#   MAP
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

    # Force pure date strings for display
    if "date" in meals_r.columns:
        meals_r["date_str"] = pd.to_datetime(meals_r["date"], errors="coerce").dt.strftime("%Y-%m-%d")

    # Filter meals to trips currently in view
    meals_r = meals_r[meals_r["trip_id"].isin(t["trip_id"])]

    # 🔗 Bring in trip_name so we can display names instead of IDs
    meals_r = meals_r.merge(
        t[["trip_id", "trip_name"]],
        how="left",
        on="trip_id"
    )

    if meals_r.empty:
        st.info("No meals match the current filters.")
    else:
        # Build table with trip_name (no trip_id)
        display_cols = [c for c in ["meal_id","trip_name","date_str","cuisine","restaurant","dish_name","rating_1_10","cost_usd"] if c in meals_r.columns]
        sort_col = "meal_id" if "meal_id" in meals_r.columns else "trip_name"
        table_df = meals_r[display_cols].sort_values(sort_col, ascending=True).reset_index(drop=True)
        table_df = table_df.rename(columns={"date_str": "date"})

        # Hide index reliably
        try:
            st.dataframe(table_df, use_container_width=True, hide_index=True)
        except TypeError:
            sty = table_df.style
            try:
                sty = sty.hide(axis="index")
            except Exception:
                try:
                    sty = sty.hide_index()
                except Exception:
                    pass
            st.dataframe(sty, use_container_width=True)

        # Cuisine averages chart
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

st.caption("If you don't see '⬇️ Download PNG' buttons, use the chart toolbar's camera icon.")