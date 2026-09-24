#!/usr/bin/env python3
import argparse

parser = argparse.ArgumentParser(description="Manage a running widget.")
parser.add_argument("--quiet", action="store_true", help="print nothing but errors")
parser.parse_args()
