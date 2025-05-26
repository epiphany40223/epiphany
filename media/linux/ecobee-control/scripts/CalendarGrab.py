import json
import os
import logging
import pickle
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

# Google Calendar API credentials
CLIENT_SECRET_FILE = "credentials.json"
SCOPES = ["https://www.googleapis.com/auth/calendar"]
TOKEN_FILE = "token.pickle"

# Define the calendar ID to exclude
EXCLUDED_CALENDAR_ID = "en.usa#holiday@group.v.calendar.google.com"


def authenticate_google_account():
    creds = None

    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "rb") as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        try:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
                creds = flow.run_local_server(port=0)

            with open(TOKEN_FILE, "wb") as token:
                pickle.dump(creds, token)

            logging.info("Authentication successful")
        except Exception as e:
            logging.error(f"Authentication failed: {e}")
            return None

    return creds


def get_paginated_results(api_call, **kwargs):
    results = []
    page_token = None

    try:
        while True:
            response = api_call(pageToken=page_token, **kwargs).execute()
            results.extend(response.get("items", []))
            page_token = response.get("nextPageToken")
            if not page_token:
                break
    except HttpError as error:
        logging.error(f"API request failed: {error}")

    return results


def get_all_calendars(service):
    logging.info("Fetching all calendars...")
    return get_paginated_results(service.calendarList().list)


def get_calendar_metadata(service, calendar_id):
    try:
        return service.calendars().get(calendarId=calendar_id).execute()
    except HttpError as error:
        logging.error(f"Failed to fetch metadata for calendar {calendar_id}: {error}")
        return {}


def get_calendar_acl(service, calendar_id):
    logging.info(f"Fetching ACL for calendar: {calendar_id}")
    return get_paginated_results(service.acl().list, calendarId=calendar_id)


def get_calendar_settings(service):
    logging.info("Fetching calendar settings...")
    return get_paginated_results(service.settings().list)


def get_events(service, calendar_id):
    logging.info(f"Fetching events for calendar: {calendar_id}")
    return get_paginated_results(
        service.events().list,
        calendarId=calendar_id,
        maxResults=500000,
        singleEvents=True,
        showDeleted=False,
        showHiddenInvitations=True,
        orderBy="startTime",
    )


def get_all_calendar_details(service):
    all_details = {"settings": get_calendar_settings(service), "calendars": []}

    calendars = get_all_calendars(service)
    for calendar in calendars:
        calendar_id = calendar["id"]

        # Skip the Holidays calendar
        if calendar_id == EXCLUDED_CALENDAR_ID:
            logging.info(f"Skipping calendar: {calendar.get('summary', calendar_id)}")
            continue

        logging.info(f"Processing calendar: {calendar.get('summary', calendar_id)}")

        calendar_data = {
            "metadata": get_calendar_metadata(service, calendar_id),
            "acl": get_calendar_acl(service, calendar_id),
            "events": get_events(service, calendar_id),
        }
        all_details["calendars"].append(calendar_data)

    return all_details


def main():
    creds = authenticate_google_account()
    if not creds:
        return

    try:
        service = build("calendar", "v3", credentials=creds)

        full_details = get_all_calendar_details(service)

        output_file = "all_calendar_details.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(full_details, f, indent=4, ensure_ascii=False)

        logging.info(f"Full calendar details saved to {output_file}")

    except HttpError as error:
        logging.error(f"An error occurred: {error}")


if __name__ == "__main__":
    main()
