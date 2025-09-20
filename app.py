import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path

st.set_page_config(page_title="Travel Dashboard", page_icon="🌍", layout="wide")
st.title("🌍 Travel Dashboard")
st.caption("Trips, spend, cuisines — with separate Transportation, Food, and Accommodation charts")

# ---- Data loading helpers ----
def read_csv_with_fallback(uploaded, default_path, **read_kwargs):
    if uploaded is not None:
        return pd.read_csv(uploaded, **read_kwargs)
    else:
        return pd.read_csv(default_path, **read_kwargs)

data_dir = Path(__file__).parent / "data"

st.sidebar.header("Upload your CSVs (optional)")
up_trips = st.sidebar.file_uploader("trips.csv", type=["csv"])
up_meals = st.sidebar.file_uploader("meals.csv", type=["csv"])

# 👉 Set your default filenames (make sure these exist in data/)
trips = read_csv_with_fallback(up_trips, data_dir / "trips.csv", parse_dates=["start_date", "end_date"])
meals = read_csv_with_fallback(up_meals, data_dir / "meals.csv", parse_dates=["date"])

# ---- Basic hygiene ----
required_trip_cols = {
    "trip_id","trip_name","start_date","end_date",
    "primary_city","country","lat","lon","total_cost_usd"
}
missing = required_trip_cols - set(trips.columns)
if missing:
    st.error(f"Missing columns in trips.csv: {missing}")
    st.stop()

# ---- Derived fields on trips ----
trips["days"] = (trips["end_date"] - trips["start_date"]).dt.days.clip(lower=1)
trips["cost_per_day"] = (trips["total_cost_usd"] / trips["days"]).round(2)

# ---- Ensure numeric and non-negative on known spend columns that exist ----
for col in ["total_cost_usd", "transportation_cost_usd", "accommodation_cost_usd"]:
    if col in trips.columns:
        trips[col] = pd.to_numeric(trips[col], errors="coerce").fillna(0).clip(lower=0)

# ===========================
#   LAYOUT: MAP + TOTAL SPEND
# ===========================
col1, col2 = st.columns([1.2, 1])

with col1:
    st.subheader("🗺️ Where you've been")
    fig_map = px.scatter_geo(
        trips,
        lat="lat",
        lon="lon",
        hover_name="trip_name",
        hover_data={"country": True, "total_cost_usd": True, "days": True, "lat": False, "lon": False},
        projection="natural earth",
    )
    # Bold, visible markers
    fig_map.update_traces(marker=dict(color="red", size=9, line=dict(width=1, color="black")))
    # Higher contrast basemap
    fig_map.update_geos(
        showcountries=True, showframe=False,
        landcolor="lightgray", oceancolor="lightblue", showocean=True
    )
    fig_map.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=450)
    st.plotly_chart(fig_map, use_container_width=True)

with col2:
    st.subheader("💵 Total spend per trip")
    fig_cost = px.bar(
        trips.sort_values("start_date"),
        x="trip_name", y="total_cost_usd",
        text_auto=True,
        labels={"trip_name": "Trip", "total_cost_usd": "USD"},
        color="total_cost_usd",
        color_continuous_scale="tealgrn",
    )
    fig_cost.update_traces(textfont_size=12, textposition="outside", cliponaxis=False)
    fig_cost.update_layout(height=450, xaxis_tickangle=-20, margin=dict(t=20), coloraxis_showscale=False)
    st.plotly_chart(fig_cost, use_container_width=True)

st.divider()

# ===========================
#   COST PER DAY LEADERBOARD
# ===========================
st.subheader("🏆 Cost per day leaderboard")
cpd = trips.sort_values("cost_per_day", ascending=True).copy()
fig_cpd = px.bar(
    cpd,
    x="cost_per_day", y="trip_name",
    orientation="h", text_auto=True,
    labels={"cost_per_day": "USD per day", "trip_name": "Trip"},
    color="cost_per_day", color_continuous_scale="blugrn",
)
fig_cpd.update_traces(textfont_size=12, textposition="outside", cliponaxis=False)
fig_cpd.update_layout(height=520, margin=dict(t=20, r=20, l=10, b=20), coloraxis_showscale=False)
median_cpd = float(cpd["cost_per_day"].median()) if len(cpd) else 0
fig_cpd.add_vline(x=median_cpd, line_dash="dash", line_width=2)
fig_cpd.add_annotation(x=median_cpd, y=-0.5, text=f"Median: ${median_cpd:.2f}", showarrow=False, yshift=-20)
st.plotly_chart(fig_cpd, use_container_width=True)

