import os
import pandas as pd
import pydeck as pdk
import streamlit as st

from databricks import sql
from databricks.sdk.core import Config


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Western LA Wildfire Situational Awareness",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ============================================================
# UI STYLING
# ============================================================

st.markdown(
    """
<style>
.block-container {
    padding-top: 1.5rem;
    padding-bottom: 2rem;
    max-width: 1500px;
}

div[data-testid="stMetric"] {
    border: 1px solid rgba(128,128,128,0.25);
    border-radius: 12px;
    padding: 14px 16px;
}

div[data-testid="stMetricValue"] {
    font-size: 2rem;
    font-weight: 700;
}

.risk-legend {
    display: flex;
    gap: 18px;
    align-items: center;
    flex-wrap: wrap;
    margin: 4px 0 12px 0;
    font-size: 14px;
}

.legend-item {
    display: flex;
    align-items: center;
    gap: 6px;
}

.legend-dot {
    width: 12px;
    height: 12px;
    border-radius: 50%;
    display: inline-block;
}

.status-box {
    border: 1px solid rgba(128,128,128,0.25);
    border-radius: 10px;
    padding: 12px 16px;
    margin-bottom: 12px;
}
</style>
""",
    unsafe_allow_html=True,
)


# ============================================================
# DATABRICKS CONFIGURATION
# ============================================================

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

    server_hostname = (
        cfg.host
        .replace("https://", "")
        .replace("http://", "")
    )

    return sql.connect(
        server_hostname=server_hostname,
        http_path=f"/sql/1.0/warehouses/{WAREHOUSE_ID}",
        credentials_provider=lambda: cfg.authenticate,
        _use_arrow_native_complex_types=False,
    )


# ============================================================
# LOAD CURRENT DATA
# ============================================================

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


# ============================================================
# LOAD HISTORY
# ============================================================

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


# ============================================================
# FETCH DATA
# ============================================================

try:
    df = load_current_data()
    history_df = load_history_data()

except Exception as e:
    st.error(
        "Unable to load wildfire data from Databricks."
    )
    st.code(str(e))
    st.stop()


# ============================================================
# DATA PREPARATION
# ============================================================

numeric_columns = [
    "latitude",
    "longitude",
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
]

for col in numeric_columns:
    if col in df.columns:
        df[col] = pd.to_numeric(
            df[col],
            errors="coerce",
        )

df["risk_change"] = (
    df["risk_change"]
    .fillna(0)
)

df["pipeline_run_timestamp"] = pd.to_datetime(
    df["pipeline_run_timestamp"],
    errors="coerce",
    utc=True,
)

history_df["risk_score"] = pd.to_numeric(
    history_df["risk_score"],
    errors="coerce",
)

history_df["pipeline_run_timestamp"] = pd.to_datetime(
    history_df["pipeline_run_timestamp"],
    errors="coerce",
    utc=True,
)

df = df.dropna(
    subset=[
        "latitude",
        "longitude",
        "risk_score",
    ]
)


# ============================================================
# HEADER
# ============================================================

title_col, refresh_col = st.columns(
    [4, 1.3]
)

with title_col:
    st.title(
        "🔥 Western LA Wildfire Situational Awareness"
    )

    st.caption(
        "Operational screening dashboard integrating "
        "wildfire hazard, historical fire exposure, "
        "and near-real-time weather."
    )


latest_refresh = (
    df["pipeline_run_timestamp"]
    .max()
)


with refresh_col:
    st.markdown("### Last Updated")

    if pd.notna(latest_refresh):

        local_refresh = latest_refresh.tz_convert(
            "America/Los_Angeles"
        )

        st.write(
            local_refresh.strftime(
                "%b %d, %Y  %I:%M %p"
            )
        )

    else:
        st.write("Unavailable")


# ============================================================
# KPI ROW
# ============================================================

high_count = df[
    df["risk_category"].isin(
        [
            "High",
            "Critical",
        ]
    )
].shape[0]

