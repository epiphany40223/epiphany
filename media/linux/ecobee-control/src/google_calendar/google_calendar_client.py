# File name: google_calendar_client.py
# Author: Tanner Jordan
# Created: 1/29/2025
# License: BSD licenses
#
# Description: Performs authentication with the Google Calendar API,
#              retriving Calendar events, reading the configuration file
#              (config.json), and returning a combined event list for
#              futher processing. Make sure you have application_id.json
#              in the same directory as this file.  You should retrieve
#              this file in the Google cloud console.

import os
import json
import pytz
import logging
import datetime

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

class GoogleCalendarClient:
    SCOPES = [
        'https://www.googleapis.com/auth/calendar'
    ]

    def __init__(self, config_file, credentials_file, token_file):
        self.config_file = config_file
        self.credentials_file = credentials_file
        self.token_file = token_file
        logging.info(f"Using credentials file: {self.credentials_file}")
        logging.info(f"Credentials file exists: {os.path.exists(self.credentials_file)}")
        logging.info(f"Using token file: {self.token_file}")
        logging.info(f"Using config file: {self.config_file}")
        self.creds = None
        self.service = None
        self.config = self.load_config()

    def load_config(self):
        """Load the configuration from config.json."""
        try:
            with open(self.config_file, 'r') as f:
                config = json.load(f)
            logging.info(f"Successfully loaded config from {self.config_file}")
            return config
        except FileNotFoundError:
            logging.error(f"Config file not found at {self.config_file}")
            exit(1)
        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse config file {self.config_file}: {e}")
            exit(1)
        except Exception as e:
            logging.error(f"Error loading config file {self.config_file}: {e}")
            exit(1)

    def authenticate_oauth(self, credentials, token):
        creds = None
        try:
            logging.info(f"Attempting to authenticate with credentials file: {credentials}")
            flow = InstalledAppFlow.from_client_secrets_file(credentials, self.SCOPES)
            creds = Credentials.from_authorized_user_file(token, self.SCOPES)

            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    logging.info("Refreshing expired credentials")
                    creds.refresh(Request())
                else:
                    logging.info("Running OAuth flow")
                    creds = flow.run_local_server(port=0)
                if token:
                    logging.info(f"Writing new token to: {token}")
                    with open(token, 'w') as token_file:
                        token_file.write(creds.to_json())
            logging.info("Authentication successful.")

        except Exception as e:
            logging.error(f"Failed to authenticate using GOOGLE_CREDENTIALS: {e}")
        return creds

    def authenticate(self):
        self.creds = self.authenticate_oauth(self.credentials_file, self.token_file)
        if self.creds:
            self.service = build("calendar", "v3", credentials=self.creds)
        else:
            logging.error("Authentication failed. Cannot build Google Calendar service.")
            exit(1)

    def get_calendar_ids(self):
        try:
            logging.info("Retrieving calendar list...")
            calendars = self.service.calendarList().list().execute().get("items", [])
            allowed_calendars = self.config.get("calendars", [])
            logging.debug("Found all of these calendars:")
            for calendar in calendars:
                logging.debug(calendar['summary'])

            calendars_to_use = [
                (calendar["id"], calendar["summary"])
                for calendar in calendars
                if calendar["summary"] in allowed_calendars
            ]
            logging.debug(f"Using these Google Calendars: {calendars_to_use}")
            return calendars_to_use

        except HttpError as error:
            logging.error("An error occurred while retrieving calendars: %s", error)
            return []

    def fetch_events(self, calendar_id, time_min, time_max):
        try:
            events_result = self.service.events().list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                maxResults=500,
                singleEvents=True,
                orderBy="startTime",
            ).execute()
            return events_result.get("items", [])
        except HttpError as error:
            logging.error(f"An error occurred while fetching events from calendar {calendar_id}: {error}")
            return []

    def get_all_events(self):
        calendar_list = self.get_calendar_ids()
        if not calendar_list:
            logging.info("No calendars to process.")
            return []

        tz = pytz.timezone(self.config['timezone'])
        now = datetime.datetime.now(datetime.timezone.utc)
        lookahead_days = 7
        future_date = now + datetime.timedelta(days=lookahead_days)
        time_min = now.isoformat()
        time_max = future_date.isoformat()

        all_events = []
        for calendar_id, calendar_name in calendar_list:
            logging.info(f"Fetching events from calendar: {calendar_name}")
            events = self.fetch_events(calendar_id, time_min, time_max)
            for event in events:
                start_str = event["start"].get("dateTime", event["start"].get("date"))
                end_str = event["end"].get("dateTime", event["end"].get("date"))
                event["start"]["dateTime"] = datetime.datetime.fromisoformat(start_str).replace(tzinfo=tz).isoformat()
                event["end"]["dateTime"] = datetime.datetime.fromisoformat(end_str).replace(tzinfo=tz).isoformat()
                event["calendar_name"] = calendar_name
                all_events.append(event)

        all_events.sort(key=lambda x: x["start"].get("dateTime", x["start"].get("date")))
        logging.info(f"Total events fetched: {len(all_events)}")
        return all_events
