import json

class Card():

    def __init__(self, card_name):
        record = self.get_record(card_name=card_name)

        self.card_name = record['cname']
        self.ability = record['ability']
        self.cost = record['cost']
        self.power = record['power']
        self.image = record['art']
        self.webpage = record['url']

    def get_record(self, card_name):
        # load the json file into memory
        with open("data/cards.json", "r") as json_file:
            data = json.load(json_file)

        # loop through each record in the data
        for record in data:
            # check if the record has the given cname
            if " ".join([word.capitalize() for word in record['cname'].replace("-", " ").split()]) == card_name:
                # found the record, print it
                return record

class Location():

    def __init__(self, loc_name):
        record = self.get_record(loc_name = loc_name)

        self.loc_name = record['Location']
        self.effect = record['Effect']

    def get_record(self, loc_name):
    # load the json file into memory
        with open("data/locations.json", "r") as json_file:
            data = json.load(json_file)

        # loop through each record in the data
        for record in data:
            # check if the record has the given cname
            if " ".join([word.capitalize() for word in record['Location'].replace("-", " ").split()]) == loc_name:
                # found the record, print it
                return record