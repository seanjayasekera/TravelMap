import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path

st.set_page_config(page_title="Travel Dashboard (Starter)", layout="wide")

st.title("🌍 Travel Dashboard — Starter")
st.caption("Minimal MVP: map of trips + spend per trip + top cuisines + cost/day leaderboard")

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

trips = read_csv_with_fallback(up_trips, data_dir / "trips.csv", parse_dates=["start_date", "end_date"])
meals = read_csv_with_fallback(up_meals, data_dir / "meals.csv", parse_dates=["date"])

# Basic hygiene
required_trip_cols = {"trip_id","trip_name","start_date","end_date","primary_city","country","lat","lon","total_cost_usd"}
missing = required_trip_cols - set(trips.columns)
if missing:
    st.error(f"Missing columns in trips.csv: {missing}")
    st.stop()

# Derived fields
trips["days"] = (trips["end_date"] - trips["start_date"]).dt.days.clip(lower=1)
trips["cost_per_day"] = (trips["total_cost_usd"] / trips["days"]).round(2)

# ---- Layout ----
col1, col2 = st.columns([1.2, 1])

with col1:
    st.subheader("🗺️ Where you've been")
    st.write("One dot per primary city")

    fig_map = px.scatter_geo(
        trips,
        lat="lat",
        lon="lon",
        hover_name="trip_name",
        hover_data={"country": True, "total_cost_usd": True, "days": True, "lat": False, "lon": False},
        projection="natural earth"
    )

    # 🔹 Make markers bold & red
    fig_map.update_traces(marker=dict(color="red", size=9, line=dict(width=1, color="black")))

    # 🔹 Improve map contrast
    fig_map.update_geos(
        showcountries=True,
        showframe=False,
        landcolor="lightgray",
        oceancolor="lightblue",
        showocean=True
    )

    fig_map.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=450)
    st.plotly_chart(fig_map, use_container_width=True)

with col2:
    st.subheader("💵 Spend per trip")
    fig_cost = px.bar(
        trips.sort_values("start_date"),
        x="trip_name",
        y="total_cost_usd",
        text_auto=True,
        labels={"trip_name":"Trip","total_cost_usd":"USD"},
        color="total_cost_usd",  # 🔹 color scale based on spend
        color_continuous_scale="tealgrn"
    )
    fig_cost.update_traces(textfont_size=12, textangle=0, textposition="outside", cliponaxis=False)
    fig_cost.update_layout(
        height=450,
        xaxis_tickangle=-20,
        margin=dict(t=20),
        coloraxis_showscale=False  # hide legend bar
    )
    st.plotly_chart(fig_cost, use_container_width=True)

st.divider()

# Cuisines summary
st.subheader("🍽️ Your top cuisines (from meals.csv)")
if "cuisine" in meals.columns:
    top_cuisines = meals.groupby("cuisine", as_index=False)["rating_1_5"].mean().rename(columns={"rating_1_5":"avg_rating"})
    top_cuisines["count"] = meals.groupby("cuisine")["cuisine"].transform("count")
    top_cuisines = top_cuisines.sort_values(["avg_rating","count"], ascending=[False,False])

    c1, c2 = st.columns([1,1])
    with c1:
        st.dataframe(top_cuisines, use_container_width=True)
    with c2:
        fig_cuisine = px.bar(
            top_cuisines,
            x="cuisine",
            y="avg_rating",
            hover_data=["count"],
            text_auto=True,
            labels={"avg_rating":"Avg Rating"},
            color="avg_rating",
            color_continuous_scale="viridis"
        )
        fig_cuisine.update_traces(textfont_size=12, textangle=0, textposition="outside", cliponaxis=False)
        fig_cuisine.update_layout(xaxis_tickangle=-30, margin=dict(t=20), coloraxis_showscale=False)
        st.plotly_chart(fig_cuisine, use_container_width=True)
else:
    st.info("Add a 'cuisine' column to meals.csv to see cuisine summaries.")

st.divider()

# 🏆 Cost per day leaderboard
st.subheader("🏆 Cost per day leaderboard (lower is better)")
# Sort by best value (lowest cost/day)
cpd = trips.sort_values("cost_per_day", ascending=True).copy()

fig_cpd = px.bar(
    cpd,
    x="cost_per_day",
    y="trip_name",
    orientation="h",
    text_auto=True,
    labels={"cost_per_day":"USD per day", "trip_name":"Trip"},
    color="cost_per_day",
    color_continuous_scale="blugrn",
)
fig_cpd.update_traces(textfont_size=12, textposition="outside", cliponaxis=False)
fig_cpd.update_layout(
    height=520,
    margin=dict(t=20, r=20, l=10, b=20),
    coloraxis_showscale=False
)
# Add a dashed median reference line
median_cpd = float(cpd["cost_per_day"].median())
fig_cpd.add_vline(x=median_cpd, line_dash="dash", line_width=2)
fig_cpd.add_annotation(
    x=median_cpd, y=-0.5, text=f"Median: ${median_cpd:.2f}", showarrow=False, yshift=-20
)

st.plotly_chart(fig_cpd, use_container_width=True)

st.caption("Next steps: add activities, FX normalization, and a 'trip similarity' card.")