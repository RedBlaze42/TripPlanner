import json, csv, os, urllib.request, zipfile
from utils import distance_km

def _download_if_not_exist(url, path):
    if not os.path.exists(path):
        print("Downloading {} ...".format(path))
        urllib.request.urlretrieve(url, path)
        print("Completed")

class TrainStations():

    def __init__(self):
        self.gtfs_blacklist = [
            "OCENavette"
        ]

        if not os.path.exists("sncf_gares.json"):
            self._load_stations()
        else:
            with open("sncf_gares.json", "r", encoding="utf-8") as f:
                self.stations = json.load(f)

        if not os.path.exists("sncf_gtfs.json"):
            self._load_gtfs_feeds()
        else:
            with open("sncf_gtfs.json", "r", encoding="utf-8") as f:
                self.gtfs = json.load(f)

    def _load_stations(self):
        _download_if_not_exist("https://ressources.data.sncf.com/explore/dataset/referentiel-gares-voyageurs/download/?format=json&timezone=Europe/Berlin&lang=fr", "sncf_gare_names.json")
        _download_if_not_exist("https://ressources.data.sncf.com/explore/dataset/frequentation-gares/download/?format=json&timezone=Europe/Berlin&lang=fr", "sncf_gares_affluence.json")

        with open("sncf_gare_names.json", "r", encoding="utf-8") as f:
            station_data = json.load(f)

        with open("sncf_gares_affluence.json", "r", encoding="utf-8") as f:
            affluence_data = json.load(f)
            affluence_data = {station["fields"]["code_uic_complet"]: station["fields"] for station in affluence_data}

        for uic, station in affluence_data.items():
            affluence_sum, field_count = 0, 0
            for field_name, field in station.items():
                if "total_voyageurs_20" in  field_name:
                    field_count += 1
                    affluence_sum += field

            affluence_data[uic] = int(affluence_sum / field_count)

        self.stations = dict()
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
            self.stations[gare_dict["uic_code"]] = gare_dict

        with open("sncf_gares.json", "w", encoding="utf-8") as f:
            json.dump(self.stations, f)
        
        os.remove("sncf_gare_names.json")
        os.remove("sncf_gares_affluence.json")

    def _load_gtfs_feeds(self):
        gtfs_feeds = [
            "https://eu.ftp.opendatasoft.com/sncf/gtfs/export-ter-gtfs-last.zip",
            "https://eu.ftp.opendatasoft.com/sncf/gtfs/export-intercites-gtfs-last.zip",
            "https://eu.ftp.opendatasoft.com/sncf/gtfs/export_gtfs_voyages.zip"
        ]

        self.gtfs = list()
        for feed in gtfs_feeds:
            feed_path = feed.split("/")[-1]
            _download_if_not_exist(feed, feed_path)

            zipfile.ZipFile(feed_path).extract("stop_times.txt")
            with open("stop_times.txt", "r") as f:
                csv_reader = csv.reader(f)
                for row in csv_reader:
                    if row[0] == "trip_id": continue

                    if any([blacklist in row[-1] for blacklist in self.gtfs_blacklist]): continue
                    
                    self.gtfs.append((row[0].split(":")[0], int(row[3].split("-")[-1])))

            os.remove("stop_times.txt")
            os.remove(feed_path)

        with open("sncf_gtfs.json", "w") as f:
            json.dump(self.gtfs, f)

    def find_closest_station(self, location, min_affluence = 0):
        lat, lon = location[0], location[1]
        station_distances = [(station, distance_km(lat, lon, station["location"][0], station["location"][1])) for uic, station in self.stations.items() if station["affluence"] > min_affluence]
        return min(station_distances, key = lambda x: x[1])[0]

    def get_stations_in_radius(self, location, radius):
        return [station for station_uic, station in self.stations.items() if distance_km(station["location"][0], station["location"][1], location[0], location[1]) < radius]

    def get_connected_station(self, station):
        uic = int(station["uic_code"])
        routes = {route_name for route_name, station in self.gtfs if station == uic}
        stations = {station for route_name, station in self.gtfs if route_name in routes}

        return [self.stations[str(uic)] for uic in stations if str(uic) in self.stations.keys()]