max_risk = (
    df["risk_score"]
    .max()
)

increasing_count = df[
    df["risk_change"] > 0
].shape[0]

largest_change = (
    df["risk_change"]
    .max()
)


k1, k2, k3, k4 = st.columns(4)

k1.metric(
    "High / Critical Zones",
    int(high_count),
)

k2.metric(
    "Highest Risk Score",
    f"{max_risk:.1f}",
)

k3.metric(
    "Zones Increasing",
    int(increasing_count),
)

k4.metric(
    "Largest Risk Increase",
    f"{largest_change:+.1f}",
)

st.divider()


# ============================================================
# CURRENT HIGHEST-RISK ZONE
# ============================================================

highest_row = (
    df.sort_values(
        by=[
            "risk_score",
            "risk_change",
        ],
        ascending=False,
    )
    .iloc[0]
)

highest_zone_id = highest_row["zone_id"]


# ============================================================
# MAP FILTER
# ============================================================

priority_mode = st.radio(
    "Map View",
    [
        "All Zones",
        "Priority Zones",
    ],
    horizontal=True,
)


if priority_mode == "Priority Zones":

    map_df = df[
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
            df["category_changed"] == True
        )
    ].copy()

    if map_df.empty:

        map_df = (
            df.sort_values(
                "risk_score",
                ascending=False,
            )
            .head(25)
            .copy()
        )

else:
    map_df = df.copy()


# ============================================================
# MAP STYLING
# ============================================================

color_map = {
    "Low": [46, 125, 50, 115],
    "Moderate": [255, 193, 7, 175],
    "High": [230, 81, 0, 225],
    "Critical": [183, 28, 28, 245],
}

radius_map = {
    "Low": 450,
    "Moderate": 650,
    "High": 1000,
    "Critical": 1300,
}

map_df["map_color"] = (
    map_df["risk_category"]
    .map(color_map)
)

map_df["map_radius"] = (
    map_df["risk_category"]
    .map(radius_map)
    .fillna(500)
)


# ============================================================
# MAP + TOP PRIORITY TABLE
# ============================================================

map_col, priority_col = st.columns(
    [2.25, 1]
)


with map_col:

    st.subheader(
        "Operational Risk Map"
    )

    st.markdown(
        """
<div class="risk-legend">
    <div class="legend-item">
        <span class="legend-dot" style="background:#2E7D32;"></span>
        Low
    </div>

    <div class="legend-item">
        <span class="legend-dot" style="background:#FFC107;"></span>
        Moderate
    </div>

    <div class="legend-item">
        <span class="legend-dot" style="background:#E65100;"></span>
        High
    </div>

    <div class="legend-item">
        <span class="legend-dot" style="background:#B71C1C;"></span>
        Critical
    </div>
</div>
""",
        unsafe_allow_html=True,
    )


    base_layer = pdk.Layer(
        "ScatterplotLayer",

        data=map_df,

        get_position=[
            "longitude",
            "latitude",
        ],

        get_fill_color="map_color",

        get_radius="map_radius",

        radius_min_pixels=3,

        radius_max_pixels=11,

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


    highest_map_df = df[
        df["zone_id"]
        == highest_zone_id
    ]


    highlight_layer = pdk.Layer(
        "ScatterplotLayer",

        data=highest_map_df,

        get_position=[
            "longitude",
            "latitude",
        ],

        get_fill_color=[
            255,
            255,
            255,
            0,
        ],

        get_line_color=[
            255,
            255,
            255,
            255,
        ],

        get_radius=1500,

        radius_min_pixels=11,

        radius_max_pixels=16,

        stroked=True,

        filled=False,

        line_width_min_pixels=3,

        pickable=False,
    )


    view_state = pdk.ViewState(
        latitude=34.115,
        longitude=-118.705,
        zoom=9.6,
        pitch=0,
        bearing=0,
    )


    tooltip = {
        "html": """
<div style="font-size:14px;">
    <b>{zone_label}</b>

    <hr style="margin:5px 0;border-color:#555;">

    Risk:
    <b>{risk_score}</b>
    ({risk_category})

    <br>

    Change:
    <b>{risk_change}</b>

    <br>

    Gust:
    <b>{wind_gust_mph} mph</b>

    <br>

    Humidity:
    <b>{relative_humidity_pct}%</b>

    <br>

    Temperature:
    <b>{temperature_f} °F</b>
</div>
""",

        "style": {
            "backgroundColor": "#111827",
            "color": "white",
            "borderRadius": "8px",
            "padding": "8px",
        },
    }


    deck = pdk.Deck(
        layers=[
            base_layer,
            highlight_layer,
        ],

        initial_view_state=view_state,

        tooltip=tooltip,

        map_style="light",
    )


    # NOTE:
    # No height argument here because the deployed
    # Streamlit version does not support it.
    st.pydeck_chart(
        deck,
        use_container_width=True,
    )

    st.caption(
        "White ring = current highest-risk zone."
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
                "risk_change": "Δ Risk",
                "wind_gust_mph": "Gust",
                "relative_humidity_pct": "RH %",
            }
        )
    )

    st.dataframe(
        top10,
        use_container_width=True,
        hide_index=True,
    )


