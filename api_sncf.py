import json, os, urllib.request
from utils import distance_km

class TrainStations():

    def __init__(self):
        if not os.path.exists("sncf_gares.json"):
            self._load_stations()
        else:
            with open("sncf_gares.json", "r", encoding="utf-8") as f:
                self.stations = json.load(f)

    def _load_stations(self): 
        if not os.path.exists("sncf_gare_names.json"):
            print("Downloading sncf_gare_names.json ...")
            urllib.request.urlretrieve("https://ressources.data.sncf.com/explore/dataset/referentiel-gares-voyageurs/download/?format=json&timezone=Europe/Berlin&lang=fr", "sncf_gare_names.json")
            print("Completed")

        if not os.path.exists("sncf_gares_affluence.json"):
            print("Downloading sncf_gares_affluence.json ...")
            urllib.request.urlretrieve("https://ressources.data.sncf.com/explore/dataset/frequentation-gares/download/?format=json&timezone=Europe/Berlin&lang=fr", "sncf_gares_affluence.json")
            print("Completed")

        with open("sncf_gare_names.json", "r", encoding="utf-8") as f:
            station_data = json.load(f)

        with open("sncf_gares_affluence.json", "r", encoding="utf-8") as f:
            affluence_data = json.load(f)
            affluence_data = {int(station["fields"]["code_uic_complet"]): station["fields"] for station in affluence_data}

        for uic, station in affluence_data.items():
            affluence_sum, field_count = 0, 0
            for field_name, field in station.items():
                if "total_voyageurs_20" in  field_name:
                    field_count += 1
                    affluence_sum += field

            affluence_data[uic] = int(affluence_sum / field_count)

        self.stations = list()
        for station in station_data:
            if not "wgs_84" in station["fields"].keys(): continue
            uic = int(station["fields"]["uic_code"])
            gare_dict = {
                "name": station["fields"]["gare_alias_libelle_noncontraint"],
                "location": station["fields"]["wgs_84"],
                "city": station["fields"]["commune_libellemin"],
                "affluence": affluence_data[uic] if uic in affluence_data.keys() else 0,
                "uic_code": uic
            }
            self.stations.append(gare_dict)

        with open("sncf_gares.json", "w", encoding="utf-8") as f:
            json.dump(self.stations, f)

    def find_closest_station(self, location, min_affluence = 0):
        lat, lon = location[0], location[1]
        station_distances = [(station, distance_km(lat, lon, station["location"][0], station["location"][1])) for station in self.stations if station["affluence"] > min_affluence]
        return min(station_distances, key = lambda x: x[1])[0]

if __name__ == "__main__":
    trains = TrainStations()
    for station in trains.stations:
        print(station)