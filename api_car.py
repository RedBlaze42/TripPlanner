import requests, json, time

auth_key = "JSBS20160223162852451059820592"

def geocode(query):
    url = "https://secure-apir.viamichelin.com/apir/1/geocode1f.json2"
    data = {"query":query,"obfuscation":False,"ie":"UTF-8","charset":"UTF-8","authKey":auth_key,"lg":"fra","nocache":1631885079421,"protocol":"https"}
    req = requests.get(url, params = data)
    req.raise_for_status()
    return req.json()["locationList"][0]["location"]["id"]

def directions(orig, dest, fuel_cost = 1.5):
    url = "https://secure-apir.viamichelin.com/apir/2/iti.json/fra"
    data = {
        "steps":"3:e:{};3:e:{};".format(geocode(orig), geocode(dest)),
        "fuelCost": fuel_cost, "fuelConsump":"7.9:6.9:7", "authKey":auth_key,
        "distUnit":"m","veht":0,"itit":0,"avoidClosedRoad":False,"currency":"EUR","indemnite":0,"favMotorways":True,"avoidBorders":False,"avoidTolls":False,"avoidCCZ":False,"avoidORC":False,"avoidPass":False,"wCaravan":False,"withSecurityAdv":True,"avoidExpressWays":False,"fullMapOpt":"300:300:true:true:true","stepMapOpt":"300:300:true:true:true","multipleIti":True,"traffic":"FRA","obfuscation":False,"ie":"UTF-8","charset":"UTF-8","lg":"fra","nocache":time.time()*1000,"protocol":"https", "callback":"JSE.HTTP.asyncRequests[9].HTTPResponseLoaded"
    }

    req = requests.get(url, params = data)
    req.raise_for_status()
    data = json.loads(req.content[req.content.decode("utf-8").index("{"):-1])

    output = {
        "fuel_cost": round(data["header"]["summaries"][0]["consumption"], 2),
        "toll_cost": round(data["header"]["summaries"][0]["tollCost"]["car"]/100, 2),
        "total_cost": round(data["header"]["summaries"][0]["consumption"] + data["header"]["summaries"][0]["tollCost"]["car"]/100, 2),
        "distance_km": int(data["header"]["summaries"][0]["drivingDist"]/1000),
        "time":data["header"]["summaries"][0]["drivingTime"]
    }

    return output