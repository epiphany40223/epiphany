"""
File name: scheduling_test.py
Author: Abel Alhussainawi
Created: 3/14/2025
License: BSD licenses

Description: This script performs the verification procedures against
             all test cases to satisfy our requirements.  The Script
             runs a mock scheduling run
             (schedule_ecobees_for_lookahead) using the test calendar
             "test_calendar_dump.json" as an input to verify that
             simulated ecobee schedule matches the expected Ecobee
             schedule. The expected schedule is a subset of the
             calendars in "test_calendar_dump.json", where the name of
             the event for the schedule is the mode the thermostat
             should be at.
"""

import json
import logging
import argparse

from datetime import datetime, timedelta
from src.google_calendar.google_calendar_client import GoogleCalendarClient
from src.zone_scheduler import schedule_ecobees_for_lookahead

class MockEcobeeClient:
    """
    Mock Ecobee client that, instead of scheduling mode changes in real time,
    converts the weekly datagram DataFrame into a list of intervals.
    """
    def __init__(self, override_now):
        self.calls = []  # will hold tuples of (thermostat, mode, start_time, end_time)
        self.override_now = override_now

    def schedule_mode_change(self, weekly_df, ecobee_id):
        # Figure out the Monday of the week for which the schedule was generated.
        start_date = self.override_now.date()
        day_order = [start_date + timedelta(days=i) for i in range(7)]
        mapping = {d.strftime("%A"): d for d in day_order}
        ordered_weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

        time_labels = weekly_df["Time"].tolist() # Get the time labels (first column).

        # For each weekday column in the fixed order, convert the 48 rows into intervals.
        for i, weekday in enumerate(ordered_weekdays):
            actual_date = mapping[weekday]          # Determine the actual date for this column.
            modes = weekly_df[weekday].tolist() # Get the mode values for this day.

            # Convert each time label (e.g., "12:00 AM") into a datetime for this actual_date.
            times = []
            for label in time_labels:
                t = datetime.strptime(label, "%I:%M %p").time()
                dt = datetime.combine(actual_date, t, tzinfo=self.override_now.tzinfo)
                times.append(dt)
            # Group consecutive intervals with the same mode.
            # example. if sleep at 4:00am-4:30 am and sleep from 4:30am-5:00 am, combine to 4:00am-5:00am
            idx = 0
            while idx < len(modes):
                current_mode = modes[idx]
                start_time = times[idx]
                # Count how many consecutive rows share the current mode.
                count = 1
                while idx + count < len(modes) and modes[idx + count] == current_mode:
                    count += 1
                # Each row represents a 30-minute interval.
                end_time = start_time + timedelta(minutes=30 * count)
                self.calls.append((ecobee_id, current_mode, start_time, end_time))
                idx += count

def parse_test_calendar_event(event):
    #Only read the test calendars
    cal_name = event.get("calendar_name", "")
    if cal_name not in ("Ecobee Test1 Modes", "Ecobee Test2 Modes"):
        return None

    summary = event.get("summary","")
    if '=' not in summary:
        return None

    left, right = summary.split('=', 1)
    left = left.strip()
    mode = right.strip()  # "Home","Away","Sleep"

    if "Test1" in left:
        thermostat = "Test1"
    elif "Test2" in left:
        thermostat = "Test2"
    else:
        return None

    start_str = event["start"].get("dateTime", event["start"].get("date"))
    end_str = event["end"].get("dateTime", event["end"].get("date"))
    start_dt = datetime.fromisoformat(start_str)
    end_dt = datetime.fromisoformat(end_str)

    return (thermostat, mode, start_dt, end_dt)

def intervals_cover_all(actual_intervals, expected_intervals):
    """
    Checks if every interval listed in the “expected” set is fully covered by at least one corresponding
    interval in the “actual” set

    Args:
        actual_intervals (list[tuple]): A list of tuples (thermostat, mode, start_dt, end_dt).
        expected_intervals (list[tuple]): A list of tuples (thermostat, mode, start_dt, end_dt).
    """
    unmatched = []
    for (exp_thermo, exp_mode, exp_start, exp_end) in expected_intervals:
        covered = False
        for (act_thermo, act_mode, act_start, act_end) in actual_intervals:
            if (
                act_thermo == exp_thermo and
                act_mode == exp_mode and
                act_start <= exp_start and
                act_end >= exp_end
            ):
                covered = True
                break
        if not covered:
            unmatched.append((exp_thermo, exp_mode, exp_start, exp_end))
    if unmatched:
        print("Unmatched expected intervals:")
        for (ecobee, mode, start_time, end_time) in unmatched:
            print(f"  {ecobee} => {mode}, {start_time.isoformat()} -> {end_time.isoformat()}")
        return False
    return True

def compare_test_calendar_vs_lookahead():
    """
    1) Fetch events & config from google_client.
    2) Build expected intervals from "Ecobee Test1/2 Modes".
    3) Run schedule_ecobees_for_lookahead(..., mock_ecobee).
    4) Compare coverage of the actual intervals with the expected intervals.
    """
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Scheduling Test for Google Calendar Integration")
    parser.add_argument('--config', default='src/google_calendar/config.json', help="Path to config.json")
    parser.add_argument('--google-app-id', default='src/google_calendar/credentials.json', help="Path to Google credentials.json")
    parser.add_argument('--google-token', default='src/google_calendar/token.json', help="Path to Google token.json")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    # 1) Fetch events & config from google_client.
    google_client = GoogleCalendarClient(
        config_file=args.config,
        credentials_file=args.google_app_id,
        token_file=args.google_token
    )
    google_client.authenticate()
    config = google_client.config

    with open("test_calendar_dump.json", "r") as f:
        test_data = json.load(f)
    all_events = test_data["events"]

    # 2) Build expected intervals from "Ecobee Test1/2 Modes".
    expected_intervals = []
    for evt in all_events:
        parsed = parse_test_calendar_event(evt)
        if parsed:
            expected_intervals.append(parsed)

    expected_intervals.sort(key=lambda x: x[2])

    print("\nExpected Intervals")
    for (ecobee,mode,start_time,end_time) in expected_intervals:
        print(f"  {ecobee} => {mode}, {start_time.isoformat()} -> {end_time.isoformat()}")

    # 3) Run schedule_ecobees_for_lookahead
    with open("test_calendar_dump.json", "r") as f:
        data = json.load(f)
    test_created_time = datetime.fromisoformat(data["created_at"])# the time test_calendar_dump.json was created
    mock_ecobee = MockEcobeeClient(override_now=test_created_time)
    schedule_ecobees_for_lookahead(all_events, config, mock_ecobee, override_now=test_created_time)

    # 4) Compare coverage of the actual intervals with the expected intervals.
    actual_intervals = mock_ecobee.calls
    actual_intervals.sort(key=lambda x: x[2])

    print("\nActual Intervals")
    for (ecobee, mode, start_time, end_time) in actual_intervals:
        print(f"  {ecobee} => {mode}, {start_time.isoformat()} -> {end_time.isoformat()}")

    covered = intervals_cover_all(actual_intervals, expected_intervals)
    print("\nCoverage Check:")
    if covered:
        print("SUCCESS: All test intervals are covered by scheduling")
    else:
        print("FAILURE:Some intervals from test calendars are not covered!")

if __name__ == "__main__":
    compare_test_calendar_vs_lookahead()
