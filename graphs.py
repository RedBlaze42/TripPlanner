import api_gites, datastores
import json, os, re
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
from plotly.offline import plot
import plotly.graph_objs as gos
from tqdm import tqdm

mapbox_key = None
if os.path.exists("config.json"):
    with open("config.json") as f:
        data = json.load(f)
        if "mapbox_key" in data.keys():
            mapbox_key = data["mapbox_key"]

colors =  ["lime", "aqua", "yellow", "fuchsia", "darkorange", "purple", "tomato", "peru", "goldenrod", "crimson", "darkslategrey", "greenyellow"]

default_mapbox_layout = go.Layout(
    hovermode = 'closest',
    mapbox = dict(
        accesstoken = mapbox_key,
        bearing = 0,
        center = dict(
            lat = 47.1,
            lon = 2
        ),
        pitch = 0,
        zoom = 5.7,
        style = "streets" if mapbox_key is not None else "open-street-map"
    )
)

def nb_gites_data(travelers, gites_args = None, to_datetime = None):
    from_datetime = datetime.now()
    
    if to_datetime is None:
        to_datetime = from_datetime + timedelta(days = 31*7)

    to_datetime = to_datetime.replace(month = to_datetime.month + 1, day = 2)

    output = dict()
    checkin = from_datetime
    checkout = checkin + timedelta(days = 1)
    progress_bar = tqdm(total = int((to_datetime-from_datetime).total_seconds()//86400))
    while checkout < to_datetime:
        output[checkin.isoformat()] = len(api_gites.GitesDeFrance(checkin, checkout, travelers, **gites_args))
        checkin = checkout
        checkout += timedelta(days = 1)
        progress_bar.update(1)
    progress_bar.close()
    return output

def nb_gites(to_datetime = None, travelers = 14, input_data = None):
    if input_data is None:
        input_data = nb_gites_data(travelers, to_datetime = to_datetime)
    
    input_data = {datetime.fromisoformat(date): value for date, value in input_data.items()}
    trace = {
        "type": "heatmap",
        "colorbar": {"title": "lodges"},
        "hoverinfo": "text",
        "colorscale": "thermal" #[[0,"rgb(255, 0, 0)"],[1,"rgb(0, 255, 0)"]]
    }

    trace["x"] = [int(date.strftime("%m"))+12 if int(date.strftime("%m"))<int(datetime.now().strftime("%m")) else int(date.strftime("%m")) for date, value in input_data.items()]
    trace["y"] = [int(date.strftime("%d")) for date, value in input_data.items()]
    trace["z"] = [value for date, value in input_data.items()]
    trace["text"] = [date.strftime("%d/%m/%Y {} Gîtes".format(value)) for date, value in input_data.items()]

    trace["zmin"] = min(trace["z"])
    trace["zmax"] = max(trace["z"])

    data = gos.Data([trace])
    layout = {
        "title": "Number of lodges available on gites-de-france.com for {} people<br>Updated on {}".format(travelers, datetime.now().strftime("%d/%m/%Y")), 
        "xaxis": {
            "title": "", 
            "mirror": True, 
            "ticklen": 0, 
            "showline": True, 
            "tickmode": "array", 
            "ticktext": ["January","February","March","April","May","June","August","September","October","November","December"]*2,
            "tickvals": [i+2 for i in range(22)]
        }, 
        "yaxis": {
            "title": "", 
            "mirror": True, 
            "showline": True,
            "autorange": "reversed",
            "tickmode": "array", 
            "ticktext": [str(day+1) for day in range(31)], 
            "tickvals": [int(day+1) for day in range(31)]
        }
    }
    fig = gos.Figure(data=data, layout=layout)
    
    return fig

def map_gites(gites, participants_dict = None):
    gite_locations = {"lat":list(), "lon": list(), "text": list(), "link": list()}

    for gite in gites:
        gite_locations["lat"].append(gite.location[0])
        gite_locations["lon"].append(gite.location[1])
        gite_locations["link"].append(gite.link)
        gite_locations["text"].append("{} Bedrooms<br>{} People\n{}€".format(gite.bedrooms, gite.beds, gite.price))
        
    data = [
        go.Scattermapbox(
            lat = gite_locations["lat"],
            lon = gite_locations["lon"],
            mode = 'markers',
            marker = dict(
                size = 10,
                color = "red"
            ),
            name = "Gîtes",
            hovertemplate = "%{text}",
            text = gite_locations["text"],
            customdata = gite_locations["link"]
        )
    ]

    if participants_dict is not None:
        data.append(
            go.Scattermapbox(
                lat = [location[0] for name, location in participants_dict.items()],
                lon = [location[1] for name, location in participants_dict.items()],
                text = [name for name, location in participants_dict.items()],
                hoverinfo = "text",
                name = "Participants",
                textposition='bottom center',
                textfont = dict(size = 16, color = 'black'),
                mode = "text+markers",
                marker_size = 14,
                marker_color = "green"
            )
        )

    fig = go.Figure(
        data = data,
        layout = default_mapbox_layout,
    )
    
    fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0})

    plot_div = plot(fig, output_type = 'div', include_plotlyjs = True)

    res = re.search('<div id="([^"]*)"', plot_div)
    div_id = res.groups()[0]

    js_callback = """
    <script>
    var plot_element = document.getElementById("{div_id}");
    plot_element.on('plotly_click', function(data){{
        console.log(data);
        var point = data.points[0];
        if (point) {{
            console.log(point.customdata);
            window.open(point.customdata);
        }}
    }})
    </script>
    """.format(div_id=div_id)

    html_str = """
    <html>
    <body>
    {plot_div}
    {js_callback}
    </body>
    </html>
    """.format(plot_div=plot_div, js_callback=js_callback)

    return fig, html_str

