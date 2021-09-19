from math import sin, cos, sqrt, atan2, radians

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