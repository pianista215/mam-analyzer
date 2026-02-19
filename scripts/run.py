#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mam_analyzer.evaluator import FlightEvaluator
from mam_analyzer.models.flight_context import FlightContext
from mam_analyzer.parser import load_flight_data

def main():
    parser = argparse.ArgumentParser(description="Analyze a MAM ACARS flight JSON file.")
    parser.add_argument("input_json", type=Path, help="Input flight JSON file")
    parser.add_argument("output_json", type=Path, help="Output report JSON file")
    parser.add_argument("--context", type=Path, default=None, help="Optional flight context JSON file")
    args = parser.parse_args()

    if not args.input_json.is_file():
        print(f"Error: input file '{args.input_json}' does not exist.")
        sys.exit(1)

    context = None
    if args.context is not None:
        if not args.context.is_file():
            print(f"Error: context file '{args.context}' does not exist.")
            sys.exit(1)
        with open(args.context, encoding="utf-8") as f:
            context = FlightContext.from_dict(json.load(f))

    input_file = args.input_json
    output_file = args.output_json

    events = load_flight_data(input_file)
    evaluator = FlightEvaluator()

    report = evaluator.evaluate(events, context=context)

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
