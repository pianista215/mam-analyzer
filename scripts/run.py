#!/usr/bin/env python3
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mam_analyzer.evaluator import FlightEvaluator
from mam_analyzer.parser import load_flight_data

def main():
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <input_json> <output_json>")
        sys.exit(1)

    input_file = Path(sys.argv[1])
    output_file = Path(sys.argv[2])

    if not input_file.is_file():
        print(f"Error: input file '{input_file}' does not exist.")
        sys.exit(1)

    events = load_flight_data(input_file)
    evaluator = FlightEvaluator()

    report = evaluator.evaluate(events)

    try:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, indent=2)
        print(f"Flight report saved to '{output_file}'")
    except Exception as e:
        print(f"Error saving flight report: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
