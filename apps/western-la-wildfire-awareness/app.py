import os
import pandas as pd
import pydeck as pdk
import streamlit as st

from databricks import sql
from databricks.sdk.core import Config


# --------------------------------------------------
# Page config
# --------------------------------------------------
st.set_page_config(
    page_title="Western LA Wildfire Situational Awareness",
    page_icon="🔥",
    layout="wide",
)


# --------------------------------------------------
# Databricks config
# --------------------------------------------------
cfg = Config()

WAREHOUSE_ID = os.getenv("WAREHOUSE_ID")

CURRENT_TABLE = (
    "dbw_sce_wildfire_dev.default.wildfire_gold_current"
)

HISTORY_TABLE = (
    "dbw_sce_wildfire_dev.default.wildfire_gold_history"
)


def get_connection():

    if not WAREHOUSE_ID:
        raise RuntimeError(
            "WAREHOUSE_ID is not configured for this Databricks App."
        )

    server_hostname = cfg.host

    server_hostname = (
        server_hostname
        .replace("https://", "")
        .replace("http://", "")
    )

    return sql.connect(
        server_hostname=server_hostname,
        http_path=f"/sql/1.0/warehouses/{WAREHOUSE_ID}",
        credentials_provider=lambda: cfg.authenticate,
        _use_arrow_native_complex_types=False,
    )


# --------------------------------------------------
# Load current data
# --------------------------------------------------
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
            previous_category,
            risk_change,
            category_changed,
            temperature_f,
            relative_humidity_pct,
            wind_speed_mph,
            wind_gust_mph,
            hazard_score,
            historical_fire_count,
            historical_burned_acres,
            last_fire_year,
            hazard_contribution,
            wind_contribution,
            humidity_contribution,
            temperature_contribution,
            history_contribution,
            google_maps_url,
            pipeline_run_timestamp
        FROM {CURRENT_TABLE}
    """

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query)
            return cursor.fetchall_arrow().to_pandas()


# --------------------------------------------------
# Load history
# --------------------------------------------------
@st.cache_data(ttl=300)
def load_history_data():

    query = f"""
        SELECT
            zone_id,
            risk_score,
            risk_category,
            pipeline_run_timestamp
        FROM {HISTORY_TABLE}
        ORDER BY pipeline_run_timestamp
    """

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query)
            return cursor.fetchall_arrow().to_pandas()


# --------------------------------------------------
# Load data
# --------------------------------------------------
try:

    df = load_current_data()
    history_df = load_history_data()

except Exception as e:

    st.error("Unable to load wildfire data.")
    st.code(str(e))
    st.stop()


# --------------------------------------------------
# Prepare data
# --------------------------------------------------
numeric_columns = [
    "risk_score",
    "previous_risk_score",
    "risk_change",
    "temperature_f",
    "relative_humidity_pct",
    "wind_speed_mph",
    "wind_gust_mph",
    "hazard_score",
    "historical_fire_count",
    "historical_burned_acres",
    "hazard_contribution",
    "wind_contribution",
    "humidity_contribution",
    "temperature_contribution",
    "history_contribution",
    "latitude",
    "longitude",
]

for col in numeric_columns:
    if col in df.columns:
        df[col] = pd.to_numeric(
            df[col],
            errors="coerce",
        )


df["risk_change"] = df[
    "risk_change"
].fillna(0)


history_df["risk_score"] = pd.to_numeric(
    history_df["risk_score"],
    errors="coerce",
)

history_df["pipeline_run_timestamp"] = pd.to_datetime(
    history_df["pipeline_run_timestamp"],
    errors="coerce",
)


# --------------------------------------------------
# Header
# --------------------------------------------------
st.title(
    "🔥 Western LA Wildfire Situational Awareness"
)

latest_refresh = df[
    "pipeline_run_timestamp"
].max()

st.caption(
    f"Latest pipeline refresh: {latest_refresh}"
)


# --------------------------------------------------
# KPI row
# --------------------------------------------------
high_count = df[
    df["risk_category"].isin(
        ["High", "Critical"]
    )
].shape[0]

max_risk = df[
    "risk_score"
].max()

increasing_count = df[
    df["risk_change"] > 0
].shape[0]

largest_change = df[
    "risk_change"
].max()


k1, k2, k3, k4 = st.columns(4)

k1.metric(
    "High / Critical Zones",
    high_count,
)

k2.metric(
    "Highest Risk Score",
    f"{max_risk:.1f}",
)

k3.metric(
    "Zones Increasing",
    increasing_count,
)

k4.metric(
    "Largest Risk Increase",
    f"{largest_change:+.1f}",
)


st.divider()


# --------------------------------------------------
# Map + Top priority
# --------------------------------------------------
map_col, priority_col = st.columns(
    [2.1, 1]
)


with map_col:

    st.subheader(
        "Operational Risk Map"
    )

    color_map = {
        "Low": [46, 125, 50, 180],
        "Moderate": [255, 193, 7, 190],
        "High": [230, 81, 0, 210],
        "Critical": [183, 28, 28, 230],
    }

    df["map_color"] = df[
        "risk_category"
    ].map(color_map)

    map_df = df.dropna(
        subset=[
            "latitude",
            "longitude",
        ]
    )

    layer = pdk.Layer(
        "ScatterplotLayer",
        data=map_df,
        get_position=[
            "longitude",
            "latitude",
        ],
        get_fill_color="map_color",
        get_radius=700,
        radius_min_pixels=4,
        radius_max_pixels=9,
        pickable=True,
        stroked=True,
        get_line_color=[
            255,
            255,
            255,
            160,
        ],
        line_width_min_pixels=1,
    )

    view_state = pdk.ViewState(
        latitude=34.10,
        longitude=-118.70,
        zoom=9.2,
        pitch=0,
    )

    tooltip = {
        "html": """
        <b>{zone_label}</b><br/>
        Risk Score: {risk_score}<br/>
        Category: {risk_category}<br/>
        Risk Change: {risk_change}<br/>
        Wind Gust: {wind_gust_mph} mph<br/>
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


