from src.mam_analyzer.parser import load_flight_data
from src.mam_analyzer.phases import detect_phases

data = load_flight_data("data/UHSH-UHMM-B350.json")
phases = detect_phases(data)

print("Fases detectadas:")
for p in phases:
    print(f"- {p}")