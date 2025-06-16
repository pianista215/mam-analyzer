import json

def load_flight_data(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)