with priority_col:

    st.subheader(
        "Top Priority Zones"
    )

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
                "wind_gust_mph",
                "relative_humidity_pct",
            ]
        ]
        .rename(
            columns={
                "zone_label": "Zone",
                "risk_score": "Risk",
                "risk_category": "Category",
                "risk_change": "Change",
                "wind_gust_mph": "Gust",
                "relative_humidity_pct": "Humidity",
            }
        )
    )

    st.dataframe(
        top10,
        use_container_width=True,
        hide_index=True,
    )


st.divider()


# --------------------------------------------------
# Zone selector
# --------------------------------------------------
st.subheader(
    "Zone Investigation"
)

zone_options = (
    df[
        "zone_label"
    ]
    .dropna()
    .sort_values()
    .tolist()
)

selected_zone_label = st.selectbox(
    "Select a zone",
    zone_options,
)


selected = df[
    df["zone_label"]
    == selected_zone_label
].iloc[0]


# --------------------------------------------------
# Selected zone metrics
# --------------------------------------------------
m1, m2, m3, m4, m5 = st.columns(5)

m1.metric(
    "Risk Score",
    f'{selected["risk_score"]:.1f}',
)

m2.metric(
    "Risk Change",
    f'{selected["risk_change"]:+.1f}',
)

m3.metric(
    "Wind Gust",
    f'{selected["wind_gust_mph"]:.1f} mph',
)

m4.metric(
    "Humidity",
    f'{selected["relative_humidity_pct"]:.0f}%',
)

m5.metric(
    "Temperature",
    f'{selected["temperature_f"]:.1f} °F',
)


# --------------------------------------------------
# Zone details + risk drivers
# --------------------------------------------------
detail_col, driver_col = st.columns(
    [1, 1]
)


