import json, utils, time, pickle
from api_google_sheets import TripPlanningSheet
from possibility import Possibility
import api_gites, api_sncf, api_car
from tqdm import tqdm

class TripPlanner():

    def __init__(self, config_path = "config.json"):
        self.config_path = config_path
        with open(config_path, "r") as f:
            self.config = json.load(f)
            
        self.possibilities = None
        self.gites = None
        self.filtered_gites = None

        self.with_trains = True

        self.participant_cache = set()
        self.participants_last_loaded = 0
        self.sheet = TripPlanningSheet(config_path = config_path)

    def refresh_participants(self):
        self.participants_last_loaded = 0
        return self.participants

    @property
    def participants(self):
        if time.time() - self.participants_last_loaded > 120:
            self._participants = self.sheet.get_participants()
            self.participants_last_loaded = time.time()
        
        return self._participants

    @property
    def nb_participants(self):
        return len(self.participants)

    def fetch_cache(self):
        api_sncf.TrainStations()
        utils.GeoCoder()

    def get_gites(self):
        dates = self.sheet.get_dates()
        filters = self.sheet.get_filters()
        self.refresh_participants()
        
        self.gites = api_gites.GitesDeFrance(dates[0], dates[1], self.nb_participants, filters = filters["filters"])

        self.filtered_gites = list()
        total_budget = self.total_budget
        min_price = self.config["min_price"] * self.nb_participants * (self.gites.checkout_datetime - self.gites.checkin_datetime).total_seconds()/86400
        for gite in tqdm(self.gites):
            if min_price < gite.price < total_budget:
                if filters["max_beds_in_bedroom"] is None or self.nb_participants is None or (gite.bedrooms is not None and self.nb_participants / gite.bedrooms >= filters["max_beds_in_bedroom"]):
                    self.filtered_gites.append(gite)
        
        return self.filtered_gites

    def refresh_possibilities(self):
        participants = self.refresh_participants()
        if self.possibilities is None or len(self.possibilities) == 0:
            self.possibilities = [Possibility(self.participants, gite, with_trains = self.with_trains) for gite in self.get_gites()]
        else:
            for possibility in self.possibilities:
                possibility.set_participants(participants)

        return self.possibilities

    @property
    def total_budget(self):
        return sum([participant.budget for participant in self.participants])

    def filter_possibilities(self, output_number = 10, price_filter_number = 50):
        if self.possibilities is None:
            self.refresh_possibilities()
        possibilities_showed = [p for p in self.possibilities if p.sheet_id is not None]

        price_filtered = list()
        while len(price_filtered) < price_filter_number:
            filtered_possibilities = [p for p in sorted(self.possibilities, key = lambda p: p.gite.price) if not p in price_filtered and p.sheet_id is None and not p.rejected]
            if len(filtered_possibilities) > 0:
                if utils.is_in_france(filtered_possibilities[0].gite.location):
                    price_filtered.append(filtered_possibilities[0])
                else:
                    self.possibilities.remove(filtered_possibilities[0])
            else:
                break
        
        if len(price_filtered) + len(possibilities_showed) == 0: return []
                
        distance_filtered = sorted(price_filtered, key = lambda p: p.total_trip_time)[:output_number - len(possibilities_showed)]
        next_index = max([p.number for p in self.possibilities if p.number > 0]) + 1 if len([1 for p in self.possibilities if p.number > 0]) > 0 else 1
        
        for possibility in distance_filtered:
            possibility.number = next_index
            next_index += 1

        return possibilities_showed + distance_filtered

    @property
    def rejected_possibilities(self):
        if self.possibilities is None or len(self.possibilities) == 0: return None
        
        return [p for p in self.possibilities if p.rejected and not p.invalid]

    def refresh_results(self, **kwargs):
        self.sheet.delete_rejected(self.possibilities)
        filtered_possibilities = self.filter_possibilities(**kwargs)
        for possibility in filtered_possibilities:
            try:
                possibility.set_routes()
            except api_car.InvalidLocationError:
                continue
        self.sheet.print_results(filtered_possibilities + self.rejected_possibilities, len(self.possibilities))
        
    def to_file(self, file_name):
        output = {
            "config_path": self.config_path,
            "possibilities": self.possibilities,
            "gites": self.gites,
            "filtered_gites": self.filtered_gites
        }
        with open(file_name, 'wb') as f:
            pickle.dump(output, f)
    
    @classmethod
    def from_file(cls, file_name):
        with open(file_name, 'rb') as f:
            data = pickle.load(f)
            
        output = cls(data["config_path"])
        output.possibilities = data["possibilities"]
        output.gites = data["gites"]
        output.filtered_gites = data["filtered_gites"]
        
        return output
        
    def reset_gites(self):
        self.possibilities = None
        self.refresh_possibilities()
        self.sheet.clear_results()