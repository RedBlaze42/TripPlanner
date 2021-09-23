import api_gites
import json, os, re
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
from plotly.offline import plot
import plotly.graph_objs as gos
from tqdm import tqdm

def nb_gites(to_datetime = None, travelers = 14, input_data = None):
    if input_data is None:
        from_datetime = datetime.now()
        if to_datetime is None:
            to_datetime = from_datetime + timedelta(days = 31*7)

        to_datetime = to_datetime.replace(month = to_datetime.month+1, day = 2)

        input_data = dict()
        checkin = from_datetime
        checkout = checkin + timedelta(days = 1)
        progress_bar = tqdm(total = int((to_datetime-from_datetime).total_seconds()//86400))
        while checkout < to_datetime:
            input_data[checkin.isoformat()] = len(api_gites.GitesDeFrance(checkin, checkout, travelers))
            checkin = checkout
            checkout += timedelta(days = 1)
            progress_bar.update(1)
        progress_bar.close()
    
    input_data = {datetime.fromisoformat(date): value for date, value in input_data.items()}
    trace = {
    "type": "heatmap",
    "colorbar": {"title": "gites"}, 
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
    "title": "Nombre de gîtes disponibles sur gitesdefrance.com, mis à jour le {}".format(datetime.now().strftime("%d/%m/%Y à %H:%M")), 
    "xaxis": {
        "title": "", 
        "mirror": True, 
        "ticklen": 0, 
        "showline": True, 
        "tickmode": "array", 
        "ticktext": ["Janvier","Février","Mars","Avril","Mai","Juin","Août","Septembre","Octobre","Novembre","Décembre"]*2,
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

def map_gites(gites):
    gite_locations = {"lat":list(), "lon": list(), "text": list(), "link": list()}

    for gite in tqdm(gites):
        gite_locations["lat"].append(gite.location[0])
        gite_locations["lon"].append(gite.location[1])
        gite_locations["link"].append(gite.link)
        gite_locations["text"].append("{} Chambres\n{} Personnes\n{}€".format(gite.chambres, gite.personnes, gite.price))
        
    data = [
        go.Scattermapbox(
            lat=gite_locations["lat"],
            lon=gite_locations["lon"],
            mode='markers',
            marker=dict(
                size=14
            ),
            name="gites",
            hovertemplate = "%{text}",
            text=gite_locations["text"],
            customdata=gite_locations["link"]
        )
    ]

    layout = go.Layout(
        hovermode='closest',
        mapbox=dict(
        bearing=0,
        center=dict(
            lat=46,
            lon=2
        ),
        pitch=0,
        zoom=6,
        )
    )

    fig = go.Figure(
        data=data,
        layout=layout,
    )

    fig.update_layout(mapbox_style="open-street-map")
    fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0})

    plot_div = plot(fig, output_type='div', include_plotlyjs=True)

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
