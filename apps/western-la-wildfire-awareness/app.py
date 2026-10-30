import pandas as pd
import pydeck as pdk
import streamlit as st

from databricks import sql
from databricks.sdk.core import Config, oauth_service_principal


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Western LA Wildfire Situational Awareness",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ============================================================
# DATABRICKS TABLES
# ============================================================

CURRENT_TABLE = (
    "dbw_sce_wildfire_dev.default.wildfire_gold_current"
)

HISTORY_TABLE = (
    "dbw_sce_wildfire_dev.default.wildfire_gold_history"
)

SUBSCRIBER_TABLE = (
    "dbw_sce_wildfire_dev.default.wildfire_alert_subscribers"
)


# ============================================================
# DATABRICKS OAUTH CONNECTION
# ============================================================

def get_connection():

    server_hostname = st.secrets[
        "DATABRICKS_SERVER_HOSTNAME"
    ]

    http_path = st.secrets[
        "DATABRICKS_HTTP_PATH"
    ]

    client_id = st.secrets[
        "DATABRICKS_CLIENT_ID"
    ]

    client_secret = st.secrets[
        "DATABRICKS_CLIENT_SECRET"
    ]

    def credential_provider():

        config = Config(
            host=f"https://{server_hostname}",
            client_id=client_id,
            client_secret=client_secret,
        )

        return oauth_service_principal(
            config
        )

    return sql.connect(
        server_hostname=server_hostname,
        http_path=http_path,
        credentials_provider=credential_provider,
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
# LOAD HISTORY DATA
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
).copy()


df["zone_label"] = df["zone_label"].fillna(
    df["zone_id"]
)


df["location_name"] = df["location_name"].fillna(
    "Western Los Angeles County"
)


# ============================================================
# HEADER
# ============================================================

header_left, header_right = st.columns(
    [4, 1.2]
)


with header_left:

    st.title(
        "🔥 Western LA Wildfire Situational Awareness"
    )

    st.caption(
        "Operational screening dashboard integrating wildfire "
        "hazard, historical fire exposure, and near-real-time weather."
    )


latest_refresh = (
    df["pipeline_run_timestamp"]
    .max()
)


# ============================================================
# DATA FRESHNESS
# ============================================================

if pd.notna(latest_refresh):

    now_utc = pd.Timestamp.now(
        tz="UTC"
    )

    refresh_age = (
        now_utc - latest_refresh
    )

    refresh_hours = (
        refresh_age.total_seconds()
        / 3600
    )

else:

    refresh_hours = None


with header_right:

    st.write(
        "**Last Updated**"
    )

    if pd.notna(latest_refresh):

        local_refresh = (
            latest_refresh
            .tz_convert(
                "America/Los_Angeles"
            )
        )

        st.write(
            local_refresh.strftime(
                "%b %d, %Y · %I:%M %p"
            )
        )

    else:

        st.write(
            "Unavailable"
        )


# ============================================================
# KPI ROW
# ============================================================

high_critical_count = df[
    df["risk_category"].isin(
        [
            "High",
            "Critical",
        ]
    )
].shape[0]


highest_risk = (
    df["risk_score"]
    .max()
)


zones_increasing = df[
    df["risk_change"] > 0
].shape[0]


largest_increase = (
    df["risk_change"]
    .max()
)


if refresh_hours is not None:

    if refresh_hours < 1:

        freshness_text = "< 1 hr"

    else:

        freshness_text = (
            f"{refresh_hours:.1f} hrs"
        )

else:

    freshness_text = "Unavailable"


k1, k2, k3, k4, k5 = st.columns(5)


k1.metric(
    "High / Critical Zones",
    int(high_critical_count),
)


k2.metric(
    "Highest Risk Score",
    f"{highest_risk:.1f}",
)


k3.metric(
    "Zones Increasing",
    int(zones_increasing),
)


k4.metric(
    "Largest Risk Increase",
    f"{largest_increase:+.1f}",
)


k5.metric(
    "Data Freshness",
    freshness_text,
)


st.divider()


# ============================================================
# RANK ZONES
# ============================================================

ranked_df = df.sort_values(
    by=[
        "risk_score",
        "risk_change",
    ],
    ascending=False,
).copy()


# ============================================================
# ZONE SELECTION
# ============================================================

st.subheader(
    "Zone Investigation"
)


zone_options = (
    ranked_df["zone_label"]
    .dropna()
    .tolist()
)


