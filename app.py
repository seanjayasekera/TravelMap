import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from geopy.geocoders import Nominatim

st.set_page_config(page_title="Travel Map", layout="wide")

# --------------------------
# Load Data
# --------------------------
@st.cache_data
def load_data(trips_file, meals_file):
    trips = pd.read_csv(trips_file, parse_dates=["start_date", "end_date"])
    meals = pd.read_csv(meals_file, parse_dates=["date"])
    return trips, meals

# Initialize geolocator
geolocator = Nominatim(user_agent="travel_app")

# --------------------------
# Sidebar Uploads & Templates
# --------------------------
st.sidebar.header("Upload your data")
trips_file = st.sidebar.file_uploader("Upload trips.csv", type="csv")
meals_file = st.sidebar.file_uploader("Upload meals.csv", type="csv")

st.sidebar.header("Download Templates")
with open("trips.csv", "rb") as f:
    st.sidebar.download_button("Download trips.csv template", f, file_name="trips.csv", mime="text/csv")
with open("meals.csv", "rb") as f:
    st.sidebar.download_button("Download meals.csv template", f, file_name="meals.csv", mime="text/csv")

if trips_file and meals_file:
    trips, meals = load_data(trips_file, meals_file)

    # --------------------------
    # Main Title
    # --------------------------
    st.title("✈️ Travel Map Dashboard")

    # --------------------------
    # Map of Trips
    # --------------------------
    st.subheader("Your Trips Map")
    fig_map = px.scatter_geo(
        trips,
        lat="lat",
        lon="lon",
        hover_name="trip_name",
        size="total_cost_usd",
        projection="natural earth",
        title="Trips Around the World"
    )
    fig_map.update_geos(showcoastlines=True, showcountries=True, showland=True, fitbounds="locations")
    st.plotly_chart(fig_map, use_container_width=True)

    # --------------------------
    # Cost Visualizations
    # --------------------------
    st.subheader("Trip Cost Overview")
    fig_total = px.bar(trips, x="trip_name", y="total_cost_usd", title="Total Spend per Trip (USD)")
    st.plotly_chart(fig_total, use_container_width=True)

    col1, col2, col3 = st.columns(3)
    with col1:
        fig_transport = px.bar(trips, x="trip_name", y="transportation_cost_usd", title="Transportation Costs (USD)")
        st.plotly_chart(fig_transport, use_container_width=True)
    with col2:
        fig_food = px.bar(trips, x="trip_name", y="food_cost_usd", title="Food Costs (USD)")
        st.plotly_chart(fig_food, use_container_width=True)
    with col3:
        fig_accommodation = px.bar(trips, x="trip_name", y="accommodation_cost_usd", title="Accommodation Costs (USD)")
        st.plotly_chart(fig_accommodation, use_container_width=True)

    # --------------------------
    # Cost per Day Leaderboard
    # --------------------------
    st.subheader("Cost per Day Leaderboard")
    trips["days"] = (trips["end_date"] - trips["start_date"]).dt.days + 1
    trips["cost_per_day"] = trips["total_cost_usd"] / trips["days"]
    leaderboard = trips[["trip_name", "cost_per_day"]].sort_values("cost_per_day")
    st.dataframe(leaderboard.reset_index(drop=True), use_container_width=True)

    # --------------------------
    # Food Ratings
    # --------------------------
    st.subheader("Food Ratings")
    if "date" in meals.columns:
        meals["date"] = pd.to_datetime(meals["date"], errors="coerce").dt.date
    table_df = meals.merge(trips[["trip_id", "trip_name"]], on="trip_id", how="left")
    table_df = table_df[["trip_name", "date", "cuisine", "restaurant", "dish_name", "rating_1_10", "cost_usd", "notes"]]
    st.dataframe(table_df.reset_index(drop=True), use_container_width=True)

else:
    st.info("👈 Please upload both trips.csv and meals.csv to begin.")

# --------------------------
# Footer with Website Link
# --------------------------
st.markdown("---")
st.markdown(
    "🌍 Check out more travel stories at [somewhere-else.org](https://somewhere-else.org)",
    unsafe_allow_html=True,
)