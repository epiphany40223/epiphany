#!/usr/bin/env python3

import os
import csv
import sys

import matplotlib.pyplot as plt

from datetime import datetime
from pprint import pprint

if sys.argv[1].strip() == '':
    print("ERROR: Must supply CSV filename")
    exit(1)

raw_data = list()
with open(sys.argv[1]) as csvfile:
    reader = csv.reader(csvfile)
    for row in reader:
        raw_data.append(row)

##################################################################

first_dt = datetime.fromtimestamp(9999999999)
last_dt  = datetime.fromtimestamp(0)

template  = {
    'value' : 0,
    'x'     : 0,
}
right_way = dict()
wrong_way = dict()
for row in raw_data:
    d     = datetime.strptime(row[0], "%m/%d/%y %H:%M")
    right = int(row[1]) if row[1] else 0
    wrong = int(row[2]) if row[2] else 0

    # 0 = Monday
    weekday = d.weekday()
    hour    = d.hour

    if d > last_dt:
        last_dt = d
    if d < first_dt:
        first_dt = d

    if weekday not in right_way:
        right_way[weekday] = dict()
        wrong_way[weekday] = dict()
    if hour not in right_way[weekday]:
        x = int(weekday) * 24 + int(hour)
        right_way[weekday][hour] = template.copy()
        wrong_way[weekday][hour] = template.copy()
        right_way[weekday][hour]['x'] = x
        wrong_way[weekday][hour]['x'] = x

    right_way[weekday][hour]['value'] += right
    wrong_way[weekday][hour]['value'] += wrong

##################################################################

# Convert the data to something friendly to plot

day_names = {
    0 : 'Monday',
    1 : 'Tuesday',
    2 : 'Wednesday',
    3 : 'Thursday',
    4 : 'Friday',
    5 : 'Saturday',
    6 : 'Sunday',
}

##################################################################

def hourly_plot():
    labels = list()
    for day in day_names.values():
        for hour in range(0, 24):
            if hour == 0:
                label = f"{day}"
            elif hour % 4 == 0:
                label = f"{hour}:00"
            else:
                label = ''

            labels.append(label)

    fig, ax = plt.subplots()

    right_y = [0] * len(labels)
    wrong_y = [0] * len(labels)
    for weekday in right_way:
        for hour in right_way[weekday]:
            right_y[right_way[weekday][hour]['x']] = right_way[weekday][hour]['value']
            wrong_y[wrong_way[weekday][hour]['x']] = wrong_way[weekday][hour]['value']

    x = range(0, len(labels))

    plot_right = ax.bar(x, right_y)
    plot_wrong = ax.bar(x, wrong_y, bottom=right_y)

    for rect_wrong, rect_right in zip(plot_wrong, plot_right):
        height = rect_wrong.get_height()
        if height > 0:
            ax.annotate(f"{height}", xy=(rect_wrong.get_x() + rect_wrong.get_width() / 2, (rect_wrong.get_height() + rect_right.get_height())), xytext=(0, 2), textcoords="offset points", ha='center', va='bottom')

    plt.ylabel("Number of vehicle transits")
    plt.title(f"Hourly summation by day\n(playground corner, {first_dt.date()} thru {last_dt.date()})")
    plt.xticks(x, labels, rotation=90)
    plt.legend(['Drove the right way', 'Drove the wrong way'])
    plt.tight_layout()

    fig.savefig("hourly-plot.pdf")

##################################################################

# Same as hourly plot, but with 4-hour buckets
def fourhourly_plot():
    labels = list()
    for day in day_names.values():
        for hour in range(0, 24, 4):
            if hour == 0:
                label = f"{day}"
            else:
                label = f"{hour}:00"

            labels.append(label)

    fig, ax = plt.subplots()

    right_y = [0] * len(labels)
    wrong_y = [0] * len(labels)
    for weekday in right_way:
        for hour in right_way[weekday]:
            bucket = int(right_way[weekday][hour]['x'] / 4)
            right_y[bucket] += right_way[weekday][hour]['value']
            wrong_y[bucket] += wrong_way[weekday][hour]['value']

    x = range(0, len(labels))

    plot_right = ax.bar(x, right_y)
    plot_wrong = ax.bar(x, wrong_y, bottom=right_y)

    for rect_wrong, rect_right in zip(plot_wrong, plot_right):
        height = rect_wrong.get_height()
        if height > 0:
            ax.annotate(f"{height}", xy=(rect_wrong.get_x() + rect_wrong.get_width() / 2, (rect_wrong.get_height() + rect_right.get_height())), xytext=(0, 2), textcoords="offset points", ha='center', va='bottom')

    plt.ylabel("Number of vehicle transits")
    plt.title(f"4-hour summation by day\n(playground corner, {first_dt.date()} thru {last_dt.date()})")
    plt.xticks(x, labels, rotation=90)
    plt.legend(['Drove the right way', 'Drove the wrong way'])
    plt.tight_layout()

    fig.savefig("4hourly-plot.pdf")

hourly_plot()
fourhourly_plot()