selected_zone_label = st.selectbox(
    "Select a zone to investigate",
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


selected_zone_id = selected[
    "zone_id"
]


# ============================================================
# SELECTED ZONE STATUS
# ============================================================

category = selected[
    "risk_category"
]


if category == "Critical":

    st.error(
        f"🔴 Investigating: {selected_zone_label} "
        f"— Critical Risk"
    )


elif category == "High":

    st.warning(
        f"🟠 Investigating: {selected_zone_label} "
        f"— High Risk"
    )


elif category == "Moderate":

    st.info(
        f"🟡 Investigating: {selected_zone_label} "
        f"— Moderate Risk"
    )


else:

    st.success(
        f"🟢 Investigating: {selected_zone_label} "
        f"— Low Risk"
    )


# ============================================================
# MAP VIEW CONTROL
# ============================================================

st.caption(
    "MAP VIEW"
)


map_view = st.radio(
    "Map View",
    [
        "All Zones",
        "Priority Zones",
    ],
    horizontal=True,
    label_visibility="collapsed",
)


if map_view == "Priority Zones":

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
            ranked_df
            .head(25)
            .copy()
        )


else:

    map_df = df.copy()


# ============================================================
# MAP COLOR STYLE
# ============================================================

def map_style(category):

    if category == "Critical":

        return pd.Series(
            [
                183,
                28,
                28,
                235,
                1100,
            ]
        )


    elif category == "High":

        return pd.Series(
            [
                230,
                81,
                0,
                225,
                900,
            ]
        )


    elif category == "Moderate":

        return pd.Series(
            [
                255,
                193,
                7,
                200,
                650,
            ]
        )


    else:

        return pd.Series(
            [
                46,
                125,
                50,
                155,
                450,
            ]
        )


map_df[
    [
        "color_r",
        "color_g",
        "color_b",
        "color_a",
        "marker_radius",
    ]
] = map_df[
    "risk_category"
].apply(
    map_style
)


for col in [
    "color_r",
    "color_g",
    "color_b",
    "color_a",
    "marker_radius",
]:

    map_df[col] = pd.to_numeric(
        map_df[col],
        errors="coerce",
    )


# ============================================================
# MAP + PRIORITY TABLE
# ============================================================

map_col, table_col = st.columns(
    [2.1, 1]
)


# ============================================================
# MAP
# ============================================================

with map_col:

    st.subheader(
        "Operational Risk Map"
    )


    l1, l2, l3, l4 = st.columns(4)

    l1.markdown(
        "🟢 **Low**"
    )

    l2.markdown(
        "🟡 **Moderate**"
    )

    l3.markdown(
        "🟠 **High**"
    )

    l4.markdown(
        "🔴 **Critical**"
    )


    risk_layer = pdk.Layer(
        "ScatterplotLayer",

        data=map_df,

        get_position=[
            "longitude",
            "latitude",
        ],

        get_fill_color=[
            "color_r",
            "color_g",
            "color_b",
            "color_a",
        ],

        get_radius="marker_radius",

        radius_min_pixels=5,

        radius_max_pixels=14,

        stroked=True,

        get_line_color=[
            40,
            40,
            40,
            180,
        ],

        line_width_min_pixels=1,

        pickable=True,

        auto_highlight=True,
    )


    selected_map_df = df[
        df["zone_id"]
        == selected_zone_id
    ].copy()


    highlight_layer = pdk.Layer(
        "ScatterplotLayer",

        data=selected_map_df,

        get_position=[
            "longitude",
            "latitude",
        ],

        get_radius=1400,

        radius_min_pixels=13,

        radius_max_pixels=20,

        filled=False,

        stroked=True,

        get_line_color=[
            0,
            0,
            0,
            255,
        ],

        line_width_min_pixels=4,

        pickable=False,
    )


    view_state = pdk.ViewState(
        latitude=34.105,
        longitude=-118.705,
        zoom=9.8,
        pitch=0,
        bearing=0,
    )


    tooltip = {
        "html": (
            "<b>{zone_label}</b><br/>"
            "Risk: <b>{risk_score}</b> ({risk_category})<br/>"
            "Change: <b>{risk_change}</b><br/>"
            "Wind gust: <b>{wind_gust_mph} mph</b><br/>"
            "Humidity: <b>{relative_humidity_pct}%</b><br/>"
            "Temperature: <b>{temperature_f} °F</b>"
        )
    }


    deck = pdk.Deck(
        layers=[
            risk_layer,
            highlight_layer,
        ],

        initial_view_state=view_state,

        tooltip=tooltip,

        map_style="light",
    )


    st.pydeck_chart(
        deck,
        use_container_width=True,
    )


    st.caption(
        "Black ring indicates the selected investigation zone. "
        "Hover over any marker for current conditions."
    )


