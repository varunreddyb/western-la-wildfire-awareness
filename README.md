# 🔥 Western LA Wildfire Situational Awareness

A cloud-based wildfire situational-awareness platform that integrates wildfire hazard, historical wildfire exposure, and near-real-time weather data to identify, rank, and explain elevated operational risk across western Los Angeles County.

The project demonstrates an end-to-end data engineering and analytics workflow using Azure Databricks, ADLS Gen2, Delta Lake, Unity Catalog, scheduled pipelines, Streamlit, geospatial processing, and SMS alerting.

> **Project Scope:** This is a public-data prototype built for portfolio and learning purposes. It does not reproduce Southern California Edison proprietary wildfire-risk, circuit-risk, or Public Safety Power Shutoff decision models.

---

## Live Dashboard

**Public Streamlit Application**

https://western-la-wildfire-awareness-7txrrhsccuzioqfrrr6acf.streamlit.app/

The dashboard allows users to:

- View wildfire operational risk across western Los Angeles County
- Identify the highest-priority analysis zones
- Investigate individual locations
- Understand the factors contributing to each risk score
- Monitor changes across pipeline refreshes
- View operational alert conditions
- Subscribe to the prototype SMS alert workflow

---

## Business Problem

Wildfire risk is influenced by multiple factors that change at different speeds.

Some factors are relatively static:

- Wildfire hazard classification
- Historical wildfire exposure
- Historical burn frequency

Other factors change frequently:

- Wind speed
- Wind gusts
- Relative humidity
- Temperature

Looking at these datasets independently makes it difficult to quickly answer an operational question:

> **Among areas already exposed to wildfire hazard, which locations currently deserve the most operational attention because of the combination of underlying hazard, current weather, and historical wildfire exposure?**

This project combines those signals into a single explainable zone-level operational screening dataset.

---

## Solution Overview

Western Los Angeles County is divided into **227 approximately 2 km analysis zones**.

Each zone is enriched with:

- Wildfire hazard severity
- Historical fire frequency
- Historical burned acreage
- Most recent recorded fire year
- Current temperature
- Current relative humidity
- Current wind speed
- Current wind gusts
- Geographic location information

The system calculates an **Operational Wildfire Risk Index** for each zone and publishes the results to an interactive dashboard.

The workflow follows:

**Detect → Prioritize → Explain → Locate → Alert → Investigate**

---

# Architecture
<img width="877" height="581" alt="image" src="https://github.com/user-attachments/assets/969035bd-a30c-4a53-8228-e1d256dcc14e" />

## Technology Stack

### Cloud & Storage

- Microsoft Azure
- Azure Data Lake Storage Gen2
- Azure Databricks
- Unity Catalog
- Databricks SQL Warehouse

### Data Engineering

- Python
- PySpark
- Pandas
- GeoPandas
- Shapely
- Delta Lake
- Parquet
- REST APIs

### Analytics & Application

- Streamlit
- PyDeck
- Databricks SQL Connector
- OAuth Machine-to-Machine Authentication
- Google Maps links

### Automation & Alerting

- Databricks Workflows
- Scheduled six-hour refresh
- Databricks Secrets
- Twilio SMS
- Subscriber-driven alert workflow

---

## Data Sources

### Wildfire Hazard

Official Los Angeles County GIS wildfire hazard data is used to determine the underlying wildfire hazard classification of each zone.

Hazard levels are converted into analytical scores representing increasing wildfire exposure.

### Historical Wildfire Perimeters

California historical wildfire perimeter data is spatially intersected with the analysis grid.

For each zone, the pipeline derives:

- Historical fire count
- Historical burned acreage
- Most recent recorded fire year

### Current Weather

Current weather conditions are retrieved using the Open-Meteo API.

The current operational weather features include:

- Temperature
- Relative humidity
- Wind speed
- Wind gusts

Weather data is refreshed as part of the operational Databricks workflow.

---

## Analysis Zones

The study area focuses on western Los Angeles County, including areas around:

- Malibu
- Santa Monica Mountains
- Topanga
- Calabasas
- Agoura Hills
- Westlake Village
- Western Los Angeles

A regular geospatial grid is created using approximately **2 km cells**.

After filtering cells with insufficient land coverage, the final analytical dataset contains:

**227 analysis zones**

Each zone receives a unique identifier such as:

`ZONE_001`

`ZONE_002`

