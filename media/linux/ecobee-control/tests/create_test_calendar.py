"""
File name: create_test_calendar.py
Author: Abel Alhussainawi
Created: 3/25/2025
License: BSD licenses
Description: A script to fetch Google Calendar Events using google_calendar_client.py and save the events to
            "test_calendar_dump.json." This script will fetch all events from the time of running the script to 7 days later.

"""

import pytz
import json
from src.google_calendar.google_calendar_client import GoogleCalendarClient
from datetime import datetime

def main():
    google_client = GoogleCalendarClient()
    google_client.authenticate()
    events = google_client.get_all_events()

    now = datetime.now(pytz.timezone("US/Eastern"))

    output = {
        "created_at": now.isoformat(),  # pass the time created for automatic overriding in zone scheduler
        "events": events
    }

    with open("test_calendar_dump.json", "w") as f:
        json.dump(output, f, indent=2)

    print(f"Calendar events saved to test_calendar_dump.json ({len(events)} events)")

if __name__ == "__main__":
    main()
