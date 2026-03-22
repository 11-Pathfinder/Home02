"""Configuration constants for London Schools Catchment Mapper."""

# Map defaults
LONDON_CENTER = (51.5074, -0.1278)
DEFAULT_ZOOM = 11
DEFAULT_CATCHMENT_RADIUS_M = 800  # ~0.5 miles

# Ofsted rating color scheme
RATING_COLORS = {
    "Outstanding": {"fill": "#2ecc71", "border": "#27ae60"},
    "Good": {"fill": "#3498db", "border": "#2980b9"},
    "Requires improvement": {"fill": "#e67e22", "border": "#d35400"},
    "Inadequate": {"fill": "#e74c3c", "border": "#c0392b"},
    "New framework": {"fill": "#9b59b6", "border": "#8e44ad"},  # Purple - 2025 report card system
    "Not yet inspected": {"fill": "#95a5a6", "border": "#7f8c8d"},
    "Independent": {"fill": "#8B4513", "border": "#5C2D0E"},
}

# All 33 London boroughs (32 boroughs + City of London)
LONDON_BOROUGHS = [
    "Barking and Dagenham",
    "Barnet",
    "Bexley",
    "Brent",
    "Bromley",
    "Camden",
    "City of London",
    "Croydon",
    "Ealing",
    "Enfield",
    "Greenwich",
    "Hackney",
    "Hammersmith and Fulham",
    "Haringey",
    "Harrow",
    "Havering",
    "Hillingdon",
    "Hounslow",
    "Islington",
    "Kensington and Chelsea",
    "Kingston upon Thames",
    "Lambeth",
    "Lewisham",
    "Merton",
    "Newham",
    "Redbridge",
    "Richmond upon Thames",
    "Southwark",
    "Sutton",
    "Tower Hamlets",
    "Waltham Forest",
    "Wandsworth",
    "Westminster",
]

# GIAS data download URL
GIAS_DOWNLOAD_URL = (
    "https://ea-edubase-api-prod.azurewebsites.net/edubase/downloads/public/edubasealldata.csv"
)

# Ofsted Management Information
OFSTED_MI_URL = (
    "https://www.gov.uk/government/statistical-data-sets/"
    "monthly-management-information-ofsteds-school-inspections-outcomes"
)
