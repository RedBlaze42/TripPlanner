import requests, json, polyline, time, threading
from utils import distance_km, interpolate_segments

def extract_michelin_points(points, data):
    white_list = ["C", "V", "P", "lim", "eTrafic"]
    if len(data) > 1 and data[0] in white_list and isinstance(data[1], dict) and "latitude" in data[1].keys() and "longitude" in data[1].keys():
        points.append([data[1]["latitude"], data[1]["longitude"]])
    else:
        return points
    
    for entry in data:
        if isinstance(entry, list) and len(entry) > 0:
            for entry2 in entry:
                if isinstance(entry2, list) and len(entry2) > 0:
                    extract_michelin_points(points, entry2)
    return points

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
                loc_distances.append((location["location"]["id"], distance_km([coords["lat"], coords["lon"]], point)))

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
        
        return req_data["locationList"]

    def directions(self, waypoints, fuel_cost = 1.5):
        url = "https://vmrest.viamichelin.com/apir/11/iti.json/eng/geom;header;roadsheet"
        data = {
            "stepList": "".join(["1:e:{}:{};".format(waypoint[1], waypoint[0]) for waypoint in waypoints]),
            "fuelCost": fuel_cost, "fuelConsump":"7.9:6.9:7", "authKey": self.auth_key,
            "distUnit":"m","itit":0,"veht":0,"avoidExpressWays":False,"avoidBorders":False,"avoidTolls":False,"avoidCCZ":False,"avoidORC":False,"avoidPass":False,"avoidClosedRoad":True,"currency":"EUR","favMotorways":False,"fuelCost":fuel_cost,"itineraryFuelType":"petrol","fullMapOpt":"300:300:true:true:true","indemnite":0,"stepMapOpt":"300:300:true:true:true","traffic":"ALL","isCostFctUsingTraffic":False,"sortFDRsByTraffic":False,"itineraryVehiculeType":"hatchback","wCaravan":False,"withSecurityAdv":False,"shouldUseNewEngine":False,"shouldUseTraffic":False,"costCategory":"car","isMotorVehicle":True,"lg":"eng","obfuscation":False,"charset":"UTF-8","ie":"UTF-8","nocache":1632567830744,"protocol":"https","callback":"JSE.HTTP.asyncRequests[3]._scriptLoaded"
        }
        
        tries = 0
        
        while tries < 10:
            try:
                req = requests.get(url, params = data)
            except requests.exceptions.ConnectionError:
                tries += 1
                continue
            else:
                break
        
        req.raise_for_status()
        data = json.loads(req.content[req.content.decode("utf-8").index("{"):-1])
        
        if not "itineraryList" in data.keys():
            print(data)
            return None
        
        data = data["itineraryList"][0]

        points = list()

        for entry in data["roadSheet"][0]:
            extract_michelin_points(points, entry)

        output = {
            "fuel_cost": round(data["header"]["summaryList"][0]["consumption"], 2),
            "toll_cost": round(data["header"]["summaryList"][0]["tollCost"]["car"]/100, 2),
            "total_cost": round(data["header"]["summaryList"][0]["consumption"] + data["header"]["summaryList"][0]["tollCost"]["car"]/100, 2),
            "distance_km": int(data["header"]["summaryList"][0]["drivingDist"]/1000),
            "time":data["header"]["summaryList"][0]["drivingTime"],
            "points": points
        }

        return output

    def directions_multithreaded(self, route_list):
        output = [None]*len(route_list)

        def thread_directions(waypoints, output, i):
            output[i] = self.directions(waypoints)

        threads = [threading.Thread(target=thread_directions, args=(waypoints, output, i)) for i, waypoints in enumerate(route_list)]
        [thread.start() for thread in threads]
        [thread.join() for thread in threads]

        return output

class OpenRouteService():
    
    def __init__(self, config_path = "config.json"):
        with open(config_path, "r") as f:
            self.api_key = json.load(f)["openrouteservice_key"]
        self.session = requests.Session()
        self.session.headers.update({'Authorization': self.api_key, "Accept": "application/json"})
        
    def post(self, url, json = None):
        tries = 0
        status_code = 429
        while status_code == 429 and tries < 4:
            req = self.session.post(url, json = json)
            tries += 1  
            status_code = req.status_code
            
            if status_code == 429:
                print("Waiting 30 secs...")
                time.sleep(30)
                
        return req
    
    def matrix(self, destinations):
        url = "https://api.openrouteservice.org/v2/matrix/driving-car"
        
        destinations_list = [dest_location[::-1] for dest_name, dest_location in destinations.items()]
        req = self.post(url, json = {"locations":destinations_list,"metrics":["distance","duration"]})
        
        req.raise_for_status()
        
        raw_data = req.json()
        
        matrix_data = dict()
        for name_source, location_source in destinations.items():
            
            source_id = destinations_list.index(location_source[::-1])
            
            matrix_data[name_source] = dict()
            
            for name_dest, location_dest in destinations.items():
                
                dest_id = destinations_list.index(location_dest[::-1])
                
                trip_dict = {
                    "distance": raw_data["distances"][source_id][dest_id],
                    "duration": raw_data["durations"][source_id][dest_id]
                }
                
                matrix_data[name_source][name_dest] = trip_dict
        
        return matrix_data
    
    def route(self, waypoints):
        url = "https://api.openrouteservice.org/v2/directions/driving-car"
        data = {
            "coordinates":[list(waypoint[::-1]) for waypoint in waypoints],
            "extra_info":["tollways"],"instructions":"false","maneuvers":"false","units":"m","geometry":"true"
        }
        
        req = self.post(url, json = data)
        
        if req.status_code == 404:
            raise InvalidLocationError

        req.raise_for_status()
        data = req.json()
        data["route"] = data["routes"][0]
        del data["routes"]
        
        data["route"]["geometry"] = polyline.decode(data["route"]["geometry"])
        
        return data

    def set_driver_route(self, driver, covoits):
        if not driver.is_driver and len(driver.passenger_names) == 0: return None
        waypoints = [driver.location]
        waypoints += [covoits[passenger_name].location for passenger_name in driver.passenger_names]
        waypoints.append(driver.destination)

        driver.route = self.route(waypoints)
        return driver.route
    
    def geocode(self, query):
        url = "https://api.openrouteservice.org/geocode/search"
        
        params = {
            "text": query,
            "api_key": self.api_key,
            "boundary.circle.lat": 47.051133,
            "boundary.circle.lon": 2.512952,
            "boundary.circle.radius": 600
        }
        
        req = self.session.get(url, params = params)
        req.raise_for_status()
        
        raw_data = req.json()
        
        if len(raw_data["features"]) == 0: return None
        
        feature = raw_data["features"][0]
        properties = feature["properties"]
        output = {
            "location": feature["geometry"]["coordinates"][::-1],
            "name": "{}{}{}".format(
                properties["county"]+", " if "county" in properties.keys() else properties["name"]+", " if "name" in properties.keys() else "",
                properties["region"]+", " if "region" in properties.keys() else "",
                properties["country"] if "country" in properties.keys() else ""
            )
        }
        
        return output
    
class InvalidLocationError(Exception):
    pass