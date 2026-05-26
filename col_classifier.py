import marimo

__generated_with = "0.23.3"
app = marimo.App(
    width="full",
    app_title="Col Compare",
    auto_download=["ipynb"],
)

with app.setup(hide_code=True):
    import marimo as mo
    import os
    import requests
    from dotenv import load_dotenv

    load_dotenv()
    ACCESS_TOKEN = os.getenv("STRAVA_ACCESS_TOKEN")
    import json
    from types import SimpleNamespace as Namespace


@app.cell(hide_code=True)
def intro():
    mo.md(r"""
    #ColCompare
    ## Overview
    Take a Strava Segment and analyse it in order to classify it under a number of numerical characteristics.

    These numerical values can then be used to:
    - pass into a neural network and make predictions, i.e. given a certain performance on a segment with these characteristics what could I set as a reasonable expectation on another segment.
    - passed into a vector database and then used to find other climbs of similar nature.
    """)
    return


@app.cell(hide_code=True)
def get_segment_options():
    def get_athletes_segments(access_token, page=1) -> dict:
        url = f"https://www.strava.com/api/v3/segments/starred?page={page}&per_page=30"
        headers = {"Authorization": f"Bearer {access_token}"}

        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            print(f"Error fetching data: {response.status_code}\n{response.text}")
            return None
        list_of_segments = json.loads(
            response.content, object_hook=lambda d: Namespace(**d)
        )
        return dict([(l.name, l.id) for l in list_of_segments])

    segment_options = get_athletes_segments(access_token=ACCESS_TOKEN)
    dropdown = mo.ui.dropdown(
        options=segment_options,
        label="Choose a segment from your starred",
        searchable=True,
        allow_select_none=False,
        value=next(iter(segment_options)),
    )
    dropdown
    return (dropdown,)


@app.cell(hide_code=True)
def choose_segment(dropdown):
    segment_id = dropdown.value

    def get_segment_data(segment_id, access_token):
        url = f"https://www.strava.com/api/v3/segments/{segment_id}"
        headers = {"Authorization": f"Bearer {access_token}"}

        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            print(f"Error fetching data: {response.status_code}\n{response.text}")
            return None

        return json.loads(response.content, object_hook=lambda d: Namespace(**d))

    segment = get_segment_data(segment_id, ACCESS_TOKEN)

    segment_name = segment.name
    return segment, segment_id, segment_name


@app.cell(hide_code=True)
def default_data_md(segment, segment_name):
    mo.md(rf"""
    ## Strava Provided Values

    We can gain some insight into the nature of our segment from the data provided to us by the api directly, things like:

    | <!-- --> | <!-- --> |
    | :-- | --: |
    | Segment name | {segment_name} |
    | Climb category | {segment.climb_category} |
    | Distance | {(segment.distance / 1000):.2f}km |
    | Average Grade | {segment.average_grade}% |
    | Max grade | {segment.maximum_grade}% |
    | Total elevation | {segment.total_elevation_gain:.2f}m |
    | Max altitude| {segment.elevation_high:.0f}m |
    | KOM time | {segment.xoms.overall} |
    """)
    return


