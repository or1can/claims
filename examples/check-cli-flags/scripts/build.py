#!/usr/bin/env python3
import argparse

parser = argparse.ArgumentParser(description="Build the widget.")
parser.add_argument("--release", action="store_true", help="optimise the build")
parser.parse_args()
