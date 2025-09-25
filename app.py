import streamlit as st
import pandas as pd
import plotly.express as px
from io import StringIO
from geopy.geocoders import Nominatim

st.set_page_config(page_title="Travel Map", layout="wide")

# --------------------------
# Travel-themed background
# --------------------------
st.markdown("""
<style>
html, body, .stApp {
  height: 100%;
  background:
    linear-gradient(rgba(0,0,0,0.05), rgba(0,0,0,0.05)),
    url('https://upload.wikimedia.org/wikipedia/commons/thumb/9/9a/BlankMap-World-v2.png/2000px-BlankMap-World-v2.png')
      no-repeat center center fixed;
  background-size: cover;
}
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
h1, h2, h3, h4, h5, h6 { color: #0f172a; }
.js-plotly-plot .plotly .bg { fill: rgba(255,255,255,0.0) !important; }
</style>
""", unsafe_allow_html=True)

# --------------------------
# Helpers
# --------------------------
@st.cache_data
def load_data(trips_file, meals_file):
    trips = pd.read_csv(trips_file, parse_dates=["start_date", "end_date"], dayfirst=False)
    meals = pd.read_csv(meals_file, parse_dates=["date"], dayfirst=False)
    return trips, meals

def df_to_csv_bytes(df: pd.DataFrame) -> bytes:
    buf = StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")

def template_trips_bytes() -> bytes:
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

# --------------------------
# Sidebar: Uploads & Templates
# --------------------------
st.sidebar.header("Upload your data")
trips_file = st.sidebar.file_uploader("Upload trips.csv", type="csv")
meals_file = st.sidebar.file_uploader("Upload meals.csv", type="csv")

st.sidebar.header("Download Templates")
st.sidebar.download_button(
    "Download trips.csv template",
    data=template_trips_bytes(),
    file_name="trips.csv",
    mime="text/csv",
)
st.sidebar.download_button(
    "Download meals.csv template",
    data=template_meals_bytes(),
    file_name="meals.csv",
    mime="text/csv",
)

with st.sidebar.expander("ℹ️ How to use this app"):
    st.write("""
    1. Download the sample CSVs above.
    2. Open them in Excel or Google Sheets.
    3. Replace the example row with your own trip and meal data.
    4. Upload the updated files here to see your visualizations.
    """)

# --------------------------
# Main
# --------------------------
st.title("✈️ Travel Map Dashboard")

if trips_file is None or meals_file is None:
    st.info("👈 Please upload both **trips.csv** and **meals.csv** to begin.")
else:
    trips, meals = load_data(trips_file, meals_file)

    for c in ["lat", "lon", "total_cost_usd", "transportation_cost_usd", "accommodation_cost_usd"]:
        if c in trips.columns:
            trips[c] = pd.to_numeric(trips[c], errors="coerce")

    # Map of Trips
    st.subheader("Your Trips Map")
    if {"lat", "lon"}.issubset(trips.columns) and len(trips):
        fig_map = px.scatter_geo(
            trips,
            lat="lat",
            lon="lon",
            hover_name="trip_name",
            size="total_cost_usd" if "total_cost_usd" in trips.columns else None,
            projection="natural earth",
            title="Trips Around the World",
        )
        fig_map.update_geos(showcoastlines=True, showcountries=True, showland=True, fitbounds="locations")
        st.plotly_chart(fig_map, use_container_width=True)
    else:
        st.warning("Map requires 'lat' and 'lon' columns in trips.csv.")

    # Cost Visualizations
    st.subheader("Trip Cost Overview")
    if "total_cost_usd" in trips.columns:
        fig_total = px.bar(trips, x="trip_name", y="total_cost_usd", title="Total Spend per Trip (USD)")
        st.plotly_chart(fig_total, use_container_width=True)

    cols = st.columns(3)
    with cols[0]:
        if "transportation_cost_usd" in trips.columns:
            fig_transport = px.bar(trips, x="trip_name", y="transportation_cost_usd", title="Transportation Costs (USD)")
            st.plotly_chart(fig_transport, use_container_width=True)
    with cols[1]:
        if "food_cost_usd" in trips.columns:
            fig_food = px.bar(trips, x="trip_name", y="food_cost_usd", title="Food Costs (USD)")
            st.plotly_chart(fig_food, use_container_width=True)
    with cols[2]:
        if "accommodation_cost_usd" in trips.columns:
            fig_accommodation = px.bar(trips, x="trip_name", y="accommodation_cost_usd", title="Accommodation Costs (USD)")
            st.plotly_chart(fig_accommodation, use_container_width=True)

    # Cost per Day Leaderboard
    st.subheader("Cost per Day Leaderboard")
    if {"start_date", "end_date", "total_cost_usd"}.issubset(trips.columns):
        trips = trips.copy()
        trips["days"] = (pd.to_datetime(trips["end_date"]) - pd.to_datetime(trips["start_date"])).dt.days + 1
        trips["days"] = trips["days"].clip(lower=1)
        trips["cost_per_day"] = pd.to_numeric(trips["total_cost_usd"], errors="coerce") / trips["days"]
        leaderboard = trips[["trip_name", "cost_per_day"]].sort_values("cost_per_day")
        st.dataframe(leaderboard.reset_index(drop=True), use_container_width=True)
    else:
        st.info("Cost per day needs start_date, end_date, and total_cost_usd in trips.csv.")

    # Food Ratings
    st.subheader("Food Ratings")
    meals_show = meals.copy()
    if "date" in meals_show.columns:
        meals_show["date"] = pd.to_datetime(meals_show["date"], errors="coerce").dt.date
    if "trip_id" in meals_show.columns and "trip_id" in trips.columns:
        table_df = meals_show.merge(trips[["trip_id", "trip_name"]], on="trip_id", how="left")
    else:
        table_df = meals_show.assign(trip_name="")
    keep_cols = [c for c in ["trip_name","date","cuisine","restaurant","dish_name","rating_1_10","cost_usd","notes"] if c in table_df.columns]
    st.dataframe(table_df[keep_cols].reset_index(drop=True), use_container_width=True)

# Footer
st.markdown("---")
st.markdown(
    "🌍 Check out more travel stories at [somewhere-else.org](https://somewhere-else.org)",
    unsafe_allow_html=True,
)