import api_car, api_sncf
from datastores import TrainUser
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp

class CovoitCalculator():
    
    def __init__(self, covoits, destination, key = "duration"):
        self.covoits = covoits
        self.key = key
        self._api_sncf = None        
        self.last_matrix_destinations, self.last_matrix = None, None
        
        self.api_ors = api_car.OpenRouteService()
        self.api_michelin = api_car.Michelin()
        self.destination = destination
        self.set_destinations(self.covoits)

    @property
    def drivers(self):
        return {name: covoit for name, covoit in self.covoits.items() if covoit.is_driver}

    def set_destinations(self, covoits):
        self.destinations = {covoit_name: covoit.location for covoit_name, covoit in covoits.items() if covoit.location is not None}
        self.destinations["_end"] = self.destination

        for covoit_name, covoit in covoits.items():
            covoit.destination = self.destination
    
    @property
    def matrix(self):
        if self.last_matrix_destinations != self.destinations:
            self.last_matrix = self.api_ors.matrix(self.destinations)
            self.last_matrix_destinations = dict(self.destinations)
            
        return self.last_matrix

    def crop_last_matrix(self, remove_names):
        if self.last_matrix is None: self.matrix

        self.set_destinations({covoit_name: covoit for covoit_name, covoit in self.covoits.items() if not covoit_name in remove_names})

        for key_row, row in list(self.last_matrix.items()):
            if key_row in remove_names:
                self.last_matrix.pop(key_row)
            else:
                for key_column, column in list(row.items()):
                    if key_column in remove_names:
                        self.last_matrix[key_row].pop(key_column)
        
        self.last_matrix_destinations = self.destinations

    def get_solution(self, ignore_trains = False, max_compute_time = 1):
        if not ignore_trains:
            self.set_destinations(self.covoits)
        else:
            self.set_destinations({covoit_name: covoit for covoit_name, covoit in self.covoits.items() if not isinstance(covoit, TrainUser)})
        
        names_ids, ids_names, matrix_for_ortools = self.get_matrix_from_key()
        data = {
            "distance_matrix": matrix_for_ortools,
            "num_vehicles":len(self.drivers),
            "starts": [ids_names[driver_name] for driver_name, driver in self.drivers.items()],
            "ends": [ids_names["_end"] for _ in range(len(self.drivers))],
            "vehicle_capacities": [driver.capacity for driver_name, driver in self.drivers.items()],
            "demands": [1 if i < len(self.matrix)-1 else 0 for i in range(len(self.matrix))]
        }
        manager = pywrapcp.RoutingIndexManager(len(data['distance_matrix']), data['num_vehicles'], data['starts'], data['ends'])
        routing = pywrapcp.RoutingModel(manager)

        def distance_callback(from_index, to_index):
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            return data['distance_matrix'][from_node][to_node]
            
        transit_callback_index = routing.RegisterTransitCallback(distance_callback)
        routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

        cost_dimension_name = "Cost"
        routing.AddDimension(transit_callback_index, 0, 35*3600, True, cost_dimension_name)
        cost_dimension = routing.GetDimensionOrDie(cost_dimension_name)
        cost_dimension.SetGlobalSpanCostCoefficient(100)

        def demand_callback(from_index):
            from_node = manager.IndexToNode(from_index)
            return data['demands'][from_node]
        
        demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)
        routing.AddDimensionWithVehicleCapacity(demand_callback_index, 0, data['vehicle_capacities'], True, 'Capacity')

        search_parameters = pywrapcp.DefaultRoutingSearchParameters()
        search_parameters.first_solution_strategy = (routing_enums_pb2.FirstSolutionStrategy.GLOBAL_CHEAPEST_ARC)
        search_parameters.local_search_metaheuristic = (routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH)
        search_parameters.time_limit.seconds = max_compute_time

        solution = routing.SolveWithParameters(search_parameters)
        if solution is None: raise LookupError("No solution found {}".format(routing.status()))
        for vehicle_id in range(data['num_vehicles']):
            index = routing.Start(vehicle_id)
            driver = self.covoits[names_ids[manager.IndexToNode(index)]]
            driver.passenger_names = list()
            while not routing.IsEnd(index):
                index = solution.Value(routing.NextVar(index))
                if names_ids[manager.IndexToNode(index)] == "_end":
                    break
                driver.passenger_names.append(names_ids[manager.IndexToNode(index)])
            
        return self.covoits
    
    @property
    def api_sncf(self):
        if self._api_sncf is None:
            self._api_sncf = api_sncf.TrainStations()
        return self._api_sncf

    def get_matrix_from_key(self):
        source = self.matrix
        name_list = list(source.keys())
        name_list += [name_list.pop(name_list.index("_end"))]
        
        names_ids = {i: name for i, name in enumerate(name_list)}
        ids_names = {name: i for i, name in enumerate(name_list)}
        
        matrix = [[list() for i in names_ids.keys()] for i in names_ids.keys()]
        
        for i in range(len(matrix)):
            for j in range(len(matrix[i])):
                if i == j:
                    matrix[i][j] = 0
                else:
                    matrix[i][j] = int(source[names_ids[i]][names_ids[j]][self.key])
        
        return names_ids, ids_names, matrix

    def set_train_stations(self):
        if not any([isinstance(covoit, TrainUser) for covoit in self.covoits.values()]):
            return self.covoits
        self.get_solution(ignore_trains = True)

        route_list = [driver.waypoints(self.covoits) for driver in self.drivers.values() if len(driver.passenger_names) < driver.capacity - 1]
        directions = self.api_michelin.directions_multithreaded(route_list)
        segments = [segment["points"] for segment in directions]

        train_users = {covoit_name: covoit for covoit_name, covoit in self.covoits.items() if isinstance(covoit, TrainUser)}

        for train_user_name, train_user in train_users.items():
            stations = self.api_sncf.get_connected_stations_from_radius(train_user.departure_location, train_user.station_radius)
            train_user.train_station = api_sncf.get_closest_station_to_segment(train_user.departure_location, stations, segments)

        return self.covoits

    def set_routes(self):
        for driver in self.drivers.values():
            self.api_ors.set_driver_route(driver, self.covoits)
        
        self.set_trip_times()

        directions = self.api_michelin.directions_multithreaded([driver.waypoints(self.covoits) for driver in self.drivers.values()])
        for i, driver in enumerate(self.drivers.values()):
            driver.set_trip_costs(self.matrix, self.covoits, directions[i]["total_cost"])

    def set_trip_times(self):
        for driver in self.drivers.values():
            driver.set_trip_times(self.matrix, self.covoits)

    def get_fartest_passengers(self, detour_limit = 2*3600):
        output = list()
        for driver_name, driver in self.drivers.items():

            for passenger in driver.passenger_names:
                detour = driver.calculate_detour(self.matrix, passenger_name = passenger)
                if detour > detour_limit and len(self.api_sncf.get_stations_in_radius(self.covoits[passenger].location, 30)) > 0:
                    output.append(passenger)

        return output

    def convert_fartest_passengers_to_trains(self, detour_limit = 2*3600):
        fartest_passengers = self.get_fartest_passengers(detour_limit = detour_limit)

        for passenger in fartest_passengers:
            self.covoits[passenger] = TrainUser.from_covoit(self.covoits[passenger])

        self.crop_last_matrix(fartest_passengers)
        self.set_train_stations()
        return self.covoits