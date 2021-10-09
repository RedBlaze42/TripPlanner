import json, utils, time
from api_google_sheets import TripPlanningSheet
from possibility import Possibility
import api_gites, api_sncf, api_car
from tqdm import tqdm

class TripPlanner():

    def __init__(self, config_path = "config.json"):
        with open(config_path, "r") as f:
            self.config = json.load(f)

        self.possibilities = None
        self.gites = None
        self.filtered_gites = None

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
            self.possibilities = [Possibility(self.participants, gite) for gite in self.get_gites()]
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
        possibilities = [p for p in self.possibilities if p.sheet_id is None and not p.rejected]
        possibilities_showed = [p for p in self.possibilities if p.sheet_id is not None]
        if len(possibilities) + len(possibilities_showed) == 0: return []

        price_filtered = sorted(possibilities, key = lambda p: p.gite.price)[:price_filter_number]
        distance_filtered = sorted(price_filtered, key = lambda p: p.total_trip_time)[:output_number]
        next_index = max([p.number for p in self.possibilities if p.sheet_id is not None]) + 1 if len([1 for p in self.possibilities if p.sheet_id is not None]) > 0 else 1
        
        for possibility in distance_filtered:
            possibility.number = next_index
            next_index += 1

        return possibilities_showed + distance_filtered

    @property
    def rejected_possibilities(self):
        if self.possibilities is None or len(self.possibilities) == 0: return None
        
        return [p for p in self.possibilities if p.rejected]

    def refresh_results(self, restults_number = 10):
        raise NotImplementedError