import os
import pandas as pd
import pydeck as pdk
import streamlit as st

from databricks import sql
from databricks.sdk.core import Config


# -----------------------------
# Page configuration
# -----------------------------
st.set_page_config(
    page_title="Western LA Wildfire Situational Awareness",
    page_icon="🔥",
    layout="wide",
)


# -----------------------------
# Databricks connection
# -----------------------------
cfg = Config()

WAREHOUSE_ID = os.getenv("WAREHOUSE_ID")

CURRENT_TABLE = (
    "dbw_sce_wildfire_dev.default.wildfire_gold_current"
)


def get_connection():
    if not WAREHOUSE_ID:
        raise RuntimeError(
            "WAREHOUSE_ID is not configured for this Databricks App."
        )

    server_hostname = cfg.host

    if server_hostname.startswith("https://"):
        server_hostname = server_hostname.replace("https://", "")

    if server_hostname.startswith("http://"):
        server_hostname = server_hostname.replace("http://", "")

    return sql.connect(
        server_hostname=server_hostname,
        http_path=f"/sql/1.0/warehouses/{WAREHOUSE_ID}",
        credentials_provider=lambda: cfg.authenticate,
        _use_arrow_native_complex_types=False,
    )


@st.cache_data(ttl=300)
def load_current_data():
    query = f"""
        SELECT
            zone_id,
            location_name,
            zone_label,
            latitude,
            longitude,
            risk_score,
            risk_category,
            previous_risk_score,
            risk_change,
            category_changed,
            temperature_f,
            relative_humidity_pct,
            wind_speed_mph,
            wind_gust_mph,
            hazard_score,
            historical_fire_count,
            google_maps_url,
            pipeline_run_timestamp
        FROM {CURRENT_TABLE}
    """

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query)
            return cursor.fetchall_arrow().to_pandas()


# -----------------------------
# Load data
# -----------------------------
try:
    df = load_current_data()

except Exception as e:
    st.error("Unable to load wildfire data.")
    st.code(str(e))
    st.stop()


# -----------------------------
# Data preparation
# -----------------------------
df["risk_score"] = pd.to_numeric(
    df["risk_score"],
    errors="coerce",
)

df["risk_change"] = pd.to_numeric(
    df["risk_change"],
    errors="coerce",
).fillna(0)

df["latitude"] = pd.to_numeric(
    df["latitude"],
    errors="coerce",
)

df["longitude"] = pd.to_numeric(
    df["longitude"],
    errors="coerce",
)

df = df.dropna(
    subset=[
        "latitude",
        "longitude",
        "risk_score",
    ]
)


# -----------------------------
# Header
# -----------------------------
st.title("🔥 Western LA Wildfire Situational Awareness")

latest_refresh = df["pipeline_run_timestamp"].max()

st.caption(
    f"Latest pipeline refresh: {latest_refresh}"
)


# -----------------------------
# KPI cards
# -----------------------------
high_count = df[
    df["risk_category"].isin(
        ["High", "Critical"]
    )
].shape[0]

max_risk = df["risk_score"].max()

increasing_count = df[
    df["risk_change"] > 0
].shape[0]

largest_change = df["risk_change"].max()


c1, c2, c3, c4 = st.columns(4)

c1.metric(
    "High / Critical Zones",
    high_count,
)

c2.metric(
    "Highest Risk Score",
    f"{max_risk:.1f}",
)

c3.metric(
    "Zones Increasing",
    increasing_count,
)

c4.metric(
    "Largest Risk Increase",
    f"+{largest_change:.1f}",
)


st.divider()


# -----------------------------
# Map + priority table
# -----------------------------
map_col, table_col = st.columns(
    [2.2, 1]
)


with map_col:

    st.subheader("Operational Risk Map")

    color_map = {
        "Low": [46, 125, 50, 170],
        "Moderate": [255, 193, 7, 180],
        "High": [230, 81, 0, 200],
        "Critical": [183, 28, 28, 220],
    }

    df["map_color"] = df[
        "risk_category"
    ].map(color_map)

    layer = pdk.Layer(
        "ScatterplotLayer",
        data=df,
        get_position=[
            "longitude",
            "latitude",
        ],
        get_fill_color="map_color",
        get_radius=850,
        radius_min_pixels=4,
        radius_max_pixels=10,
        pickable=True,
        stroked=True,
        get_line_color=[255, 255, 255],
        line_width_min_pixels=1,
    )

    view_state = pdk.ViewState(
        latitude=34.10,
        longitude=-118.70,
        zoom=9.1,
        pitch=0,
    )

    tooltip = {
        "html": """
        <b>{zone_label}</b><br/>
        Risk: {risk_score}<br/>
        Category: {risk_category}<br/>
        Change: {risk_change}<br/>
        Gust: {wind_gust_mph} mph<br/>
        Humidity: {relative_humidity_pct}%<br/>
        Temperature: {temperature_f} °F
        """,
        "style": {
            "backgroundColor": "#111827",
            "color": "white",
        },
    }

    deck = pdk.Deck(
        layers=[layer],
        initial_view_state=view_state,
        tooltip=tooltip,
    )

    st.pydeck_chart(
        deck,
        use_container_width=True,
    )


with table_col:

    st.subheader("Top Priority Zones")

    top10 = (
        df.sort_values(
            by=[
                "risk_score",
                "risk_change",
            ],
            ascending=False,
        )
        .head(10)
        [
            [
                "zone_label",
                "risk_score",
                "risk_category",
                "risk_change",
            ]
        ]
        .rename(
            columns={
                "zone_label": "Zone",
                "risk_score": "Risk",
                "risk_category": "Category",
                "risk_change": "Change",
            }
        )
    )

    st.dataframe(
        top10,
        use_container_width=True,
        hide_index=True,
    )


# -----------------------------
# Highest-risk zone details
# -----------------------------
st.divider()

st.subheader("Highest-Risk Zone Snapshot")

highest = (
    df.sort_values(
        "risk_score",
        ascending=False,
    )
    .iloc[0]
)

d1, d2, d3, d4, d5 = st.columns(5)

d1.metric(
    "Zone",
    highest["zone_id"],
)

d2.metric(
    "Risk",
    f'{highest["risk_score"]:.1f}',
)

d3.metric(
    "Risk Change",
    f'{highest["risk_change"]:+.1f}',
)

d4.metric(
    "Wind Gust",
    f'{highest["wind_gust_mph"]:.1f} mph',
)

d5.metric(
    "Humidity",
    f'{highest["relative_humidity_pct"]:.0f}%',
)


if pd.notna(highest["google_maps_url"]):
    st.link_button(
        "Open highest-risk zone in Google Maps",
        highest["google_maps_url"],
    )


st.caption(
    "Public-data prototype for situational awareness. "
    "The Operational Wildfire Risk Index is an analytical "
    "screening measure and is not an SCE proprietary wildfire "
    "or PSPS decision model."
)
