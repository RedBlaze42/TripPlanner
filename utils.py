from math import sin, cos, sqrt, atan2, radians
import urllib.request, os, json
import time

def distance_km(lat1, lon1, lat2, lon2):
    radius = 6373.0
    lat1, lon1 = radians(lat1), radians(lon1)
    lat2, lon2 = radians(lat2), radians(lon2)
    dlon = lon1 - lon2
    dlat = lat1 - lat2
    a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return c * radius

def is_in_france(lat, lon):
    return distance_km(46.452547, 2.404213, lat, lon) < 600

def format_seconds(seconds, show_seconds=False):
    output = ""
    output += "{}h".format(seconds//3600)
    output += " {}m".format(seconds%3600//60)
        
    if show_seconds:
        output += " {}s".format(seconds%60)
    
    return output

class GeoCoder():
    
    def __init__(self):
        if not os.path.exists("villes_laposte.json"):
            print("Downloading villes_laposte.json ...")
            urllib.request.urlretrieve("https://datanova.legroupe.laposte.fr/explore/dataset/laposte_hexasmal/download/?format=json&timezone=Europe/Berlin&lang=fr", "villes_laposte.json")
            print("Completed")
            
        with open("villes_laposte.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        
        self.villes = dict()
        
        for ville in data:
            if "coordonnees_gps" not in ville["fields"]:
                continue

            self.villes[ville["fields"]["nom_de_la_commune"]] = ville["fields"]["coordonnees_gps"]
        
    def geocode(self, lat, lon):
        return min(self.villes.items(), key = lambda x : distance_km(x[1][0], x[1][1], lat, lon))[0]