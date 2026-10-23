"""One anonymous sample per isolated process; never imports builder/scorer."""
import argparse

from .common import load_view, read_json, write_json
from .models import curve, summarize
from .signals import times


def estimate(view, model):
    settings = model["settings"]
    results = []
    for method in ("xcorr", "arx"):
        prediction = summarize(curve(view, method, model[method], settings), model["calibration"][method], settings)
        prediction.update(method=method, sample_id=str(view["sample_id"]),
                          trajectory_id=str(view["trajectory_id"]), score_timesteps=len(times(len(view["command"]), settings)))
        results.append(prediction)
    return results


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--model", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args()
    write_json(args.output, estimate(load_view(args.input), read_json(args.model)))


if __name__ == "__main__":
    main()
