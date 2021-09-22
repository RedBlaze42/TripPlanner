

class Covoit():
    
    def __init__(self, name, location, is_driver, capacity = 5):
        self.name = name
        self.location = location
        self.is_drisver = is_driver
        self.capacity = capacity
        
        if self.is_driver:
            self.passenger_names = list()
        else:
            self.driver_name = None
        
    def calculate_trip(self, matrix, passengers = None, key = "duration"):
        trip_sum = 0
        
        if passengers is None: passengers = self.passenger_names
        
        previous_step = self.name
        for passenger in passengers:
            trip_sum += matrix[previous_step][passenger][key]
            previous_step = passenger
            
        if "__end__" in matrix.keys():
            trip_sum += matrix[previous_step]["__end__"][key]
            
        return trip_sum

    def calculat_detour(self, matrix, passenger_name = None, key = "duration"):
        if not self.is_driver: return None
        
        if passenger_name is None:
            return self.calculate_trip(matrix, key = key) - self.calculate_trip(matrix, passengers = [] , key = key)
        else:
            temp_passengers = list(self.passenger_names)
            temp_passengers.remove(passenger_name)
            
            return self.calculate_trip(matrix, key = key) - self.calculate_trip(matrix, passengers = temp_passengers)