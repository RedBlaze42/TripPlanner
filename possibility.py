from covoit_calculator import CovoitCalculator

class Possibility():
    def __init__(self, participants, gite):
        self.participants = participants
        self.gite = gite
        self._covoits, self._covoit_calculator = None, None
        self._solution_set = False

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
    
    @property
    def solution_set(self):
        if not self._solution_set:
            self.set_solution()
            self._solution_set = True
        
        return self._solution_set

    def set_solution(self):
        self.covoit_calculator.get_solution()
        self.covoit_calculator.convert_fartest_passengers_to_trains()
        self.covoit_calculator.get_solution()
        self.covoit_calculator.set_routes()
