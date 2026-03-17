"""Generate an interactive Folium map with school catchment areas."""

from pathlib import Path

import folium
import pandas as pd

from config import (
    DEFAULT_CATCHMENT_RADIUS_M,
    DEFAULT_ZOOM,
    LONDON_CENTER,
    RATING_COLORS,
)

OUTPUT_DIR = Path("output")


def _rating_color(rating):
    """Get fill and border colors for an Ofsted rating."""
    return RATING_COLORS.get(rating, RATING_COLORS["Not yet inspected"])


def _make_popup(row):
    """Create an HTML popup for a school marker."""
    rating = row["OfstedRating"]
    colors = _rating_color(rating)
    return f"""
    <div style="font-family: Arial, sans-serif; min-width: 200px;">
        <h4 style="margin: 0 0 5px 0;">{row['Name']}</h4>
        <p style="margin: 2px 0;">
            <strong>Ofsted:</strong>
            <span style="color: {colors['border']}; font-weight: bold;">{rating}</span>
        </p>
        <p style="margin: 2px 0;"><strong>Borough:</strong> {row['Borough']}</p>
        <p style="margin: 2px 0; font-size: 0.9em; color: #666;">{row.get('Address', '')}</p>
    </div>
    """


def _create_legend():
    """Create an HTML legend overlay for the map."""
    items = []
    for rating, colors in RATING_COLORS.items():
        items.append(
            f'<li style="margin: 3px 0;">'
            f'<span style="background:{colors["fill"]}; '
            f'width:14px; height:14px; display:inline-block; '
            f'border-radius:50%; margin-right:6px; vertical-align:middle;'
            f'border: 1px solid {colors["border"]};"></span>'
            f'{rating}</li>'
        )

    return """
    <div style="
        position: fixed;
        bottom: 30px;
        left: 10px;
        z-index: 1000;
        background: white;
        padding: 10px 14px;
        border-radius: 6px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.3);
        font-family: Arial, sans-serif;
        font-size: 13px;
    ">
        <strong>Ofsted Rating</strong>
        <ul style="list-style: none; padding: 0; margin: 5px 0 0 0;">
            {items}
        </ul>
    </div>
    """.format(items="\n".join(items))


def generate_map(schools_df, radius_m=DEFAULT_CATCHMENT_RADIUS_M, output_path=None):
    """Generate an interactive map with school catchment circles.

    Args:
        schools_df: DataFrame with columns Name, Latitude, Longitude, OfstedRating, Borough, Address
        radius_m: Catchment circle radius in meters
        output_path: Path for the output HTML file
    """
    OUTPUT_DIR.mkdir(exist_ok=True)
    if output_path is None:
        output_path = OUTPUT_DIR / "london_schools_map.html"

    print(f"Generating map with {len(schools_df)} schools (radius={radius_m}m)...")

    # Create base map
    m = folium.Map(
        location=LONDON_CENTER,
        zoom_start=DEFAULT_ZOOM,
        tiles="CartoDB positron",
    )

    # Create a FeatureGroup for each rating category (enables layer control)
    groups = {}
    for rating in RATING_COLORS:
        fg = folium.FeatureGroup(name=rating)
        groups[rating] = fg

    # Add schools to map
    for _, row in schools_df.iterrows():
        rating = row["OfstedRating"]
        colors = _rating_color(rating)
        fg = groups.get(rating, groups["Not yet inspected"])

        # Catchment circle
        folium.Circle(
            location=[row["Latitude"], row["Longitude"]],
            radius=radius_m,
            color=colors["border"],
            fill=True,
            fill_color=colors["fill"],
            fill_opacity=0.12,
            weight=1,
            popup=folium.Popup(_make_popup(row), max_width=300),
        ).add_to(fg)

        # School marker (small dot)
        folium.CircleMarker(
            location=[row["Latitude"], row["Longitude"]],
            radius=3,
            color=colors["border"],
            fill=True,
            fill_color=colors["fill"],
            fill_opacity=0.9,
            weight=1,
        ).add_to(fg)

    # Add all groups to map
    for fg in groups.values():
        fg.add_to(m)

    # Add layer control
    folium.LayerControl(collapsed=False).add_to(m)

    # Add legend
    legend_html = _create_legend()
    m.get_root().html.add_child(folium.Element(legend_html))

    # Save
    m.save(str(output_path))
    print(f"Map saved to {output_path}")
    return output_path


if __name__ == "__main__":
    data_path = Path("data/schools_processed.csv")
    if data_path.exists():
        df = pd.read_csv(data_path)
        generate_map(df)
    else:
        print(f"No processed data found at {data_path}. Run process_data.py first.")
