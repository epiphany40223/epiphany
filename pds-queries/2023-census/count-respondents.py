#!/usr/bin/env python3

import csv

fids = dict()

with open("ECC 2022 Census update - Form Responses.csv") as csvfile:
    reader = csv.DictReader(csvfile)
    for row in reader:
        print(f"FID: {row['fid']}")
        fids[row['fid']] = True

print(f"Number of unique respondents: {len(fids)}")