`ZONE_003`

These zones are analytical proxy areas created specifically for this prototype.

They are **not utility circuits, SCE operational boundaries, or PSPS decision units**.

---

## Operational Wildfire Risk Index

The model combines five explainable components.

| Risk Driver | Weight |
|---|---:|
| Wildfire Hazard | 40% |
| Wind Gust | 25% |
| Low Relative Humidity | 20% |
| Temperature | 10% |
| Historical Fire Exposure | 5% |

The final score ranges from:

**0 – 100**

Risk categories are:

| Score | Category |
|---|---|
| 0 – <25 | Low |
| 25 – <50 | Moderate |
| 50 – <75 | High |
| 75 – 100 | Critical |

The objective is not to predict whether a wildfire will occur.

Instead, the score provides an explainable way to prioritize zones where the combination of static exposure and current weather conditions may warrant additional operational attention.

---

## Explainability

Each zone stores the contribution of individual risk drivers:

- Hazard contribution
- Wind contribution
- Humidity contribution
- Temperature contribution
- Historical exposure contribution

This allows the dashboard to show **why** a particular zone receives its current risk score.

For example, two zones may both have Moderate risk while being driven by different combinations of hazard, wind, humidity, or historical exposure.

---

## Data Pipeline

The Databricks implementation is organized into modular notebooks.

```text
00_adls_connection_test
01_ingest_hazard
02_transform_hazard
03_ingest_fire_history
04_transform_fire_history
05_build_analysis_zones
06_build_static_features
07_ingest_weather
08_calculate_risk
09_publish_gold
10_data_quality
11_build_location_lookup
12_send_wildfire_alerts
```

The initial full pipeline constructs the static and operational datasets.

The recurring operational workflow focuses on:

```text
07_ingest_weather
        ↓
08_calculate_risk
        ↓
09_publish_gold
        ↓
10_data_quality
        ↓
12_send_wildfire_alerts
```

The workflow is scheduled to run every **six hours**.

---

## Medallion Architecture

### Bronze

Stores raw ingested data from external APIs.

Examples:

- Raw wildfire hazard features
- Raw fire perimeter data
- Raw weather responses

### Silver

Stores cleaned and transformed analytical datasets.

Examples:

- Fire hazard features
- Historical wildfire exposure
- Analysis-zone geometry
- Static zone features
- Current weather
- Zone location lookup
- Current calculated risk

### Gold

Stores application-ready datasets.

Primary outputs:

`wildfire_gold_current`

Contains the latest risk state for all zones.

`wildfire_gold_history`

Stores historical snapshots used for trend analysis.

---

## Data Quality

The pipeline includes automated validation before operational results are considered complete.

Checks include:

- Expected zone count
- Unique zone IDs
- Duplicate detection
- Missing weather values
- Humidity validity
- Negative wind values
- Missing risk scores
- Risk score range validation
- Risk category validation

This provides a basic operational quality gate between data processing and downstream consumption.

---

## Dashboard

The Streamlit dashboard provides several operational views.

### Executive KPIs

- High / Critical Zones
- Highest Risk Score
- Zones Increasing
- Largest Risk Increase
- Data Freshness

### Zone Investigation

Users can select an individual zone and investigate:

- Current risk score
- Previous risk
- Risk change
- Wind gust
- Humidity
- Temperature
- Hazard score
- Historical wildfire exposure
- Location
- Risk drivers

### Operational Risk Map

The map displays the geographic distribution of risk.

Risk categories are represented as:

🟢 Low  
🟡 Moderate  
🟠 High  
🔴 Critical

The selected investigation zone is highlighted separately.

### Top Priority Zones

Zones are ranked using current risk score and recent risk change to help identify the areas deserving the most immediate attention.

### Risk Trend

Historical Gold snapshots allow the application to display changes in risk across pipeline refreshes.

A stable score does not indicate that the pipeline has stopped refreshing.

The model uses threshold-based weather factors, so small changes in weather may not change the final risk score until a scoring threshold is crossed.

The dashboard therefore also displays **Data Freshness** and the latest raw weather conditions.

---

## Alerting Workflow

The platform includes an SMS alerting workflow.

Users can register a mobile number through the Streamlit interface.

Subscriber records are stored in a Databricks Delta table.

The alert notebook evaluates the latest Gold dataset and identifies zones that meet defined alert conditions.

Alert conditions include:

