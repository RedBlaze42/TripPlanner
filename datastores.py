from dataclasses import dataclass


class Covoit():
    
    def __init__(self, name, location, is_driver, destination, capacity = 5):
        self.name = name
        self.location = location
        self.is_driver = is_driver
        self.destination = destination
        self.trip_cost = None
        self.trip_time = None
        
        if self.is_driver:
            self.capacity = capacity
            self.passenger_names = list()
            self.route = None
        else:
            self.driver_name = None

    def waypoints(self, covoits):
        if not self.is_driver: return None
        waypoints = [self.location,]
        waypoints += [covoits[passenger_name].location for passenger_name in self.passenger_names]
        waypoints.append(self.destination)

        return waypoints
        
    def calculate_trip(self, matrix, passengers = None, key = "duration", start_step = None):
        trip_sum = 0
        
        if passengers is None and self.is_driver: passengers = self.passenger_names
        
        previous_step = self.name if start_step is None else start_step
        for passenger in passengers:
            trip_sum += matrix[previous_step][passenger][key]
            previous_step = passenger
            
        if "__end__" in matrix.keys():
            trip_sum += matrix[previous_step]["__end__"][key]
            
        return trip_sum

    def calculate_detour(self, matrix, passenger_name = None, key = "duration"):
        if not self.is_driver: return None
        
        if passenger_name is None:
            return self.calculate_trip(matrix, key = key) - self.calculate_trip(matrix, passengers = [] , key = key)
        else:
            temp_passengers = list(self.passenger_names)
            temp_passengers.remove(passenger_name)
            
            return self.calculate_trip(matrix, key = key) - self.calculate_trip(matrix, passengers = temp_passengers)

    def set_trip_times(self, matrix, covoits):
        if not self.is_driver: return None
        
        self.trip_time = self.calculate_trip(matrix)

        for i, passenger_name in enumerate(self.passenger_names):
            covoits[passenger_name].trip_time = self.calculate_trip(matrix, self.passenger_names[i:], start_step = passenger_name)

    def set_trip_costs(self, matrix, covoits, total_cost):
        if not self.is_driver: return None

        total_distance = sum([matrix[passenger_name]["__end__"]["distance"] for passenger_name in self.passenger_names])
        total_distance += matrix[self.name]["__end__"]["distance"]
        
        self.trip_cost = (matrix[self.name]["__end__"]["distance"] / total_distance) * total_cost
        for passenger_name in self.passenger_names:
                covoits[passenger_name].trip_cost = (matrix[passenger_name]["__end__"]["distance"] / total_distance) * total_cost

    def __str__(self):
        output = str()
        for key, value in self.__dict__.items():
            if isinstance(value, str) or isinstance(value, int) or isinstance(value, float) and key[0] != "_":
                if not isinstance(value, str) or len(value) < 100:
                    output += "{}: {} ".format(key, value)
        
        return output

class TrainUser(Covoit):
    def __init__(self, name, departure_location, destination, train_station = None, station_radius = 20):
        self.departure_location = departure_location

        self._train_station = None
        super().__init__(name, None, False, destination)
        
        self.train_station = train_station
        self.station_radius = station_radius

    @property
    def train_station(self):
        return self._train_station

    @train_station.setter
    def train_station(self, train_station):
        if train_station is None: return
        self._train_station = train_station
        self.location = train_station["location"]

    @classmethod
    def from_covoit(cls, covoit):
        return cls(covoit.name, covoit.location, covoit.destination)

@dataclass
class Participant():
    name: str
    is_driver: bool
    capacity: int
    location: list
    budget: float

    def get_covoit(self, destination):
        return Covoit(self.name, self.location, self.is_driver, destination, capacity = self.capacity)