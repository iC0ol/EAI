from d_alignment.q2.build import build_anchors, build_queries
import argparse

p = argparse.ArgumentParser()
p.add_argument("mode", choices=["anchors", "queries"])
args = p.parse_args()
build_anchors() if args.mode == "anchors" else build_queries()