- High risk
- Critical risk
- Major increase in risk score
- Risk-category change

When alert conditions are detected, the workflow can send notifications through Twilio.

The subscriber list is deduplicated before sending notifications to prevent duplicate delivery.

---

## Location Intelligence

Each analysis zone is enriched with:

- Latitude
- Longitude
- Human-readable location
- Google Maps URL

Representative points are generated from zone geometries and reverse-geocoded to provide more understandable location labels.

This allows dashboard users to move directly from an analytical zone to geographic investigation.

---

## Automation

The operational workflow is automated using Databricks Workflows.

The scheduled pipeline:

1. Retrieves updated weather
2. Calculates current wildfire risk
3. Publishes the latest Gold dataset
4. Stores a historical snapshot
5. Executes data-quality checks
6. Evaluates operational alert conditions

The workflow runs every **six hours**.

---

## Security

The public Streamlit application does not contain Databricks credentials directly in source code.

Authentication uses a Databricks-managed service principal with OAuth machine-to-machine authentication.

Secrets are stored using Streamlit Cloud secrets and Databricks secret scopes.

Sensitive credentials are excluded from GitHub.

Examples include:

- Databricks OAuth client secrets
- Twilio authentication tokens
- Azure credentials
- Personal access tokens

---

## Repository Structure

```text
western-la-wildfire-awareness/
│
├── apps/
│   └── western-la-wildfire-awareness/
│       ├── app.py
│       ├── app.yaml
│       └── requirements.txt
│
├── notebooks/
│   ├── 00_adls_connection_test.py
│   ├── 01_ingest_hazard.py
│   ├── 02_transform_hazard.py
│   ├── 03_ingest_fire_history.py
│   ├── 04_transform_fire_history.py
│   ├── 05_build_analysis_zones.py
│   ├── 06_build_static_features.py
│   ├── 07_ingest_weather.py
│   ├── 08_calculate_risk.py
│   ├── 09_publish_gold.py
│   ├── 10_data_quality.py
│   ├── 11_build_location_lookup.py
│   └── 12_send_wildfire_alerts.py
│
├── sql/
│   ├── create_external_tables.sql
│   └── subscriber_table.sql
│
├── docs/
│   ├── architecture.png
│   ├── dashboard-main.png
│   ├── zone-investigation.png
│   └── alerting.png
│
├── README.md
├── .gitignore
└── LICENSE
```

---

## Key Engineering Challenges

Several practical engineering problems were addressed during implementation:

- Processing geospatial wildfire perimeter data
- Resolving geometry topology errors
- Converting between geographic and projected coordinate systems
- Building repeatable spatial analysis zones
- Integrating multiple external APIs
- Maintaining current and historical Gold datasets
- Implementing idempotent pipeline logic
- Automating scheduled refreshes
- Configuring Unity Catalog external locations
- Connecting an external Streamlit application securely to Databricks SQL
- Configuring OAuth machine-to-machine authentication
- Implementing subscriber-driven SMS alerting
- Maintaining data-quality controls

---

## What This Project Demonstrates

This project demonstrates the ability to move from an ambiguous operational problem to a working analytical product.

It covers the full lifecycle:

**Raw Data → Cloud Storage → Data Engineering → Geospatial Transformation → Risk Modeling → Data Quality → Automation → Visualization → Alerting**

The goal was not simply to build a dashboard.

The goal was to demonstrate how public wildfire and weather information can be transformed into an automated, explainable operational situational-awareness workflow.

---

## Future Enhancements

Potential future improvements include:

- Finer-grained weather data
- Forecast weather integration
- Red Flag Warning integration
- National Weather Service alert integration
- Vegetation and fuel-condition indicators
- Terrain and slope features
- Fire-weather indices
- Improved subscriber verification and opt-out management
- Notification throttling
- Additional geographic drill-down
- Expanded historical trend analysis
- More advanced geospatial visualization
- Infrastructure-as-code deployment

---

## Disclaimer

This project is an independent public-data prototype.

It is not affiliated with, endorsed by, or developed for Southern California Edison.

The Operational Wildfire Risk Index is an analytical screening measure and should not be interpreted as:

- A wildfire prediction
- An ignition probability
- A PSPS recommendation
- A utility circuit-risk score
- An emergency warning system

Actual wildfire and utility operational decisions require substantially more data, domain expertise, validated models, operational controls, and regulatory processes.