st.divider()

# ======================================
#   TRANSPORT / FOOD / ACCOM SEPARATE BARS
# ======================================

# 🚗 Transportation spend per trip
st.subheader("🚗 Transportation spend per trip")
if "transportation_cost_usd" in trips.columns:
    fig_transport = px.bar(
        trips.sort_values("start_date"),
        x="trip_name", y="transportation_cost_usd",
        text_auto=True,
        labels={"trip_name": "Trip", "transportation_cost_usd": "USD"},
        color="transportation_cost_usd",
        color_continuous_scale="tealgrn",
    )
    fig_transport.update_traces(textfont_size=12, textposition="outside", cliponaxis=False)
    fig_transport.update_layout(height=420, xaxis_tickangle=-20, margin=dict(t=20), coloraxis_showscale=False)
    st.plotly_chart(fig_transport, use_container_width=True)
else:
    st.info("Add a 'transportation_cost_usd' column to trips.csv to see this chart.")

# 🍜 Food spend per trip (computed from meals.csv) — de-dupe safe and robust
st.subheader("🍜 Food spend per trip")
if {"trip_id", "cost_usd"}.issubset(meals.columns):
    meals = meals.copy()
    meals["cost_usd"] = pd.to_numeric(meals["cost_usd"], errors="coerce").fillna(0)
    meals["trip_id"] = pd.to_numeric(meals["trip_id"], errors="coerce").astype("Int64")

    food_by_trip = meals.groupby("trip_id", dropna=False)["cost_usd"].sum().rename("food_cost_usd")

    # Remove any existing food columns (_x/_y from reruns) then merge fresh
    trips = trips.drop(columns=[c for c in trips.columns if c.startswith("food_cost_usd")], errors="ignore")
    trips = trips.merge(food_by_trip, how="left", left_on="trip_id", right_index=True)
    trips["food_cost_usd"] = pd.to_numeric(trips["food_cost_usd"], errors="coerce").fillna(0)

    if trips["food_cost_usd"].sum() == 0 and len(meals) > 0:
        st.info("No food costs matched your trips. Check that trip_id values in meals.csv match trips.csv.")
    else:
        fig_food = px.bar(
            trips.sort_values("start_date"),
            x="trip_name", y="food_cost_usd",
            text_auto=True,
            labels={"trip_name": "Trip", "food_cost_usd": "USD"},
            color="food_cost_usd",
            color_continuous_scale="viridis",
        )
        fig_food.update_traces(textfont_size=12, textposition="outside", cliponaxis=False)
        fig_food.update_layout(height=420, xaxis_tickangle=-20, margin=dict(t=20), coloraxis_showscale=False)
        st.plotly_chart(fig_food, use_container_width=True)
else:
    st.info("Your meals.csv needs columns named exactly: 'trip_id' and 'cost_usd' to compute food totals.")

# 🏨 Accommodation spend per trip
st.subheader("🏨 Accommodation spend per trip")
if "accommodation_cost_usd" in trips.columns:
    fig_accom = px.bar(
        trips.sort_values("start_date"),
        x="trip_name", y="accommodation_cost_usd",
        text_auto=True,
        labels={"trip_name": "Trip", "accommodation_cost_usd": "USD"},
        color="accommodation_cost_usd",
        color_continuous_scale="purples",
    )
    fig_accom.update_traces(textfont_size=12, textposition="outside", cliponaxis=False)
    fig_accom.update_layout(height=420, xaxis_tickangle=-20, margin=dict(t=20), coloraxis_showscale=False)
    st.plotly_chart(fig_accom, use_container_width=True)
else:
    st.info("Add an 'accommodation_cost_usd' column to trips.csv to see this chart.")

st.caption(
    "Food totals are computed from meals.csv. Transportation/Accommodation are read from trips.csv if present."
)