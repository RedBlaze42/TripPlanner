import json, utils, time
from api_google_sheets import TripPlanningSheet
from possibility import Possibility
import api_gites, api_sncf, api_car
from tqdm import tqdm

class TripPlanner():

    def __init__(self, config_path = "config.json"):
        with open(config_path, "r") as f:
            self.config = json.load(f)

        self.possibilities = list()
        self.gites = None
        self.filtered_gites = None

        self.participants_last_loaded = 0
        self.sheet = TripPlanningSheet(config_path = config_path)

    def refresh_participants(self):
        self.participants_last_loaded = 0
        self.participants

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
        self.refresh_participants()
        self.possibilities = [Possibility(self.participants, gite) for gite in self.gites]

        return self.possibilities

    @property
    def total_budget(self):
        return sum([participant.budget for participant in self.participants])