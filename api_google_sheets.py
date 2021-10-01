import gspread, json
import api_car
from datastores import Participant

def make_list_to_len(input_list, output_len):
    while len(input_list) < output_len:
        input_list.append([])
    return input_list

def set_row(row, value, index = 0):
    row = make_list_to_len(row, index + 1)
    row[index] = value
    return row

class TripPlanningSheet():
    
    def __init__(self, config_path = "config.json"):
        self.config_path = config_path
        with open(config_path, "r") as f:
            self.config = json.load(f)
        self.ranges = self.config["google_sheet"]["ranges"]
        
        self.gc = gspread.oauth(
            credentials_filename = "./credentials.json",
            authorized_user_filename = "./authorized_user.json"
        )

        self.file = self.gc.open_by_url(self.config["google_sheet"]["link"])
        self.sheet_calculs = self.file.worksheet("Calculs")
        self.sheet_participants = self.file.worksheet("Participants")
        self.sheet_results = self.file.worksheet("Résultats")
        self.sheet_result_model = self.file.worksheet("Gite_model")
        
        self.api_open_route = api_car.OpenRouteService(config_path = config_path)
        
    def auto_complete_locations(self):
        departure_cities = self.sheet_participants.batch_get([self.ranges["departure_cities"]], major_dimension = "ROWS")[0]
        cities_cache, cities_coords = self.sheet_calculs.batch_get([self.ranges["cities_cache"], self.ranges["cities_coords"]], major_dimension = "ROWS")
        cities_cache, cities_coords = make_list_to_len(cities_cache, len(departure_cities)), make_list_to_len(cities_coords, len(departure_cities))
        
        for i, city in enumerate(departure_cities):
            city = city[0]
            if len(cities_cache[i]) > 0 and city == cities_cache[i][0]: continue
            
            geocode = self.api_open_route.geocode(city)
            if geocode is None: continue
            cities_cache[i] = set_row(cities_cache[i], geocode["name"])
            cities_coords[i] = set_row(cities_coords[i], json.dumps(geocode["location"]))
            departure_cities[i] = set_row(departure_cities[i], geocode["name"])

        self.sheet_participants.batch_update([{"range": self.ranges["departure_cities"], "values": departure_cities}])
        self.sheet_calculs.batch_update([{"range": self.ranges["cities_cache"], "values": cities_cache}, {"range": self.ranges["cities_coords"], "values": cities_coords}])

    def get_participants(self):
        participant_array = self.sheet_participants.batch_get([self.ranges["participant_array"]], major_dimension = "ROWS", value_render_option = "FORMULA")
        coords_list = self.sheet_calculs.batch_get([self.ranges["cities_coords"]])[0]
        coords_list = [json.loads(coords[0]) for coords in coords_list]
        
        return [Participant(participant[0], participant[1], participant[2]+1, coords_list[i], participant[5]) for i, participant in enumerate(participant_array[0]) if participant[0]!=""]