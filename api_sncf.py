import json, os, urllib.request
from utils import distance_km

class TrainStations():

    def __init__(self):
        if not os.path.exists("sncf_gares.json"):
            print("Downloading sncf_gares.json ...")
            urllib.request.urlretrieve("https://ressources.data.sncf.com/explore/dataset/referentiel-gares-voyageurs/download/?format=json&timezone=Europe/Berlin&lang=fr", "sncf_gares.json")
            print("Completed")

        with open("sncf_gares.json", "r", encoding="utf-8") as f:
            data = json.load(f)

        self.stations = list()
        for station in data:
            if not "wgs_84" in station["fields"].keys(): continue
            gare_dict = {
                "name": station["fields"]["gare_alias_libelle_noncontraint"],
                "lat": station["fields"]["wgs_84"][0],
                "lon": station["fields"]["wgs_84"][1],
                "ville": station["fields"]["commune_libellemin"]
            }
            self.stations.append(gare_dict)

    def find_closest_station(self, lat, lon):
        station_distances = [(station, distance_km(lat, lon, station["lat"], station["lon"])) for station in self.stations]
        return min(station_distances, key = lambda x: x[1])[0]