def covoit_route(covoits):
    drivers = {driver_name: driver for driver_name, driver in covoits.items() if driver.is_driver}
    if any([driver.route is None for driver_name, driver in drivers.items()]):
        raise ValueError("No routes set")
    
    routes = list()

    for i, (driver_name, driver) in enumerate(drivers.items()):

        steps = list()
        steps.append((driver.name, driver.location))
        steps += [(passenger_name,covoits[passenger_name].location) for passenger_name in driver.passenger_names]
        steps.append(("Destination", driver.destination))

        routes.append([
            driver.route,
            {step_name: step_location for step_name, step_location in steps},
            colors[i]
        ])

    fig = go.Figure()

    markers = list()
    for route_data, steps, color in routes:
        lat, lon = [lat for lat, lon in route_data["route"]["geometry"]], [lon for lat, lon in route_data["route"]["geometry"]]

        fig.add_trace(
            go.Scattermapbox(
                lat = lat,
                lon = lon,
                line_width = 5,
                mode = "lines",
                showlegend = True,
                name = list(steps.keys())[0],
                hoverinfo = 'none',
                line_color = color
            )
        )

        for i, (name, location) in enumerate(steps.items()):
            if not (name in covoits.keys() and isinstance(covoits[name], datastores.TrainUser)):
                markers.append({
                    "name": name,
                    "location": location,
                    "type": "driver" if i == 0 else "end" if i == len(steps) - 1 else "passenger"
                })
            else:
                markers.append({
                    "name": name,
                    "location": covoits[name].departure_location,
                    "type": "passenger"
                })

    fig.add_trace(
        go.Scattermapbox(
            lat = [marker["location"][0] for marker in markers if marker["type"] == "driver"],
            lon = [marker["location"][1] for marker in markers if marker["type"] == "driver"],
            text = [marker["name"] for marker in markers if marker["type"] == "driver"],
            name = "Drivers",
            marker_size = 15,
            marker_color = "green",
            hoverinfo = "text",
            textposition="bottom center",
            textfont = dict(size=12, color="black"),
            mode = "text+markers"
        )
    )

    if sum([1 for covoit_name, covoit in covoits.items() if isinstance(covoit, datastores.TrainUser)]) > 0:
        train_users = {covoit_name: covoit for covoit_name, covoit in covoits.items() if isinstance(covoit, datastores.TrainUser)}
        train_stations = {covoit.train_station["name"]: covoit.train_station for name, covoit in train_users.items()}
        
        fig.add_trace(
            go.Scattermapbox(
                lat = [station["location"][0] for station_name, station in train_stations.items()],
                lon = [station["location"][1] for station_name, station in train_stations.items()],
                text = [station["name"] for station_name, station in train_stations.items()],
                name = "Train station",
                marker_size = 15,
                marker_color = "black",
                hoverinfo = "text",
                textposition="bottom center",
                textfont = dict(size=12, color="black"),
                mode = "text+markers"
            )
        )
        end_location = [marker for marker in markers if marker["type"] == "end"][0]
        for covoit_name, covoit in train_users.items():
            fig.add_trace(
                go.Scattermapbox(
                    lat = [covoit.departure_location[0], covoit.train_station["location"][0]],
                    lon = [covoit.departure_location[1], covoit.train_station["location"][1]],
                    line_width = 3,
                    mode = "lines",
                    showlegend = False,
                    hoverinfo = "none",
                    line = dict(color = "black"),
                    name = "Trains"
                )
            )

    fig.add_trace(
        go.Scattermapbox(
            lat = [marker["location"][0] for marker in markers if marker["type"] == "passenger"],
            lon = [marker["location"][1] for marker in markers if marker["type"] == "passenger"],
            text = [marker["name"] for marker in markers if marker["type"] == "passenger"],
            name = "Passengers",
            marker_size = 15,
            marker_color = "blue",
            hoverinfo = "text",
            textposition="bottom center",
            textfont = dict(size=12, color="black"),
            mode = "text+markers"
        )
    )
            
    fig.add_trace(
        go.Scattermapbox(
            lat = [marker["location"][0] for marker in markers if marker["type"] == "end"],
            lon = [marker["location"][1] for marker in markers if marker["type"] == "end"],
            text = [marker["name"] for marker in markers if marker["type"] == "end"],
            name = "Destination",
            marker_size = 15,
            marker_color = "red",
            hoverinfo = "text",
            textposition="bottom center",
            textfont = dict(size=12, color="black"),
            mode = "text+markers"
        )
    )


    fig.layout = default_mapbox_layout

    fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0})

    return fig