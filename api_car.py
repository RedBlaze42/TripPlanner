import requests, json, time, polyline
from utils import distance_km

class Michelin():
    
    def __init__(self, auth_key = None):
        if auth_key is None:
            self.auth_key = "JSBS20110216111214120400892678"#"JSBS20160223162852451059820592"
        else:
            self.auth_key = auth_key

    def geocode(self, query, point = None):
        url = "https://secure-apir.viamichelin.com/apir/1/geocode1f.json2"
        data = {"query":query,"obfuscation":False,"ie":"UTF-8","charset":"UTF-8","authKey":self.auth_key,"lg":"fra","nocache":1631885079421,"protocol":"https"}
        req = requests.get(url, params = data)
        req.raise_for_status()
        req_data = req.json()
        
        if point is None:
            return req_data["locationList"][0]["location"]["id"]
        else:
            loc_distances = list()
            for location in req_data["locationList"]:
                coords = location["location"]["coords"]
                loc_distances.append((location["location"]["id"], distance_km(coords["lat"], coords["lon"], point[0], point[1])))

            return min(loc_distances, key = lambda x: x[1])[0]
    
    def rgeocode(self, lat, lon):
        url = "https://vmrest.viamichelin.com/apir/1/rgeocode.json2"
        
        data = {
            "center": "{}:{}".format(lon, lat),
            "showHT": True,"obfuscation": False,"ie": "UTF-8","charset": "UTF-8","authKey": self.auth_key,"lg": "eng","protocol": "https"
        }
        req = requests.get(url, params = data)
        req.raise_for_status()
        req_data = req.json()
        print(req.content)
        return req_data["locationList"][0]["location"]["id"]

    def directions(self, orig_id, dest_id, fuel_cost = 1.5):
        url = "https://secure-apir.viamichelin.com/apir/2/iti.json/fra"
        data = {
            "steps":"3:e:{};3:e:{};".format(orig_id, dest_id),
            "fuelCost": fuel_cost, "fuelConsump":"7.9:6.9:7", "authKey": self.auth_key,
            "distUnit":"m","veht":0,"itit":0,"avoidClosedRoad":False,"currency":"EUR","indemnite":0,"favMotorways":True,"avoidBorders":False,"avoidTolls":False,"avoidCCZ":False,"avoidORC":False,"avoidPass":False,"wCaravan":False,"withSecurityAdv":True,"avoidExpressWays":False,"fullMapOpt":"300:300:true:true:true","stepMapOpt":"300:300:true:true:true","multipleIti":True,"traffic":"FRA","obfuscation":False,"ie":"UTF-8","charset":"UTF-8","lg":"fra","nocache":time.time()*1000,"protocol":"https", "callback":"JSE.HTTP.asyncRequests[9].HTTPResponseLoaded"
        }

        req = requests.get(url, params = data)
        req.raise_for_status()
        data = json.loads(req.content[req.content.decode("utf-8").index("{"):-1])
        
        if not "header" in data.keys():
            print(data)
            return None
        
        output = {
            "fuel_cost": round(data["header"]["summaries"][0]["consumption"], 2),
            "toll_cost": round(data["header"]["summaries"][0]["tollCost"]["car"]/100, 2),
            "total_cost": round(data["header"]["summaries"][0]["consumption"] + data["header"]["summaries"][0]["tollCost"]["car"]/100, 2),
            "distance_km": int(data["header"]["summaries"][0]["drivingDist"]/1000),
            "time":data["header"]["summaries"][0]["drivingTime"]
        }

        return output

class OpenRouteService():
    
    def __init__(self, config_path = "config.json"):
        with open(config_path, "r") as f:
            self.key = json.load(f)["openrouteservice_key"]
        self.session = requests.Session()
        self.session.headers.update({'Authorization': self.key, "Accept": "application/json"})
            
            
    def matrix(self, destinations):
        url = "https://api.openrouteservice.org/v2/matrix/driving-car"
        
        destinations_list = [dest_location[::-1] for dest_name, dest_location in destinations.items()]
        req = self.session.post(url, json ={"locations":destinations_list,"metrics":["distance","duration"]})
        
        req.raise_for_status()
        #print(req.content)
        raw_data = req.json()
        
        matrix_data = dict()
        for name_source, location_source in destinations.items():
            
            source_id = destinations_list.index(location_source[::-1])
            
            matrix_data[name_source] = dict()
            
            for name_dest, location_dest in destinations.items():
                if name_dest == name_source: continue
                
                dest_id = destinations_list.index(location_dest[::-1])
                
                trip_dict = {
                    "distance": raw_data["distances"][source_id][dest_id],
                    "duration": raw_data["durations"][source_id][dest_id]
                }
                
                matrix_data[name_source][name_dest] = trip_dict
        
        return matrix_data
    
    def directions(self, waypoints):
        url = "https://api.openrouteservice.org/v2/directions/driving-car"
        
        data = {
            "coordinates":[waypoint[::-1] for waypoint in waypoints],
            "extra_info":["tollways"],"instructions":"false","maneuvers":"false","units":"m","geometry":"true"
        }
        
        req = self.session.post(url, json = data)
        req.raise_for_status()
        data = req.json()
        data["route"] = data["routes"][0]
        del data["routes"]
        
        data["route"]["geometry"] = polyline.decode(data["route"]["geometry"])
        
        return data