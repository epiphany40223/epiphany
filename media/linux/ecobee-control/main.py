"""
File name: main.py
Author: Abel Alhussainawi
Created: 1/29/2025
License: BSD licenses
Description: This is the top level code of the project. This script initializes the Google Calendar
             and Ecobee clients, retrieves upcoming events from Google Calendar, loads the configuration file
             (config.json), and then schedules Ecobee thermostats based on those events.
"""

import argparse
import logging
from google_calendar.google_calendar_client import GoogleCalendarClient
from ecobee.ecobee_client import EcobeeClient
from zone_scheduler import schedule_ecobees_for_lookahead

def main():
    # Set up argument parser for both clients
    parser = argparse.ArgumentParser(description="Ecobee and Google Calendar Integration")
    # Google Calendar flags
    parser.add_argument('--config', default=None, help="Path to Google Calendar config.json")
    parser.add_argument('--google-credentials', default=None, help="Path to Google credentials JSON")
    parser.add_argument('--token-json', default=None, help="Path to Google token.json")
    # Ecobee flags
    parser.add_argument('--credentials', default=None, help="Path to Ecobee credentials.json")
    parser.add_argument('--schedule-payload', default=None, help="Path to Ecobee schedule_payload.txt")
    parser.add_argument('--db-path', default=None, help="Path to Ecobee pyecobee_db")
    args = parser.parse_args()

    # Setup Google Calendar Client and authenticate
    google_client = GoogleCalendarClient()
    google_client.authenticate()

    # Retrieve all upcoming events
    all_events = google_client.get_all_events()

    # Load configuration (including zones, ecobees, lookahead days, sleep times, timezone)
    config = google_client.config

    # Set up the Ecobee Client and authenticate
    ecobee_client = EcobeeClient(
        thermostat_name="Test1",
        credentials_file=args.credentials,
        schedule_payload_file=args.schedule_payload,
        db_path=args.db_path,
        config=config
    )
    ecobee_client.authenticate()

    # Hand off scheduling to zone_scheduler
    schedule_ecobees_for_lookahead(all_events, config, ecobee_client)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
