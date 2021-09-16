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
    seed = None
    _nb_results = None

    def __init__(self, region, checkin, checkout, travelers):
        self.checkin = datetime.strftime(checkin, "%Y-%m-%d") if isinstance(checkin, datetime) else checkin
        self.checkout = datetime.strftime(checkout, "%Y-%m-%d") if isinstance(checkout, datetime) else checkout
        if not isinstance(region, Regions): raise ValueError
        
        self.region = region
        self.travelers = travelers

    def __iter__(self):
        self.n = 0
        self.cache = list()
        return self

    def __next__(self):
        self.n += 1
        if self.n < self.nb_results:
            if self.n >= len(self.cache):
                page = (self.n + 1) // RESULTS_PER_PAGES
                self.cache += self.get_result_page(page = page)
            return self.cache[self.n]

    def __len__(self):
        return self.nb_results

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
            output.append(Gite(result))
        
        return output

class Gite():


    def __init__(self, soup):
        self.soup = str(soup)
        self.link = BASE_URL + soup.find_all("a")[2]["href"]
        self.id = re.findall(r"-([a-z0-9]+)\?", self.link)[0]
        self.image = [BASE_URL + image["data-src"] if "data-src" in image.attrs.keys() else BASE_URL + image["src"] for image in soup.find_all("img")]
        self.price = int("".join([charac for charac in soup.select(".g2f-accommodationTile-text-price-new")[0].text.strip() if charac.isdigit()]))
        self.title = soup.find("h2").text.strip()
        self.epis = len(soup.select(".g2f-levelEpis")[0].find_all("li")) if len(soup.select(".g2f-levelEpis")) > 0 else None
        self.location_name = soup.select(".g2f-accommodationTile-text-place")[0].text[2:]
        self.chambres, self.personnes = re.findall(r"(?:(\d+) chambres)?(?:\s|\\n)*(\d+) personnes", soup.select(".g2f-accommodationTile-text-capacity")[0].text.strip())[0]
        self.note = float(soup.select(".g2f-rating-full")[0]["style"][12:16]) if len(soup.select(".g2f-rating-full")) > 0 else None

    def __str__(self):
        output = str()
        for key, value in self.__dict__.items():
            if isinstance(value, str) or isinstance(value, int) or isinstance(value, float) and key[0] != "_":
                output += "{}: {} ".format(key, value)
        
        return output


if __name__ == "__main__":
    gites = GitesDeFrance(Regions.BRETAGNE, datetime.now() + timedelta(days = 31), datetime.now() + timedelta(days = 31 + 7), 4)
    print(gites.nb_results)
    for gite in gites:
        print(gite)