# ============================================================
# TOP PRIORITY TABLE
# ============================================================

with table_col:

    st.subheader(
        "Top Priority Zones"
    )


    top10 = (
        ranked_df
        .head(10)
        [
            [
                "location_name",
                "zone_id",
                "risk_score",
                "risk_category",
                "risk_change",
                "wind_gust_mph",
                "relative_humidity_pct",
            ]
        ]
        .copy()
    )


    top10["Zone"] = (
        top10["location_name"]
        .astype(str)
        + " — "
        + top10["zone_id"]
        .astype(str)
    )


    top10["Risk"] = (
        top10["risk_score"]
        .round(1)
    )


    top10["Δ Risk"] = (
        top10["risk_change"]
        .round(1)
    )


    top10["Gust"] = (
        top10["wind_gust_mph"]
        .round(1)
    )


    top10["Humidity"] = (
        top10[
            "relative_humidity_pct"
        ]
        .round(0)
        .astype("Int64")
    )


    top10["Category"] = (
        top10["risk_category"]
    )


    top10_display = top10[
        [
            "Zone",
            "Risk",
            "Category",
            "Δ Risk",
            "Gust",
            "Humidity",
        ]
    ]


    st.caption(
        "Highest-priority zones ranked by current risk score."
    )


    st.dataframe(
        top10_display,
        use_container_width=True,
        hide_index=True,

        column_config={

            "Zone":
                st.column_config.TextColumn(
                    "Zone",
                    width="large",
                ),

            "Risk":
                st.column_config.NumberColumn(
                    "Risk",
                    format="%.1f",
                    width="small",
                ),

            "Category":
                st.column_config.TextColumn(
                    "Category",
                    width="small",
                ),

            "Δ Risk":
                st.column_config.NumberColumn(
                    "Δ Risk",
                    format="%+.1f",
                    width="small",
                ),

            "Gust":
                st.column_config.NumberColumn(
                    "Gust",
                    format="%.1f mph",
                    width="small",
                ),

            "Humidity":
                st.column_config.NumberColumn(
                    "RH",
                    format="%d%%",
                    width="small",
                ),
        },
    )


st.divider()


# ============================================================
# SELECTED ZONE DETAILS
# ============================================================