st.divider()


# ============================================================
# ZONE INVESTIGATION
# ============================================================

st.subheader(
    "Zone Investigation"
)


zone_options = (
    df.sort_values(
        by=[
            "risk_score",
            "risk_change",
        ],
        ascending=False,
    )
    ["zone_label"]
    .dropna()
    .tolist()
)


selected_zone_label = st.selectbox(
    "Select a zone",
    zone_options,
    index=0,
)


selected = (
    df[
        df["zone_label"]
        == selected_zone_label
    ]
    .iloc[0]
)


st.markdown(
    f"""
<div class="status-box">
    <b>Investigating:</b>
    {selected_zone_label}

    &nbsp;&nbsp; | &nbsp;&nbsp;

    <b>Category:</b>
    {selected["risk_category"]}
</div>
""",
    unsafe_allow_html=True,
)


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


# ============================================================
# ZONE DETAILS + RISK DRIVERS
# ============================================================

detail_col, driver_col = st.columns(
    [1, 1.25]
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
        f"**Previous Risk:** {selected['previous_risk_score']}"
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

    if pd.notna(
        selected["historical_burned_acres"]
    ):

        st.write(
            f"**Historical Burned Acres:** "
            f"{selected['historical_burned_acres']:.0f}"
        )

    if pd.notna(
        selected["last_fire_year"]
    ):

        st.write(
            f"**Last Recorded Fire Year:** "
            f"{int(selected['last_fire_year'])}"
        )

    if pd.notna(
        selected["google_maps_url"]
    ):

        st.link_button(
            "📍 Open in Google Maps",
            selected[
                "google_maps_url"
            ],
            use_container_width=True,
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


# ============================================================
# HISTORICAL RISK TREND
# ============================================================

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
        "No historical snapshots are available "
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


st.divider()


# ============================================================
# OPERATIONAL ALERT PREVIEW
# ============================================================

st.subheader(
    "Operational Alert Preview"
)


alert_df = df[
    (
        df["risk_category"]
        .isin(
            [
                "High",
                "Critical",
            ]
        )
    )
    |
    (
        df["risk_change"]
        >= 10
    )
    |
    (
        df["category_changed"]
        == True
    )
]


if alert_df.empty:

    st.success(
        "No active High / Critical, major risk-increase, "
        "or category-change alerts."
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
            by=[
                "risk_score",
                "risk_change",
            ],
            ascending=False,
        )
        .rename(
            columns={
                "zone_label": "Zone",
                "risk_score": "Risk",
                "risk_category": "Category",
                "risk_change": "Δ Risk",
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


# ============================================================
# DISCLAIMER
# ============================================================

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
