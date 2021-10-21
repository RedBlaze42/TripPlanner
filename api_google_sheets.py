import gspread, json, time
import api_car, utils, graphs
from api_gites import Filters
from datastores import Participant
from datetime import datetime
from math import ceil

def make_list_to_len(input_list, output_len, with_value = None):
    while len(input_list) < output_len:
        if with_value is None:
            input_list.append([])
        else:
            input_list.append(with_value)
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
        if "sftp_access" in self.config.keys():
            self.sftp_client = utils.SftpClient()
        else:
            self.sftp_client = None
        
    def auto_complete_locations(self):
        nb_participants_max = gspread.utils.a1_range_to_grid_range(self.ranges["departure_cities"])["endRowIndex"] - gspread.utils.a1_range_to_grid_range(self.ranges["departure_cities"])["startRowIndex"]
        departure_cities = make_list_to_len(self.sheet_participants.batch_get([self.ranges["departure_cities"]], major_dimension = "ROWS")[0], nb_participants_max)
        cities_cache, cities_coords = self.sheet_calculs.batch_get([self.ranges["cities_cache"], self.ranges["cities_coords"]], major_dimension = "ROWS")
        cities_cache, cities_coords = make_list_to_len(cities_cache, nb_participants_max), make_list_to_len(cities_coords, nb_participants_max)
        
        for i, city in enumerate(departure_cities):
            if len(city) == 0:
                cities_cache[i] = set_row(cities_cache[i], "")
                cities_coords[i] = set_row(cities_coords[i], "")
                continue
            
            city = city[0]
            if len(cities_cache[i]) > 0 and city == cities_cache[i][0]: continue
            
            geocode = self.api_open_route.geocode(city)
            if geocode is None: continue
            cities_cache[i] = set_row(cities_cache[i], geocode["name"])
            cities_coords[i] = set_row(cities_coords[i], json.dumps(geocode["location"]))
            departure_cities[i] = set_row(departure_cities[i], geocode["name"])

        self.sheet_participants.batch_update([{"range": self.ranges["departure_cities"], "values": departure_cities}])
        self.sheet_calculs.batch_update([{"range": self.ranges["cities_cache"], "values": (cities_cache)}, {"range": self.ranges["cities_coords"], "values": cities_coords}])

    def get_participants(self):
        self.auto_complete_locations()
        participant_array = self.sheet_participants.batch_get([self.ranges["participant_array"]], major_dimension = "ROWS", value_render_option = "FORMULA")[0]
        participant_array = [participant for participant in participant_array if len(participant) > 0]
        coords_list = self.sheet_calculs.batch_get([self.ranges["cities_coords"]])[0]
        coords_list = [json.loads(coords[0]) for coords in coords_list if len(coords) > 0]
        
        return [Participant(participant[0], participant[1], participant[2]+1, coords_list[i], participant[5]) for i, participant in enumerate(participant_array) if len(participant)>0 and participant[0]!=""]

    def get_filters(self):
        raw_filters = self.sheet_participants.batch_get([self.ranges["filters"]], major_dimension = "COLUMNS", value_render_option = "FORMULA")[0][0]
        filters = [Filters[self.config["google_sheet"]["filters"][i]] for i, value in enumerate(raw_filters) if isinstance(value, bool) and value]
        output = {
            "filters": filters,
            "max_beds_in_bedroom": raw_filters[9] if len(raw_filters) >= 10 else None
        }
        return output
    
    def get_dates(self):
        date_range = self.sheet_participants.batch_get([self.ranges["dates"]])[0]
        return datetime.strptime(date_range[0][0], "%Y-%m-%d"), datetime.strptime(date_range[1][0], "%Y-%m-%d")

    def delete_rejected(self, possibilities):
        ranges = list()
        keys = list()
        for possibility in possibilities:
            if possibility.sheet_id is not None:
                keys.append(possibility)
                worksheet = self.file.get_worksheet_by_id(possibility.sheet_id)
                ranges.append(gspread.utils.absolute_range_name(worksheet.title, self.ranges["result_reject"]))

        response = self.file.values_batch_get(ranges)
        for i, line in enumerate(response.get("valueRanges", [])):
            if "values" in line.keys() and line["values"][0][0] == "TRUE":
                keys[i].rejected = True

        for possibility in possibilities:
            if possibility.rejected and possibility.sheet_id is not None:
                worksheet = self.file.get_worksheet_by_id(possibility.sheet_id)
                self.file.del_worksheet(worksheet)
                possibility.sheet_id = None
    
    def print_results(self, possibilities, nb_results):
        for possibility in possibilities:
            if not possibility.rejected:
                self.print_result(possibility)
        
        grid_range = gspread.utils.a1_range_to_grid_range(self.ranges["results"])
        column_number = grid_range["endColumnIndex"]-grid_range["startColumnIndex"]
        
        rejected_grid_range = gspread.utils.a1_range_to_grid_range(self.ranges["rejected_results"])
        rejected_results_number = rejected_grid_range["endRowIndex"]-rejected_grid_range["startRowIndex"]
        rejected_results = [possibility for possibility in possibilities if possibility.rejected][:rejected_results_number]
        rejected_results = sorted(rejected_results, key=lambda p: p.number)
        
        results_number = grid_range["endRowIndex"]-grid_range["startRowIndex"]
        results = [possibility for possibility in possibilities if not possibility.rejected][:results_number]
        results = sorted(results, key=lambda p: p.number)
        
        results_array = [self.get_result_line(possibility) for possibility in results]
        results_array = make_list_to_len(results_array, results_number, with_value = [""]*column_number)
        rejected_results_array = [self.get_result_line(possibility) for possibility in rejected_results]
        rejected_results_array = make_list_to_len(rejected_results_array, rejected_results_number, with_value = [""]*column_number)
        
        updates = [
            {"range": self.ranges["results"], "values": results_array},
            {"range": self.ranges["rejected_results"], "values": rejected_results_array},
            {"range": self.ranges["nb_results"], "values": [[nb_results]]}
        ]
        if self.sftp_client is not None:
            results_map = self.get_results_map_links([result.gite for result in results], list(results[0].covoits.values()))
            results_map_values = [['=HYPERLINK("{}";"Carte interactive")'.format(results_map["html"])],['=IMAGE("{}")'.format(results_map["png"])]]
            updates.append({"range": self.ranges["results_map"], "values": results_map_values})
            
        self.sheet_results.batch_update(updates, value_input_option = "USER_ENTERED")
        
    def get_results_map_links(self, gites, participants):
        fig = graphs.map_gites(gites, {participant.name: participant.location for participant in participants})
        fig[0].write_image("results_map.png")
        with open("results_map.html", "w") as f: f.write(fig[1])
        output = {
            "png":self.sftp_client.upload_file("results_map.png"),
            "html":self.sftp_client.upload_file("results_map.html")
        }
        return output
    
    def get_result_map_links(self, possibility):
        possibility.set_routes()
        fig = graphs.covoit_route(possibility.covoits)
        base_path = "result_{}".format(possibility.number)
        png_path, html_path = base_path + ".png", base_path + ".html"
        fig.write_image(png_path)
        fig.write_html(html_path)
        output = {
            "png":self.sftp_client.upload_file(png_path),
            "html":self.sftp_client.upload_file(html_path)
        }
        return output
        
    def get_result_line(self, possibility):
        output = [
            possibility.number,
            possibility.gite.location_name,
            possibility.gite.bedrooms if possibility.gite.bedrooms is not None else "?",
            possibility.gite.beds,
            possibility.total_cost / len(possibility.participants),
            possibility.total_trip_time / 86400 / len(possibility.covoits),
            '=HYPERLINK("#gid={}";"Détails")'.format(possibility.sheet_id) if not possibility.rejected else '=HYPERLINK("{}";"Lien")'.format(possibility.gite.link)
        ]
        return output
    
    def print_result(self, possibility):
        header = {"range":self.ranges["result_header"],"major_dimension":"COLUMNS","values":[[
            possibility.number,
            possibility.gite.title,
            possibility.total_cost / len(possibility.participants), "",
            possibility.total_trip_time / 86400 / len(possibility.covoits),
            possibility.gite.bedrooms if possibility.gite.bedrooms is not None else "?",
            possibility.gite.beds,
            '=HYPERLINK("{}";"{}")'.format("https://www.google.com/maps/search/?api=1&query={},{}&basemap=satellite&zoom=19".format(possibility.gite.location[0], possibility.gite.location[1]), possibility.gite.location_name),
            ceil(len(possibility.covoits)/possibility.gite.bedrooms) if possibility.gite.bedrooms is not None else "?"
        ]]}
        images = [{"range": self.ranges["result_images"][i], "values": [['=IMAGE("{}")'.format(image)]]} for i, image in enumerate(possibility.gite.images[:len(self.ranges["result_images"])])]
        link = {"range": self.ranges["result_link"], "values":[['=HYPERLINK("{}";"Lien")'.format(possibility.gite.link)]]}
        participants = {
            "range": self.ranges["result_participants"],
            "values":[[participant.name, possibility.gite.price/len(possibility.covoits), participant.trip_cost, participant.trip_time/86400] for participant in possibility.covoits.values()]
        }
        nb_drivers_max = gspread.utils.a1_range_to_grid_range(self.ranges["result_covoits"])["endRowIndex"] - gspread.utils.a1_range_to_grid_range(self.ranges["result_covoits"])["startRowIndex"]
        drivers = sorted([covoit for covoit in possibility.covoits.values() if covoit.is_driver], key = lambda x: len(x.passenger_names), reverse = True)[:nb_drivers_max]
        covoit_values = [[covoit.name]+[""]*9 for covoit in drivers]
        for row in covoit_values:
            driver = possibility.covoits[row[0]]
            for i, passenger_name in enumerate(driver.passenger_names):
                row[i*2+1] = passenger_name
                row[i*2+1+1] = driver.calculate_detour(possibility.covoit_calculator.matrix, passenger_name = passenger_name) / 86400
            row[9] = driver.calculate_detour(possibility.covoit_calculator.matrix) / 86400
        
        covoits = {
            "range": self.ranges["result_covoits"],
            "values": make_list_to_len(covoit_values, nb_drivers_max, with_value = [""]*10)
        }
        
        if self.sftp_client is not None:
            map_result_links = self.get_result_map_links(possibility)
            map_result = {
                "range": self.ranges["result_map"],
                "values": [['=HYPERLINK("{}";"Carte des déplacements")'.format(map_result_links["html"])],['=IMAGE("{}")'.format(map_result_links["png"])]]
            }
        
        updates = [header, link, participants, covoits]
        if self.sftp_client is not None:
            updates.append(map_result)
        updates += images
        
        if possibility.sheet_id is None:
            result_sheet = self.file.duplicate_sheet(self.sheet_result_model.id, insert_sheet_index = len(self.file.worksheets()), new_sheet_name = "Gîte {}".format(possibility.number))
            possibility.sheet_id = result_sheet.id
        
        self.file.get_worksheet_by_id(possibility.sheet_id).batch_update(updates, value_input_option = "USER_ENTERED")
        
    def clear_results(self):
        for worksheet in self.file.worksheets():
            if "Gîte " in worksheet.title:
                self.file.del_worksheet(worksheet)
                
        self.sheet_results.batch_clear([
            self.ranges["results"],
            self.ranges["results_map"],
            self.ranges["nb_results"],
            self.ranges["rejected_results"],
        ])