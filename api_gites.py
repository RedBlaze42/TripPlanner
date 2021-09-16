from bs4 import BeautifulSoup
import requests, re
from datetime import datetime, timedelta
from enum import Enum

BASE_URL = "https://www.gites-de-france.com"
BASE_SEARCH_URL = "https://www.gites-de-france.com/fr/search"
RESULTS_PER_PAGES = 20

class FilterOrder(Enum):
    ASC = 1
    DESC = -1

class Filters(Enum):
    GITE_DE_GROUPE = 0
    GITE = 1
    CHAMBRE_HOTE = 2
    #Piscine/Autre ?

class Regions(Enum):
    ILE_DE_FRANCE = (6, "Île-de-France")
    CENTRE_VAL_DE_LOIRE = (7, "Centre-Val de Loire")
    BOURGOGNE_FRANCHE_COMTE = (8, "Bourgogne-Franche-Comté")
    NORMANDIE = (9, "Normandie")
    HAUTS_DE_FRANCE = (10, "Hauts-de-France")
    GRAND_EST = (11, "Grand Est")
    PAYS_DE_LA_LOIRE = (12, "Pays de la Loire")
    BRETAGNE = (13, "Bretagne")
    NOUVELLE_AQUITAINE = (14, "Nouvelle-Aquitaine")
    OCCITANIE = (15, "Occitanie")
    AUVERGNE_RHONE_ALPES = (16, "Auvergne-Rhône-Alpes")
    PROVENCE_ALPES_COTE_DAZURE = (17, "Provence-Alpes-Côte d'Azur")

    
class GitesDeFrance():

    def __init__(self, region, checkin, checkout, travelers):
        self.checkin = datetime.strftime(checkin, "%Y-%m-%d") if isinstance(checkin, datetime) else checkin
        self.checkout = datetime.strftime(checkout, "%Y-%m-%d") if isinstance(checkout, datetime) else checkout
        if not isinstance(region, Regions): raise ValueError
        
        self.region = region
        self.travelers = travelers
        self.seed = None
        self._nb_results = None
        self.results = list()
        self.n = 0

    def __iter__(self, n = 0):
        self.n = n - 1
        return self

    def __next__(self):
        self.n += 1
        if self.n < self.nb_results:
            if self.n > len(self.results) - 1:
                page = (self.n + 1) // RESULTS_PER_PAGES
                self.results += self.get_result_page(page = page)
            return self.results[self.n]
        else:
            raise StopIteration

    def __len__(self):
        return self.nb_results

    @property
    def result_ids(self):
        return {result.id for result in self.results}

    @property
    def nb_results(self):
        if self._nb_results is not None: return self._nb_results

        soup = BeautifulSoup(self.get_page_html(page = 0), features = "html.parser")
        line = [line for line in soup.find_all("p") if "Résultat" in str(line)]
        if len(line) == 0: return 0
        
        self._nb_results = int(re.findall(r"(\d+) Résultats", str(line[0]))[0])
        return self._nb_results

    def get_page_html(self, page = 0):
        region_code, region_name = self.region.value
        params = {"destination": region_name, "regions": region_code, "page": page, "arrival": self.checkin, "departure": self.checkout, "travelers": self.travelers}
        if self.seed is not None: params["seed"] = self.seed

        req = requests.get(BASE_SEARCH_URL, params = params)

        req.raise_for_status()
        self.last_url = req.url
        if self.seed is None:
            try:
                self.seed = re.findall(r"seed=([a-zA-Z0-9]*)", req.url)[0]
            except IndexError:
                pass

        return req.content

    def get_result_page(self, page = 0):
        soup = BeautifulSoup(self.get_page_html(page = page), features = "html.parser")
        results = soup.find("section", id = "markup-tiles").select(".g2f-accommodationTile ")
        output = list()

        for result in results:
            gite = Gite(result)
            if gite.id not in self.result_ids:
                output.append(gite)
        
        return output

    def to_dict(self):
        output_dict = {
            "region": self.region.name,
            "checkin": self.checkin,
            "checkout": self.checkout,
            "travelers": self.travelers,
            "seed": self.seed,
            "n": self.n,
            "nb_results": self._nb_results,
            "results": [{"soup": result.soup, "location": result._location} for result in self.results]
        }
        return output_dict

    @classmethod
    def from_dict(cls, input_dict):
        obj = cls(Regions[input_dict["region"]], input_dict["checkin"], input_dict["checkout"], input_dict["travelers"])
        obj.seed = input_dict["seed"]
        obj.n = input_dict["n"]
        obj._nb_results = input_dict["nb_results"]
        for result in input_dict["results"]:
            gite = Gite(BeautifulSoup(result["soup"], features = "html.parser"))
            gite._location = result["location"]
            obj.results.append(gite)
        
        return obj

class Gite():

    def __init__(self, soup):
        self.soup = str(soup)
        self.link = BASE_URL + soup.find_all("a")[2]["href"]
        self.id = re.findall(r"-([a-z0-9]+)\?", self.link)[0]
        self.image = [BASE_URL + image["data-src"] if "data-src" in image.attrs.keys() else BASE_URL + image["src"] for image in soup.find_all("img")]
        self.title = soup.find("h2").text.strip()
        self.epis = len(soup.select(".g2f-levelEpis")[0].find_all("li")) if len(soup.select(".g2f-levelEpis")) > 0 else None
        self.location_name = soup.select(".g2f-accommodationTile-text-place")[0].text[2:]
        self.chambres, self.personnes = re.findall(r"(?:(\d+) chambres)?(?:\s|\\n)*(\d+) personnes", soup.select(".g2f-accommodationTile-text-capacity")[0].text.strip())[0]
        self.chambres, self.personnes = int(self.chambres) if self.chambres != "" else None, int(self.personnes)
        self._location = None
        self.note = float(soup.select(".g2f-rating-full")[0]["style"][12:16]) if len(soup.select(".g2f-rating-full")) > 0 else None

        price_soup = soup.select(".g2f-accommodationTile-text-price-new")[0]
        if len(price_soup.find_all("del")) > 0: price_soup = price_soup.find("strong")
        self.price = int("".join([charac for charac in price_soup.text.strip().split(",")[0] if charac.isdigit()]))

    @property
    def location(self):
        if self._location is not None: return self._location
        
        req = requests.get(self.link)
        req.raise_for_status()
        soup = BeautifulSoup(req.content, features = "html.parser")
        map_div = soup.find("div",id="map-accommodation")
        self._location = float(map_div["data-lat"]), float(map_div["data-lng"])

        return self._location

    def __str__(self):
        output = str()
        for key, value in self.__dict__.items():
            if isinstance(value, str) or isinstance(value, int) or isinstance(value, float) and key[0] != "_":
                if not isinstance(value, str) or len(value) < 100:
                    output += "{}: {} ".format(key, value)
        
        return output


if __name__ == "__main__":
    gites = GitesDeFrance(Regions.BOURGOGNE_FRANCHE_COMTE, datetime.now() + timedelta(days = 31), datetime.now() + timedelta(days = 31 + 7), 16)
    print(gites.nb_results)
    for gite in gites:
        print(gite)
    print(gites.last_url)