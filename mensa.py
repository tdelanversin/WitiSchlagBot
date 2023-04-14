import datetime
import json
import urllib.request
from bs4 import BeautifulSoup


def get_meals(name):
    return get_mensa(name).get_meals()


def get_mensa(name):
    for mensa in available:
        if mensa.has_alias(name):
            return mensa


MEALTIME_SWITCH = 14  # 14:00


class Meal:
    label = "No label"
    price_student = "Not available."
    price_staff = "Not available."
    price_extern = "Not available."
    description = []

    def __str__(self):
        """
        to String Method
        :return:
        """
        out = "{} (STUD:{} STAFF:{} EXTERN:{})".format(self.label, self.price_student, self.price_staff, self.price_extern)
        for description in self.description:
            out = out + "\n\t{}".format(description)
        return out


class Mensa:
    name = "Not available."
    aliases = []

    def get_meals(self):
        """
        Returns list of menu objects of meuns that are available
        """
        return []

    # Checks if Mensa could be called that name
    def has_alias(self, alias):
        return alias.lower() in self.aliases or alias.lower() == self.name.lower()


# ETH Mensa
class ETHMensa(Mensa):
    api_name = ""  # the name used in the ETH api (has to be defined by the inheriting class)
    opening = ""
    closing = ""

    def get_meals(self):
        menus = []
        try:
            date = datetime.datetime.now().strftime("%Y-%m-%d")
            mealtime = "lunch" if datetime.datetime.now().hour < MEALTIME_SWITCH else "dinner"
            url = "https://www.webservices.ethz.ch/gastro/v1/RVRI/Q1E1/meals/en/{}/{}".format(date, mealtime)
            with urllib.request.urlopen(url) as request:
                mensas = json.loads(request.read().decode())


            for mensa in mensas:
                if mensa["mensa"] == self.api_name:
                    self.opening = mensa['hours']['mealtime'][0]["from"]
                    self.closing = mensa['hours']['mealtime'][0]["to"]
                    for meal in mensa["meals"]:
                        menu = Meal()
                        menu.label = meal['label']
                        menu.price_student = meal['prices']['student']
                        menu.price_staff = meal['prices']['staff']
                        menu.price_extern = meal['prices']['extern']
                        menu.description = meal['description']
                        menus.append(menu)
            return menus
        except Exception as e:
            print(e)
            return menus  # we failed, but let's pretend nothing ever happened


class UniMensa(Mensa):
    api_name = ""  # the name used on the UNI website (has to be defined by the inheriting class)

    tage = ["montag", "dienstag", "mittwoch", "donnerstag", "freitag", "samstag", "sonntag"]

    def get_meals(self):
        day = self.tage[datetime.datetime.today().weekday()]  # current day
        url = "https://www.mensa.uzh.ch/de/menueplaene/{}/{}.html".format(self.api_name, day)

        try:
            with urllib.request.urlopen(url) as request:
                raw_data = request.read().decode("utf8")
                
            soup = BeautifulSoup(raw_data, "html.parser")
            menu_holder = soup.find("div", {"class": "newslist-description"})

            lines = menu_holder.text.split("\n")
        except Exception as e:
            print(e)
            return []

        menus = []
        i = 0
        # Loop until there are no menus left
        while True:
            try:
                # find next menu
                while i < len(lines) and " | " not in lines[i]:
                    i += 1
                # check if we found menu or hit end
                if i < len(lines):
                    # very ugly html parsing for a very ugly html site :/
                    menu = Meal()
                    menu.label = lines[i].split(" | ")[0]
                    prices = lines[i].split(" | ")[1].split(" / ")

                    menu.price_student = prices[0].replace("CHF", "").replace(" ", "")
                    menu.price_staff = prices[1].replace("CHF", "").replace(" ", "")
                    menu.price_extern = prices[2].replace("CHF", "").replace(" ", "")

                    menu.description = lines[i + 1].split("  ")
                    menus.append(menu)
                    i += 1
                # return what we've found when we hit the end
                else:
                    return menus
            except Exception as e:
                print(e)
                # If anything bad happens just ignore it. Just like we do in real life.
                return menus


class Polymensa(ETHMensa):
    aliases = ["poly", "polymensa", "polyterrasse", "mensa polyterrasse"]
    name = "Mensa Polyterrasse"
    api_name = "Mensa Polyterrasse"


class FoodLab(ETHMensa):
    aliases = ["foodlab", "food lab", "food&lab"]
    name = "Food&Lab"
    api_name = "food&lab"


class Clausiusbar(ETHMensa):
    aliases = ["clausius", "clausiusbar", "lausiusbar", "lausius"]
    name = "Causiusbar"
    api_name = "Clausiusbar"


class Polysnack(ETHMensa):
    aliases = ["polysnack", "snack"]
    name = "Polysnack"
    api_name = "Polysnack"


