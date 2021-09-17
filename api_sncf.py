import json, os, urllib.request
from math import sin, cos, sqrt, atan2, radians

class TrainStations():

    def __init__(self):
        if not os.path.exists("sncf_gares.json"):
            urllib.request.urlretrieve("https://ressources.data.sncf.com/explore/dataset/referentiel-gares-voyageurs/download/?format=json&timezone=Europe/Berlin&lang=fr", "sncf_gares.json")

        with open("sncf_gares.json", "r", encoding="utf-8") as f:
            data = json.load(f)

        self.stations = list()
        for station in data:
            if not "wgs_84" in station["fields"].keys(): continue
            gare_dict = {
                "name": station["fields"]["gare_alias_libelle_noncontraint"],
                "lat": station["fields"]["wgs_84"][0],
                "lon": station["fields"]["wgs_84"][1]
            }
            self.stations.append(gare_dict)

    def find_closest_station(self, lat, lon):
        radius = 6373.0
        station_distances = list()
        for station in self.stations:
            lat1, lon1 = radians(lat), radians(lon)
            lat2, lon2 = radians(station["lat"]), radians(station["lon"])
            dlon = lon1 - lon2
            dlat = lat1 - lat2
            a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
            c = 2 * atan2(sqrt(a), sqrt(1 - a))

            station_distances.append((station, radius * c))
        station_distances.sort(key = lambda x: x[1])
        return station_distances[0][0]