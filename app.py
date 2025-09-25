import streamlit as st
import pandas as pd
import plotly.express as px
from geopy.geocoders import Nominatim

# =========================
#   PAGE CONFIG
# =========================
st.set_page_config(page_title="Travel Dashboard", layout="wide")

# =========================
#   GLOBAL STYLES
# =========================
st.markdown("""
<style>
/* Background image (vintage parchment map) */
.stApp {
    background-image: url('https://upload.wikimedia.org/wikipedia/commons/9/9a/Vintage_world_map_parchment.jpg');
    background-size: cover;
    background-attachment: fixed;
    background-position: center;
    color: #000000;
}

/* Glassmorphism effect for panels */
.block-container {
    background: rgba(255,255,255,0.60);
    backdrop-filter: blur(6px);
    -webkit-backdrop-filter: blur(6px);
    border-radius: 16px;
    padding: 1.2rem 1.4rem;
    box-shadow: 0 10px 30px rgba(0,0,0,0.08);
}

/* --- SIDEBAR NAVY BLUE --- */
section[data-testid="stSidebar"],
[data-testid="stSidebar"] {
    background-color: #0a192f !important;   /* navy blue */
    color: #ffffff !important;
    border-right: 1px solid #0a192f !important;
}
[data-testid="stSidebar"] * {
    color: #ffffff !important;
}
[data-testid="stSidebar"] h2, 
[data-testid="stSidebar"] h3 {
    color: #ffffff !important;
}
[data-testid="stSidebar"] [data-testid="stExpander"] > div {
    background: #112240 !important;  /* darker navy */
    border: 1px solid #1e2a47 !important;
    border-radius: 10px !important;
}
:root { --sidebar-background-color: #0a192f; }

/* Transparent plot backgrounds */
.js-plotly-plot .plotly .bg { fill: rgba(255,255,255,0.0) !important; }
</style>
""", unsafe_allow_html=True)

# =========================
#   TITLE BAR
# =========================
st.markdown("""
<style>
.topbar {
  position: sticky; top: 0; z-index: 1000;
  background: rgba(15,37,87,0.92); /* navy */
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
  color: #ffffff; padding: 14px 18px; margin: -1rem -1rem 1rem -1rem;
  border-bottom: 1px solid rgba(255,255,255,0.12);
  border-radius: 0 0 12px 12px;
}
.topbar h1 { margin: 0; font-size: 1.6rem; line-height: 1.2; }
.topbar .sub { font-size: 0.95rem; opacity: 0.95; margin-top: 2px; }
</style>
<div class="topbar">
  <h1>🌍 Travel Dashboard</h1>
  <div class="sub">Track trips, meals, and costs • somewhere-else.org</div>
</div>
""", unsafe_allow_html=True)

# =========================
#   FILE UPLOADS
# =========================
st.sidebar.header("Upload Your Data")

trips_file = st.sidebar.file_uploader("Upload trips.csv", type="csv")
meals_file = st.sidebar.file_uploader("Upload meals.csv", type="csv")

# =========================
#   LOAD DATA
# =========================
if trips_file:
    trips = pd.read_csv(trips_file)
else:
    trips = pd.DataFrame()

if meals_file:
    meals = pd.read_csv(meals_file)
else:
    meals = pd.DataFrame()

# =========================
#   GEOCODER (for city lookups)
# =========================
geolocator = Nominatim(user_agent="travel_dashboard")

def get_coordinates(city, country):
    try:
        location = geolocator.geocode(f"{city}, {country}")
        if location:
            return location.latitude, location.longitude
    except:
        return None, None
    return None, None

# =========================
#   MAIN DASHBOARD
# =========================
if not trips.empty:
    st.subheader("Trip Map")
    fig_map = px.scatter_geo(
        trips,
        lat="lat",
        lon="lon",
        text="trip_name",
        hover_name="trip_name",
        size="total_cost_usd",
        projection="natural earth"
    )
    st.plotly_chart(fig_map, use_container_width=True)

    st.subheader("Cost Breakdown per Trip")
    fig_costs = px.bar(
        trips,
        x="trip_name",
        y=["transportation_cost_usd", "accommodation_cost_usd"],
        title="Trip Cost Categories",
        barmode="group"
    )
    st.plotly_chart(fig_costs, use_container_width=True)

if not meals.empty:
    st.subheader("Food Ratings")
    meals["date"] = pd.to_datetime(meals["date"]).dt.date
    meals_display = meals.merge(trips[["trip_id", "trip_name"]], on="trip_id", how="left")
    st.dataframe(
        meals_display[["trip_name", "date", "cuisine", "restaurant", "dish_name", "rating_1_10", "cost_usd"]],
        use_container_width=True,
        hide_index=True
    )

# =========================
#   SIDEBAR: HOW TO USE
# =========================
with st.sidebar.expander("ℹ️ How to Use"):
    st.markdown("""
    1. Download the **sample CSVs** below.  
    2. Fill them in with your own trips and meals.  
    3. Upload them back into the app to see your travel dashboard update live.  
    """)

    with open("trips.csv", "w") as f:
        f.write("trip_id,trip_name,start_date,end_date,primary_city,country,lat,lon,total_cost_usd,transportation_cost_usd,accommodation_cost_usd\n1,Tokyo Spring Break,2023-03-15,2023-03-22,Tokyo,Japan,35.6895,139.6917,2000,600,800\n")
    with open("meals.csv", "w") as f:
        f.write("meal_id,trip_id,date,cuisine,restaurant,dish_name,rating_1_10,cost_usd\n1,1,2023-03-16,Japanese,Ichiran,Tonkotsu Ramen,9,12\n")

    with open("trips.csv", "rb") as f:
        st.download_button("Download trips.csv (template)", f, "trips.csv")
    with open("meals.csv", "rb") as f:
        st.download_button("Download meals.csv (template)", f, "meals.csv")