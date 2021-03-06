from covoit_calculator import CovoitCalculator
from api_car import InvalidLocationError

class Possibility():
    def __init__(self, participants, gite, with_trains = True):
        self.participants = participants
        self.gite = gite
        self._covoits, self._covoit_calculator = None, None
        self._solution_set = False
        self._route_set = False
        self.invalid = False
        
        self.rejected = False
        self.sheet_id = None
        self.number = 0
        self.with_trains = with_trains

    def set_participants(self, participants):
        if not sorted(participants, key=lambda x: x.name) == sorted(self.participants, key=lambda x: x.name):
            self.participants = participants
            self._covoits, self._covoit_calculator = None, None
            self._solution_set = False
            self._route_set = False
            self.sheet_id = None

    @property
    def covoits(self):
        if self._covoits is None:
            self._covoits = {participant.name: participant.get_covoit(self.gite.location) for participant in self.participants}
        return self._covoits

    @property
    def covoit_calculator(self):
        if self._covoit_calculator is None:
            self._covoit_calculator = CovoitCalculator(self.covoits, self.gite.location)
        return self._covoit_calculator

    def set_solution(self):
        if not self._solution_set:
            if self.with_trains:
                self.covoit_calculator.get_solution()
                self.covoit_calculator.convert_fartest_passengers_to_trains()
            self.covoit_calculator.get_solution()
            self._solution_set = True

    def refresh_solution(self):
        self._covoits = None
        self._covoit_calculator = None
        self._solution_set = False
        self.set_solution()

    def set_routes(self):
        if not self._route_set:
            try:
                self.set_solution()
                self.covoit_calculator.set_routes()
            except InvalidLocationError as e:
                self.invalid = True
                self.rejected = True
                raise e
            else:
                self._route_set = True

    def refresh_routes(self):
        self._route_set = False
        self.set_routes()

    @property
    def total_trip_time(self):
        total_trip_time = 0
        self.set_solution()
        self.covoit_calculator.set_trip_times()
        for covoit in self.covoits.values():
            total_trip_time += covoit.trip_time
        return total_trip_time

    @property    
    def total_trip_cost(self):
        total_trip_cost = 0
        self.set_routes()
        for covoit in self.covoits.values():
            total_trip_cost += covoit.trip_cost
        return total_trip_cost

    @property
    def total_cost(self):
        return self.total_trip_cost + self.gite.price