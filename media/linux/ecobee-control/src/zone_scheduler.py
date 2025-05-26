# File name: zone_scheduler.py
# Author: Abel Alhussainawi
# Created: 2/29/2025
# License: BSD licenses
#
# Description: This file contains functions to schedule Ecobee
#              thermostats based on Google Calendar events.  Ecobee
#              modes are assigned depending on these conditions:
#              1. “Home” during events 2. "Away" outside the sleep end
#              and sleep start period defined in the config.json file
#              3. "Sleep" within the sleep end and sleep start period
#              defined in the config.json file

import pytz
import logging
import datetime

import pandas as pd

def generate_weekly_df(events, config, override_now=None):
    """
    Generate a weekly schedule dataframe for a single Ecobee for the next 7 days starting from today.

    Args:
        events (list): List of event dictionaries (each containing "start" and "end" in ISO format).
        config (dict): from config file: "zones", "ecobees", "sleep start", "sleep end", "timezone", etc.
        override_now (datetime, optional): For testing, overrides the current date with the date in the test_calendar_dump.json

    Returns:
        pd.DataFrame: Weekly schedule dataframe
    """
    # Extract configuration parameters.
    sleep_start_str = config.get("Overnight start")  # e.g., "21:00"
    sleep_start_time = datetime.datetime.strptime(sleep_start_str, "%H:%M").time()
    sleep_end_str = config.get("Overnight end")        # e.g., "06:00"
    sleep_end_time = datetime.datetime.strptime(sleep_end_str, "%H:%M").time()
    timezone_str = config.get("timezone")          # e.g., "US/Eastern"
    tz = pytz.timezone(timezone_str)
    baseline = ["sleep"] * 12 + ["away"] * 30 + ["sleep"] * 6

    # Determine the start date or overide if testing
    now = override_now if override_now else datetime.datetime.now(tz)
    start_date = now.date()

    # dictionary keyed by actual date for the next 7 days.
    schedule_by_date = {}
    day_order = []
    for offset in range(7):
        day_date = start_date + datetime.timedelta(days=offset)
        schedule_by_date[day_date] = baseline.copy()
        day_order.append(day_date)

    # Create time labels for the 48 intervals. 12:00 AM, 12:30 AM...11:00 PM,11:30 PM
    time_intervals = []
    today_midnight = datetime.datetime.combine(start_date, datetime.time(0, 0), tzinfo=tz)
    for i in range(48):
        interval_time = today_midnight + datetime.timedelta(minutes=30 * i)
        time_intervals.append(interval_time.strftime("%I:%M %p"))

    # Process each day in the next 7 days.
    for day_date in day_order:
        day_midnight = datetime.datetime.combine(day_date, datetime.time(0, 0), tzinfo=tz)
        # Define the daytime window: from wake time (sleep end) to bedtime (sleep start).
        daytime_start = datetime.datetime.combine(day_date, sleep_end_time, tzinfo=tz)
        daytime_end = datetime.datetime.combine(day_date, sleep_start_time, tzinfo=tz)

        # Process each event for this day.
        for event in events:
            # Parse event start and end times.
            start_str = event["start"].get("dateTime", event["start"].get("date"))
            end_str = event["end"].get("dateTime", event["end"].get("date"))
            ev_start = datetime.datetime.fromisoformat(start_str).astimezone(tz)
            ev_end = datetime.datetime.fromisoformat(end_str).astimezone(tz)

            # Compute the effective overlap of the event with this day's daytime window.
            effective_start = max(ev_start, daytime_start)
            effective_end = min(ev_end, daytime_end)
            if effective_end <= effective_start:
                continue  # No overlap.

            # Update any 30-minute interval overlapping the effective event time to "home".
            for idx in range(48):
                interval_start = day_midnight + datetime.timedelta(minutes=30 * idx)
                interval_end = day_midnight + datetime.timedelta(minutes=30 * (idx + 1))
                if interval_end > effective_start and interval_start < effective_end:
                    schedule_by_date[day_date][idx] = "home"

    # Reorder the weekday columns: Monday through Sunday.
    weekday_schedule = {}
    for day_date in day_order:
        day_name = day_date.strftime("%A")
        weekday_schedule[day_name] = schedule_by_date[day_date]

    ordered_weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    # Assemble the final DataFrame.
    data = {"Time": time_intervals}
    for weekday in ordered_weekdays:
        data[weekday] = weekday_schedule.get(weekday, baseline.copy())

    weekly_df = pd.DataFrame(data)
    return weekly_df


def schedule_ecobees_for_lookahead(all_events, config, ecobee_client, override_now=None):
    """
    For each Ecobee thermostat, generate a weekly schedule DataFrame for the next 7 days and schedule the thermostat.

    Args:
        all_events (list): List of all event dictionaries.
        config (dict): from config file: "zones", "ecobees", "sleep start", "sleep end", "timezone", etc.
        ecobee_client: An instance of EcobeeClient
        override_now (datetime, optional): For testing, overrides the current date with the date in the test_calendar_dump.json
    """
    zones = config.get("zones", [])
    ecobees = config.get("ecobees", [])

    # Build a mapping: ecobee_id -> list of events from the zones it is associated with.
    ecobee_events_map = {e_id: [] for e_id in ecobees}
    for zone in zones:
        zone_calendars = zone.get("calendars", [])
        zone_events = [event for event in all_events if event.get("calendar_name") in zone_calendars]
        for e_id in zone.get("ecobees", []):
            ecobee_events_map[e_id].extend(zone_events)

    logging.debug(ecobee_events_map)

    for ecobee_id, events in ecobee_events_map.items():
        weekly_df = generate_weekly_df(events, config, override_now)
        ecobee_client.schedule_mode_change(weekly_df, ecobee_id)
