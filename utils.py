from math import sin, cos, sqrt, atan2, radians, asin, degrees
import urllib.request, urllib.parse
import os, json
import time
import paramiko, pysftp
from base64 import decodebytes
import numpy as np

radius = 6373.0

def distance_km(from_point, to_point):
    lat1, lon1 = radians(from_point[0]), radians(from_point[1])
    lat2, lon2 = radians(to_point[0]), radians(to_point[1])
    dlon = lon1 - lon2
    dlat = lat1 - lat2
    a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return c * radius

def min_distance_km_np(lat1, lon1, lat2, lon2):
    lon1, lat1, lon2, lat2 = map(np.array, [lon1, lat1, lon2, lat2])
    lon1, lat1, lon2, lat2 = map(np.radians, [lon1, lat1, lon2, lat2])

    dlon = lon2 - lon1
    dlat = lat2 - lat1

    a = np.sin(dlat/2.0)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2.0)**2

    c = 2 * np.arcsin(np.sqrt(a))
    km = 6373 * c
    return np.min(km)

def trace_distance_km(trace):
    distance_sum = 0
    prev_point = trace[0]
    for point in trace[1:]:
        distance_sum += distance_km(prev_point, point)

    return distance_sum

def get_line_bearing(lat1, lon1, lat2, lon2):
    lat1, lon1 = radians(lat1), radians(lon1)
    lat2, lon2 = radians(lat2), radians(lon2)
    dlat = lon2-lon1
    val_rad = atan2( sin(dlat)*cos(lat2) , cos(lat1) * sin(lat2) - sin(lat1) * cos(lat2) * cos(dlat))
    return val_rad

def point_bearing_distance(lat, lon, bearing, distance):
    lat, lon = radians(lat), radians(lon)
    point_lat = asin( sin(lat)*cos(distance/radius) + cos(lat)*sin(distance/radius)*cos(bearing))
    point_lon = lon + atan2(sin(bearing)*sin(distance/radius)*cos(lat), cos(distance/radius)-sin(lat)*sin(point_lat))
    return degrees(point_lat), degrees(point_lon)

def interpolate_segment(from_point, to_point, step_km = 5):
    points = list()
    segment_distance = distance_km(from_point, to_point)
    bearing = get_line_bearing(from_point[0], from_point[1], to_point[0], to_point[1])

    for distance in range(0, int(segment_distance), step_km):
        points.append(list(point_bearing_distance(from_point[0], from_point[1], bearing, distance)))

    return points

def interpolate_segments(points, step_km = 5):
    output = [points[0],]
    for point in points[1:]:
        output += interpolate_segment(output[-1], point, step_km = step_km)
        output.append(point)

    return output

def is_in_france(location):
    return distance_km([46.452547, 2.404213], location) < 600

def format_seconds(seconds, show_seconds=False):
    output = ""
    output += "{}h".format(seconds//3600)
    output += " {}m".format(seconds%3600//60)
        
    if show_seconds:
        output += " {}s".format(seconds%60)
    
    return output

def nocache(link):
    link += "?" if not "?" in link else "&"
    link += "nocache={:.0f}".format(time.time())
    return link

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
        return min(self.villes.items(), key = lambda x : distance_km(x[1], [lat, lon]))[0]

class SftpClient():

    def __init__(self, config_path = "config.json"):
        with open(config_path, "r") as f:
            self.access_info = json.load(f)["sftp_access"]
        #key = paramiko.RSAKey(data=decodebytes(self.access_info["keydata"].encode("utf-8")))
        self.cnopts = pysftp.CnOpts()
        self.cnopts.hostkeys = None
        #self.cnopts.hostkeys.add(self.access_info["host"], 'ssh-rsa', key)
        self.remote_path = "/" + "/".join([path for path in self.access_info["html_root"].split("/") + self.access_info["path"].split("/") if path != ""])

        with self.client as client:
            client.makedirs(self.access_info["html_root"]+"/"+self.access_info["path"])
        
    @property
    def client(self):
        return pysftp.Connection(self.access_info["host"], username = self.access_info["username"], password = self.access_info["password"], port = self.access_info["port"], cnopts = self.cnopts)

    def upload_file(self, filename, delete_after = True):
        with self.client as client:
            with client.cd(self.remote_path):
                client.put(filename)
        if delete_after: os.remove(filename)
        return nocache("http://" + "/".join([dirname for dirname in self.access_info["host"].split("/") + self.access_info["path"].split("/") + filename.split("/") if dirname != ""]))

    def list_dir(self):
        with self.client as client:
            file_list = client.listdir(self.remote_path)

        return file_list

    def remove_file(self, filename):
        with self.client as client:
            with client.cd(self.remote_path):
                client.remove(filename)

    def remove_all(self):
        with self.client as client:
            with client.cd(self.remote_path):
                file_list = client.listdir(".")
                for file in file_list:
                    client.remove(file)