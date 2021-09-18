import json, os, urllib.request, requests, re
from utils import distance_km
from datetime import datetime

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
                "lon": station["fields"]["wgs_84"][1],
                "ville": station["fields"]["commune_libellemin"]
            }
            self.stations.append(gare_dict)

    def find_closest_station(self, lat, lon):
        station_distances = [(station, distance_km(lat, lon, station["lat"], station["lon"])) for station in self.stations]
        station_distances.sort(key = lambda x: x[1])
        return station_distances[0][0]

class TrainLine():

    def __init__(self):
        with open("trainline_headers.json", "r") as f: self.headers = json.load(f)
        self.session = requests.Session()
        self.session.get("https://www.thetrainline.com/") #To get cookies
        
        
    def geocode(self, query, point = None):
        url = "https://www.thetrainline.com/api/locations-search/v1/search"
        
        data = {
            "searchTerm": query,
            "lang":"en","scopes":"atoconly","scopes":"eurostaronly","scopes":"sncf","scopes":"benerail","scopes":"trenitalia","scopes":"renfe","scopes":"ntv","scopes":"busbud","scopes":"flixbus","scopes":"dbfull","scopes":"ouigo","scopes":"obb","scopes":"cff","scopes":"westbahn","scopes":"distribusion","scopes":"busbudfull","size":30,"country":"FR","locationType":"station","locationType":"stationGroup","locationType":"city"
        }
        
        req = self.session.get(url, params=data)
        req.raise_for_status()
        req_data = req.json()["requestedCountry"]
        
        if point is None:
            return req_data[0]["id"]
        else:
            loc_distances = list()
            for location in req_data:
                loc_distances.append((location["id"], distance_km(location["latitude"], location["longitude"], point[0], point[1])))

            return min(loc_distances, key = lambda x: x[1])[0]
        
    def directions(self, origin_id, dest_id, departure_datetime):
        url = "https://www.thetrainline.com/api/journey-search/"
        
        data = {"transitDefinitions":
            [{"direction":"outward","origin":origin_id,"destination":dest_id,"journeyDate":{"type":"departAfter","time":departure_datetime.strftime("%Y-%m-%dT%H:%M:%S")}}],
            "passengers":[{"id":"ef02a327-3d8d-4d63-a3c4-b23b9eb4aaf3","dateOfBirth":"1994-09-18","cardIds":[]}],"isEurope":True,"cards":[],"type":"return","maximumJourneys":5,"includeRealtime":True,"transportModes":["mixed"],"directSearch":False}
        
        req = self.session.post(url, json = data)
        req.raise_for_status()
        
        req_data = req.json()["data"]["journeySearch"]
        
        voyages = list()
        for alternative_id, alternative in req_data["alternatives"].items():
            #voyages.append({"duration":, "total_cost":})
            price = alternative["fullPrice"]["amount"]
            fares = alternative["fares"]
            
            duration = 0
            
            for fare in fares:
                legs = req_data["fares"][fare]["fareLegs"]
                
                for leg in legs:
                    req_data["legs"][leg]
                    result = re.findall(r"PT(\d*)H(\d*)M",req_data["legs"][leg]["duration"])
                    print(result)
            
        
        
if __name__ == "__main__":
    train = TrainLine()
    origin_id, dest_id = train.geocode("Paris"), train.geocode("Marseille")
    train.directions(origin_id, dest_id, datetime(2021,10,21,12,0,0))