class Foodtrailer(ETHMensa):
    aliases = ["foodtrailer", "trailer", "trailerburger"]
    name = "Trailerburger"
    api_name = "Foodtrailer ETZ"


class AlumniLounge(ETHMensa):
    aliases = ["alumni", "alumnilounge", "alumni lounge"]
    name = "Alumni quattro Lounge"
    api_name = "Alumni quattro Lounge"


class Bellavista(ETHMensa):
    aliases = ["bellavista", "bella vista"]
    name = "Bellavista"
    api_name = "BELLAVISTA"


class FusionMeal(ETHMensa):
    aliases = ["fusion", "fusionmeal", "fusion meal"]
    name = "Fusion Meal"
    api_name = "FUSION meal"


class GessBar(ETHMensa):
    aliases = ["gess", "gessbar", "g-essbar", "essbar"]
    name = "G-ESSbar"
    api_name = "G-ESSbar"


class Tannenbar(ETHMensa):
    aliases = ["tanne", "tannenbar", "tannen bar"]
    name = "Tannenbar"
    api_name = "Tannenbar"


class Dozentenfoyer(ETHMensa):
    aliases = ["dozentenfoyer", "dozenten", "foyer", "dozenten foyer"]
    name = "Dozentenfoyer"
    api_name = "Dozentenfoyer"


class Platte(UniMensa):
    aliases = ["platte", "plattestross", "plattenstrasse", "plattestrass"]
    name = "Plattenstrasse"
    api_name = "cafeteria-uzh-plattenstrasse"


class Raemi59(UniMensa):
    aliases = ["raemi", "rämi", "rämi59", "raemi59", "rämi 59", "raemi 59", "raemistrasse", "rämistrasse", "rämistross"]
    name = "Rämi 59"
    api_name = "raemi59"


class UZHMercato(UniMensa):
    aliases = ["uniunten", "mercato", "uni-unten", "uni unten"]
    name = "UZH Mercato"
    api_name = "zentrum-mercato"


class UZHMercatoAbend(UniMensa):
    aliases = ["uniuntenabend", "mercato abend", "uni-unten-abend", "uni unten abend"]
    name = "UZH Mercato"
    api_name = "zentrum-mercato-abend"


class UZHZentrum(UniMensa):
    aliases = ["unioben", "zentrum", "uni", "uzh zentrum", "uzhzentrum"]
    name = "UZH Zentrum"
    api_name = "zentrum-mensa"


class UZHZentrumAllgemein(UniMensa):
    aliases = ["uni"]
    name = "UZH Zentrum"

    def get_meals(self):
        if datetime.datetime.now().hour < MEALTIME_SWITCH:
            self.api_name = "zentrum-mensa"
        else:
            self.api_name = "zentrum-mercato-abend"
        return super().get_meals()


class UZHLichthof(UniMensa):
    aliases = ["lichthof", "rondell"]
    name = "UZH Lichthof"
    api_name = "lichthof-rondell"


class Irchel(UniMensa):
    aliases = ["irchel", "irchel mensa", "irchelmensa"]
    name = "UZH Irchel"
    api_name = "mensa-uzh-irchel"


class IrchelAtrium(UniMensa):
    aliases = ["atrium", "irchel atrium"]
    name = "UZH Irchel Atrium"
    api_name = "irchel-cafeteria-atrium"


class Binzmühle(UniMensa):
    aliases = ["binzmuehle", "binzmühle"]
    name = "UZH Binzmühle"
    api_name = "mensa-uzh-binzmuehle"


class Cityport(UniMensa):
    aliases = ["cityport"]
    name = "UZH Cityport"
    api_name = "mensa-uzh-cityport"


class Zahnmedizin(UniMensa):
    aliases = ["zahnmedizin", "zzm"]
    name = "UZH Zahnmedizin"
    api_name = "cafeteria-zzm"


class Tierspital(UniMensa):
    aliases = ["tierspital"]
    name = "UZH Tierspital"
    api_name = "cafeteria-uzh-tierspital"


class BotanischerGarten(UniMensa):
    aliases = ["botanischergarten", "botanischer garten", "garten", "botgarten"]
    name = "UZH Botanischer Garten"
    api_name = "cafeteria-uzh-botgarten"


available = [Polymensa(), FoodLab(), Clausiusbar(), Polysnack(), Foodtrailer(), AlumniLounge(),
             Bellavista(), FusionMeal(), GessBar(), Tannenbar(), Dozentenfoyer(), Platte(),
             Raemi59(), UZHMercato(), UZHZentrum(), UZHLichthof(), Irchel(), IrchelAtrium(), Binzmühle(),
             Cityport(), Zahnmedizin(), Tierspital(), BotanischerGarten(), UZHZentrumAllgemein()]
