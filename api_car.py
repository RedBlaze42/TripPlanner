import requests, json, time, polyline, ratelimit
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
        
        return req_data["locationList"]

    def directions(self, waypoints, fuel_cost = 1.5):
        url = "https://vmrest.viamichelin.com/apir/11/iti.json/eng/geom;header;roadsheet"
        data = {
            "stepList": "".join(["1:e:{}:{};".format(waypoint[1], waypoint[0]) for waypoint in waypoints]),
            "fuelCost": fuel_cost, "fuelConsump":"7.9:6.9:7", "authKey": self.auth_key,
            "distUnit":"m","itit":0,"veht":0,"avoidExpressWays":False,"avoidBorders":False,"avoidTolls":False,"avoidCCZ":False,"avoidORC":False,"avoidPass":False,"avoidClosedRoad":True,"currency":"EUR","favMotorways":False,"fuelCost":fuel_cost,"itineraryFuelType":"petrol","fullMapOpt":"300:300:true:true:true","indemnite":0,"stepMapOpt":"300:300:true:true:true","traffic":"ALL","isCostFctUsingTraffic":False,"sortFDRsByTraffic":False,"itineraryVehiculeType":"hatchback","wCaravan":False,"withSecurityAdv":False,"shouldUseNewEngine":False,"shouldUseTraffic":False,"costCategory":"car","isMotorVehicle":True,"lg":"eng","obfuscation":False,"charset":"UTF-8","ie":"UTF-8","nocache":1632567830744,"protocol":"https","callback":"JSE.HTTP.asyncRequests[3]._scriptLoaded"
        }
        
        req = requests.get(url, params = data)
        req.raise_for_status()
        data = json.loads(req.content[req.content.decode("utf-8").index("{"):-1])
        
        if not "itineraryList" in data.keys():
            print(data)
            return None
        
        data = data["itineraryList"][0]

        output = {
            "fuel_cost": round(data["header"]["summaryList"][0]["consumption"], 2),
            "toll_cost": round(data["header"]["summaryList"][0]["tollCost"]["car"]/100, 2),
            "total_cost": round(data["header"]["summaryList"][0]["consumption"] + data["header"]["summaryList"][0]["tollCost"]["car"]/100, 2),
            "distance_km": int(data["header"]["summaryList"][0]["drivingDist"]/1000),
            "time":data["header"]["summaryList"][0]["drivingTime"]
        }

        return output


class OpenRouteService():
    
    def __init__(self, config_path = "config.json"):
        with open(config_path, "r") as f:
            self.api_key = json.load(f)["openrouteservice_key"]
        self.session = requests.Session()
        self.session.headers.update({'Authorization': self.api_key, "Accept": "application/json"})
            
    @ratelimit.sleep_and_retry
    @ratelimit.limits(calls = 40, period = 120)
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
                
                dest_id = destinations_list.index(location_dest[::-1])
                
                trip_dict = {
                    "distance": raw_data["distances"][source_id][dest_id],
                    "duration": raw_data["durations"][source_id][dest_id]
                }
                
                matrix_data[name_source][name_dest] = trip_dict
        
        return matrix_data
    
    @ratelimit.sleep_and_retry
    @ratelimit.limits(calls = 30, period = 60)
    def route(self, waypoints):
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

    def set_driver_route(self, driver, covoits):
        if not driver.is_driver and len(driver.passenger_names) == 0: return None
        waypoints = [driver.location]
        waypoints += [covoits[passenger_name].location for passenger_name in driver.passenger_names]
        waypoints.append(driver.destination)

        driver.route = self.route(waypoints)
        return driver.route
    
    @ratelimit.sleep_and_retry
    @ratelimit.limits(calls = 100, period = 120)
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
                properties["country"]+", " if "country" in properties.keys() else ""
            )
        }
        
        return output      