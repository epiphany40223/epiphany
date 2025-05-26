#!/usr/bin/env python3

# File name: main.py
# Author: Abel Alhussainawi
# Created: 1/29/2025
# License: BSD licenses
#
# Description: This is the top level code of the project. This script
#              initializes the Google Calendar and Ecobee clients,
#              retrieves upcoming events from Google Calendar, loads the
#              configuration file (config.json), and then schedules
#              Ecobee thermostats based on those events.

import os
import argparse
import logging

from google_calendar.google_calendar_client import GoogleCalendarClient
from ecobee.ecobee_client import EcobeeClient
from zone_scheduler import schedule_ecobees_for_lookahead

def setup_logging(args):
    level = logging.WARNING
    if args.verbose:
        level = logging.INFO
    if args.debug:
        level = logging.DEBUG

    logging.basicConfig(level=level)

def setup_cli():
    # Get the directory of the current script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.realpath(os.path.join(script_dir, "..", "data"))

    # Default file paths, relative to src/
    default_config_file = \
        os.path.join(data_dir, "config.json")
    default_google_credentials_file = \
        os.path.join(data_dir, "google-application-id.json")
    default_google_token_file = \
        os.path.join(data_dir, "google-token.json")
    default_ecobee_credentials_file = \
        os.path.join(data_dir, "ecobee-credentials.json")

    # Parse command-line arguments with defaults
    parser = argparse.ArgumentParser()

    parser.add_argument('--config',
                        default=default_config_file,
                        help="Path to config.json")
    parser.add_argument('--google-app-id',
                        default=default_google_credentials_file,
                        help="Path to Google Application ID JSON file")
    parser.add_argument('--google-token',
                        default=default_google_token_file,
                        help="Path to Google credentials token JSON file")
    parser.add_argument('--ecobee-credentials',
                        default=default_ecobee_credentials_file,
                        help="Path to Ecobee credentials JSON file")

    parser.add_argument('--verbose',
                        default=False,
                        action='store_true')
    parser.add_argument('--debug',
                        default=False,
                        action='store_true')

    args = parser.parse_args()

    setup_logging(args)

    # Sanity check
    for filename in [args.config, args.google_app_id,
                 args.google_token, args.ecobee_credentials]:
        if not os.path.exists(filename):
            logging.error(f"Cannot find {filename}")
            exit(1)

    return args

def main():
    args = setup_cli()

    # Setup Google Calendar Client
    logging.info("Setting up Google Calendar Client...")
    google_client = GoogleCalendarClient(
        config_file=args.config,
        credentials_file=args.google_app_id,
        token_file=args.google_token
    )
    google_client.authenticate()

    # Retrieve all upcoming events
    logging.info("Retrieving upcoming events from Google Calendar...")
    all_events = google_client.get_all_events()

    # Load configuration
    config = google_client.config

    # Set up the Ecobee Client
    logging.info("Setting up Ecobee Client...")
    ecobee_client = EcobeeClient(
        thermostat_name="Test1",
        credentials_file=args.ecobee_credentials,
        config=config
    )
    ecobee_client.authenticate()

    # Hand off scheduling to zone_scheduler
    logging.info("Handing off scheduling to zone scheduler...")
    schedule_ecobees_for_lookahead(all_events, config, ecobee_client)

if __name__ == "__main__":
    main()