st.subheader(
    "Selected Zone Details"
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
# CONTEXT + RISK DRIVERS
# ============================================================

context_col, driver_col = st.columns(
    [1, 1.35]
)


with context_col:

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


    if pd.notna(
        selected[
            "previous_risk_score"
        ]
    ):

        st.write(
            f"**Previous Risk:** "
            f"{selected['previous_risk_score']:.1f}"
        )


    if pd.notna(
        selected[
            "previous_category"
        ]
    ):

        st.write(
            f"**Previous Category:** "
            f"{selected['previous_category']}"
        )


    if pd.notna(
        selected[
            "hazard_score"
        ]
    ):

        st.write(
            f"**Hazard Score:** "
            f"{selected['hazard_score']:.2f}"
        )


    if pd.notna(
        selected[
            "historical_fire_count"
        ]
    ):

        st.write(
            f"**Historical Fire Count:** "
            f"{int(selected['historical_fire_count'])}"
        )


    if pd.notna(
        selected[
            "historical_burned_acres"
        ]
    ):

        st.write(
            f"**Historical Burned Acres:** "
            f"{selected['historical_burned_acres']:,.0f}"
        )


    if pd.notna(
        selected[
            "last_fire_year"
        ]
    ):

        st.write(
            f"**Last Recorded Fire Year:** "
            f"{int(selected['last_fire_year'])}"
        )


    if pd.notna(
        selected[
            "google_maps_url"
        ]
    ):

        st.link_button(
            "📍 Open Zone in Google Maps",
            selected[
                "google_maps_url"
            ],
            use_container_width=True,
        )


# ============================================================
# RISK DRIVERS
# ============================================================

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


    driver_df[
        "Contribution"
    ] = pd.to_numeric(
        driver_df[
            "Contribution"
        ],
        errors="coerce",
    ).fillna(0)


    st.bar_chart(
        driver_df,
        x="Driver",
        y="Contribution",
        use_container_width=True,
    )


st.divider()


# ============================================================
# RISK TREND
# ============================================================

st.subheader(
    "Risk Trend"
)


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
        "No historical snapshots are available for this zone."
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


# ============================================================
# OPERATIONAL ALERT PREVIEW
# ============================================================

st.divider()


st.subheader(
    "Operational Alert Preview"
)


alert_df = df[
    (
        df[
            "risk_category"
        ].isin(
            [
                "High",
                "Critical",
            ]
        )
    )
    |
    (
        df[
            "risk_change"
        ] >= 10
    )
    |
    (
        df[
            "category_changed"
        ] == True
    )
].copy()


if alert_df.empty:

    st.success(
        "✅ No active High/Critical, major risk-increase, "
        "or category-change alerts."
    )


else:

    alert_df = alert_df.sort_values(
        by=[
            "risk_score",
            "risk_change",
        ],
        ascending=False,
    )


    st.warning(
        f"⚠️ {len(alert_df)} zone(s) currently meet "
        f"the operational alert criteria."
    )


    alert_display = alert_df[
        [
            "zone_label",
            "risk_score",
            "risk_category",
            "risk_change",
            "wind_gust_mph",
            "relative_humidity_pct",
        ]
    ].rename(
        columns={
            "zone_label": "Zone",
            "risk_score": "Risk",
            "risk_category": "Category",
            "risk_change": "Δ Risk",
            "wind_gust_mph": "Gust",
            "relative_humidity_pct": "RH %",
        }
    )


    st.dataframe(
        alert_display,
        use_container_width=True,
        hide_index=True,
    )


# ============================================================
# WILDFIRE ALERT SUBSCRIPTION
# ============================================================

st.divider()


st.subheader(
    "📱 Wildfire Alert Subscription"
)


st.caption(
    "Enter a mobile number to receive wildfire alerts when a zone "
    "becomes High/Critical, increases significantly, or changes risk category."
)


phone_number = st.text_input(
    "Mobile Number",
    placeholder="+17145551234",
)


agree = st.checkbox(
    "I agree to receive wildfire situational-awareness SMS alerts."
)


if st.button(
    "Subscribe to Alerts",
    use_container_width=True,
):

    cleaned_phone = (
        phone_number
        .strip()
        .replace(" ", "")
        .replace("-", "")
        .replace("(", "")
        .replace(")", "")
    )


    if not cleaned_phone:

        st.warning(
            "Enter a mobile number."
        )


    elif not cleaned_phone.startswith("+"):

        st.warning(
            "Use international format, for example +17145551234."
        )


    elif not cleaned_phone[1:].isdigit():

        st.warning(
            "Enter a valid phone number using digits only after the + sign."
        )


    elif len(cleaned_phone) < 10 or len(cleaned_phone) > 16:

        st.warning(
            "Enter a valid international mobile number."
        )


    elif not agree:

        st.warning(
            "Please confirm that you want to receive alerts."
        )


    else:

        safe_phone = (
            cleaned_phone
            .replace("'", "")
        )


        insert_query = f"""
        INSERT INTO {SUBSCRIBER_TABLE}
        (
            phone_number,
            active,
            created_at
        )
        VALUES
        (
            '{safe_phone}',
            TRUE,
            current_timestamp()
        )
        """


        try:

            with get_connection() as conn:

                with conn.cursor() as cursor:

                    cursor.execute(
                        insert_query
                    )


            masked_phone = (
                "*" * max(
                    len(cleaned_phone) - 4,
                    0
                )
                + cleaned_phone[-4:]
            )


            st.success(
                f"✅ Alert subscription activated for {masked_phone}."
            )


        except Exception as e:

            st.error(
                "Unable to save the alert subscription."
            )

            st.code(
                str(e)
            )


# ============================================================
# ABOUT THIS PROTOTYPE
# ============================================================

st.divider()


st.subheader(
    "About this Prototype"
)


st.write(
    "This public-data prototype divides western Los Angeles County into "
    "227 analysis zones and combines wildfire hazard, historical fire "
    "exposure, and near-real-time weather into an explainable "
    "Operational Wildfire Risk Index."
)


st.write(
    "The workflow supports operational situational awareness by helping "
    "identify changing conditions, prioritize zones, explain the main "
    "risk drivers, locate affected areas, and trigger alert workflows."
)


st.caption(
    "Analysis zones are 2 km proxy areas created for this prototype "
    "and are not SCE circuits, service territories, or proprietary "
    "operational boundaries."
)


# ============================================================
# DISCLAIMER
# ============================================================

st.divider()


st.caption(
    "Public-data prototype demonstrating how geospatial wildfire "
    "hazard, historical wildfire exposure, and near-real-time weather "
    "can be integrated into a zone-level situational-awareness dataset. "
    "The Operational Wildfire Risk Index is an analytical screening "
    "measure and is not intended to reproduce SCE proprietary wildfire-risk "
    "or PSPS decision models."
)