@app.cell(hide_code=True)
def calculate_directness_cell(segment):
    def calculate_directness(segment):
        gain = (
            segment.total_elevation_gain
            if segment.total_elevation_gain != 0
            else segment.elevation_high - segment.elevation_low
        )
        return (segment.elevation_high - segment.elevation_low) / gain
    directness = calculate_directness(segment)
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    The Strava API also provides us with a Polyline which we can use to view our segment on a map
    """)
    return


@app.cell(hide_code=True)
def display_segment_map(segment):
    import folium
    import polyline

    coordinates = polyline.decode(segment.map.polyline, 5)

    south = min(coordinates, key=lambda t: t[0])
    west = min(coordinates, key=lambda t: t[1])
    north = max(coordinates, key=lambda t: t[0])
    east = max(coordinates, key=lambda t: t[1])

    bounds = [[south, west], [north, east]]
    display_map = folium.Map(
        location=(segment.start_latlng[0], segment.start_latlng[1]),
        scrollWheelZoom=False,
        dragging=False,
    )
    folium.TileLayer(
        tiles="https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        attr="&copy; <a href='https://www.openstreetmap.org/copyright'>OpenStreetMap</a> contributors",
        referrer_policy="strict-origin",
    ).add_to(display_map)
    folium.PolyLine(
        locations=coordinates,
        color="orange",
        weight=8,
        opacity=1,
        smooth_factor=0,
    ).add_to(display_map)
    folium.Marker(
        location=[coordinates[0][0], coordinates[0][1]],
        popup="Start",
        icon=folium.Icon(color="green"),
    ).add_to(display_map)
    folium.Marker(
        location=[coordinates[-1][0], coordinates[-1][1]],
        popup="End",
        icon=folium.Icon(color="red"),
    ).add_to(display_map)
    display_map.fit_bounds(bounds)
    display_map
    return


@app.cell(hide_code=True)
def get_segment_elevation_data(segment_id):
    def get_segment_elevation(segment_id, access_token):
        """
        Retrieve the altitude and distance streams for the given Strava segment.

        Parameters:
            segment_id (str): The ID of the Strava segment.
            access_token (str): Your Strava API OAuth access token.

        Returns:
            tuple: (distance_data, altitude_data) as lists, or (None, None) if the request fails.
        """
        url = f"https://www.strava.com/api/v3/segments/{segment_id}/streams"
        params = {
            "keys": "altitude,distance",
            "resolution": "low",  # Options: 'low', 'medium', or 'high'
        }
        headers = {"Authorization": f"Bearer {access_token}"}

        response = requests.get(url, headers=headers, params=params, timeout=10)
        if response.status_code != 200:
            print(f"Error fetching data: {response.status_code}\n{response.text}")
            return None, None

        streams = response.json()
        altitude_data = None
        distance_data = None

        for stream in streams:
            if stream.get("type") == "altitude":
                altitude_data = stream.get("data")
            elif stream.get("type") == "distance":
                distance_data = stream.get("data")

        if altitude_data is None:
            print("Altitude data not found in the response.")
        if distance_data is None:
            print("Distance data not found in the response.")

        return distance_data, altitude_data

    dist_axis, ele_axis = get_segment_elevation(segment_id, ACCESS_TOKEN)
    return dist_axis, ele_axis


@app.cell(hide_code=True)
def elevation_data_md():
    mo.md(r"""
    ## Elevation data
    To do any meaningful analysis of a climb we need to know its elevation profile.

    To retrieve its elevation data we use the strava api's streams endpoint on the segment. I have used [this project](https://github.com/ekalvi/strava-segment-elevation) on Github by [ekalvi](https://github.com/ekalvi) as a guide for how to retrieve this information.

    Let's take a look in the graph below at the elevation profile of our chosen segment.
    """)
    return


@app.cell(hide_code=True)
def elevation_profile_plot(dist_axis, ele_axis, segment_name):
    import matplotlib.pyplot as plt

    plt.plot(dist_axis, ele_axis)
    plt.title(f"Elevation Profile of {segment_name}")
    plt.xlabel("Distance")
    plt.ylabel("Elevation")
    plt.grid(True)
    plt.gca()
    return (plt,)


@app.cell(hide_code=True)
def gradient_md():
    mo.md(r"""
    ## Gradient
    We can see with our eyes as the elevation changes up our down how that changes the gradient, but lets put it into perspective and plot it on a graph
    """)
    return


@app.cell(hide_code=True)
def gradient_plot(dist_axis, ele_axis, plt, segment_name):
    rises = [j - i for i, j in zip(ele_axis[:-1], ele_axis[1:])]
    runs = [j - i for i, j in zip(dist_axis[:-1], dist_axis[1:])]
    gradient = [(rise / run) * 100 for rise, run in zip(rises, runs)]
    midpoints = [(a + b) / 2 for a, b in zip(dist_axis[:-1], dist_axis[1:])]

    plt.plot(midpoints, gradient)
    plt.title(f"Gradient Profile of {segment_name}")
    plt.xlabel("Distance (m)")
    plt.ylabel("Gradient (%)")
    plt.grid(True)
    plt.gca()
    return


if __name__ == "__main__":
    app.run()
