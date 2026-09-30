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
import re
import sys
import argparse
import logging
import warnings

# The production server runs this under WSL1, which leaves the x87 FPU
# in 53-bit (double) precision mode.  numpy then cannot identify the
# long double format and emits a UserWarning when it is first used
# (pandas triggers this at import time).  This script never uses long
# doubles, so the warning is harmless noise: silence just that one.
# This must run before anything imports numpy.
warnings.filterwarnings(
    "ignore",
    message=r"Signature .* for <class 'numpy\.longdouble'> does not match",
    category=UserWarning,
)

from google_calendar.google_calendar_client import GoogleCalendarClient
from ecobee.ecobee_client import EcobeeClient
from zone_scheduler import schedule_ecobees_for_lookahead

# Ecobee credentials that can show up in log output: bearer tokens in
# request headers, and tokens / the app key in token-request URLs.
# pyecobee sends those as query parameters, and both urllib3's debug
# output and pyecobee's error messages include the full request URL.
_SECRET_RE = re.compile(
    r'(Bearer\s+|[?&](?:code|refresh_token|access_token|client_id)=)'
    r'[^\s&"\']+')

def redact(text):
    """Replace Ecobee credentials in text with a placeholder."""
    return _SECRET_RE.sub(r'\1<redacted>', text)

class RedactFilter(logging.Filter):
    """Logging handler filter that redacts credentials from each record's
    message and traceback before the record is formatted."""
    def filter(self, record):
        record.msg = redact(record.getMessage())
        record.args = None
        if record.exc_info and not record.exc_text:
            record.exc_text = logging.Formatter().formatException(record.exc_info)
        if record.exc_text:
            record.exc_text = redact(record.exc_text)
        return True

def log_uncaught_exception(exc_type, exc, tb):
    """sys.excepthook that sends uncaught exceptions through logging, so
    their tracebacks are redacted too (e.g., pyecobee puts the
    token-request URL in some exception messages)."""
    logging.critical("Unhandled exception", exc_info=(exc_type, exc, tb))

def setup_logging(args):
    level = logging.WARNING
    if args.verbose:
        level = logging.INFO
    if args.debug:
        level = logging.DEBUG

    logging.basicConfig(level=level)

    # This script's output can be posted to Slack, so redact credentials
    # from everything that gets logged, including uncaught exceptions
    for handler in logging.getLogger().handlers:
        handler.addFilter(RedactFilter())
    sys.excepthook = log_uncaught_exception

    # pyecobee's debug output includes every request's headers (i.e.,
    # the Ecobee bearer token) and full token-refresh requests and
    # responses (i.e., the long-lived refresh token), in formats the
    # redaction filter does not try to cover.  Keep pyecobee at INFO or
    # above unless its debug output is explicitly requested.
    if args.debug_ecobee:
        logging.getLogger("pyecobee").setLevel(logging.DEBUG)
    else:
        logging.getLogger("pyecobee").setLevel(max(level, logging.INFO))

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
    parser.add_argument('--debug-ecobee',
                        default=False,
                        action='store_true',
                        help="Also show the pyecobee library's debug "
                        "output.  WARNING: this prints Ecobee "
                        "credentials; only use it interactively.")

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