with detail_col:

    st.markdown(
        "#### Zone Context"
    )

    st.write(
        f"**Zone ID:** {selected['zone_id']}"
    )

    st.write(
        f"**Location:** {selected['location_name']}"
    )

    st.write(
        f"**Risk Category:** {selected['risk_category']}"
    )

    st.write(
        f"**Previous Category:** {selected['previous_category']}"
    )

    st.write(
        f"**Hazard Score:** {selected['hazard_score']}"
    )

    st.write(
        f"**Historical Fire Count:** "
        f"{selected['historical_fire_count']}"
    )

    st.write(
        f"**Historical Burned Acres:** "
        f"{selected['historical_burned_acres']:.0f}"
    )

    if pd.notna(
        selected["google_maps_url"]
    ):

        st.link_button(
            "Open zone in Google Maps",
            selected[
                "google_maps_url"
            ],
        )


with driver_col:

    st.markdown(
        "#### Risk Drivers"
    )

    driver_df = pd.DataFrame(
        {
            "Driver": [
                "Hazard",
                "Wind",
                "Humidity",
                "Temperature",
                "History",
            ],

            "Contribution": [
                selected[
                    "hazard_contribution"
                ],
                selected[
                    "wind_contribution"
                ],
                selected[
                    "humidity_contribution"
                ],
                selected[
                    "temperature_contribution"
                ],
                selected[
                    "history_contribution"
                ],
            ],
        }
    )

    st.bar_chart(
        driver_df,
        x="Driver",
        y="Contribution",
        use_container_width=True,
    )


st.divider()


# --------------------------------------------------
# Historical trend
# --------------------------------------------------
st.subheader(
    "Risk Trend"
)

selected_zone_id = selected[
    "zone_id"
]

zone_history = (
    history_df[
        history_df["zone_id"]
        == selected_zone_id
    ]
    .dropna(
        subset=[
            "pipeline_run_timestamp",
            "risk_score",
        ]
    )
    .sort_values(
        "pipeline_run_timestamp"
    )
)


if zone_history.empty:

    st.info(
        "No historical snapshots available "
        "for this zone."
    )

else:

    trend_df = (
        zone_history[
            [
                "pipeline_run_timestamp",
                "risk_score",
            ]
        ]
        .set_index(
            "pipeline_run_timestamp"
        )
    )

    st.line_chart(
        trend_df,
        use_container_width=True,
    )


# --------------------------------------------------
# Alert preview
# --------------------------------------------------
st.divider()

st.subheader(
    "Operational Alert Preview"
)

alert_df = df[
    (
        df["risk_category"].isin(
            [
                "High",
                "Critical",
            ]
        )
    )
    |
    (
        df["risk_change"] >= 10
    )
    |
    (
        df["category_changed"]
        == True
    )
]


if alert_df.empty:

    st.success(
        "No active High / Critical, "
        "major risk-increase, or category-change alerts."
    )

else:

    alert_display = (
        alert_df[
            [
                "zone_label",
                "risk_score",
                "risk_category",
                "risk_change",
            ]
        ]
        .sort_values(
            "risk_score",
            ascending=False,
        )
        .rename(
            columns={
                "zone_label": "Zone",
                "risk_score": "Risk",
                "risk_category": "Category",
                "risk_change": "Change",
            }
        )
    )

    st.warning(
        f"{len(alert_display)} active alert zone(s)"
    )

    st.dataframe(
        alert_display,
        use_container_width=True,
        hide_index=True,
    )


# --------------------------------------------------
# Disclaimer
# --------------------------------------------------
st.divider()

st.caption(
    "Public-data prototype demonstrating how geospatial "
    "wildfire hazard, historical wildfire exposure, and "
    "near-real-time weather can be integrated into a "
    "zone-level situational-awareness dataset. "
    "The Operational Wildfire Risk Index is an analytical "
    "screening measure and is not intended to reproduce "
    "SCE proprietary wildfire-risk or PSPS decision models."
)
