import os
import json
import logging
import argparse
import datetime

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow

# Define the scope for Google Calendar API
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

def setup_cli():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True, help="Path to config.json")
    parser.add_argument('--google-credentials', required=True, help="Path to Google credentials JSON")
    parser.add_argument('--token-json', help="Path to token.json")

    args = parser.parse_args()

    if not args.token_json:
        print("No token.json provided, using OAuth flow to generate it.")

    return args

def authenticate_oauth(credentials=None, token=None):
    creds = None
    try:
        # Use InstalledAppFlow to authenticate using the credentials file
        if credentials and os.path.exists(credentials):
            creds = None  # reset creds to ensure the flow occurs
            flow = InstalledAppFlow.from_client_secrets_file(credentials, SCOPES)

            # If we have a token file, use it to try and load the credentials
            if token and os.path.exists(token):
                creds = Credentials.from_authorized_user_file(token, SCOPES)

            # If we have no credentials or they're expired, go through the flow to get new credentials
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    creds = flow.run_local_server(port=0)

                # Save the credentials for the next run
                if token:
                    with open(token, 'w') as token_file:
                        token_file.write(creds.to_json())

            logging.info("Authentication successful.")

        else:
            logging.error("Google credentials file not found.")
            return None

    except Exception as e:
        logging.error(f"Failed to authenticate using GOOGLE_CREDENTIALS: {e}")

    return creds

def load_config(config_path=None):
    # Loads the calendar configuration from a config file. The path to the config file can be passed via CLI argument or environment variable.
    if not os.path.exists(config_path):
        logging.error(f"Config file {config_path} not found.")
        return None

    try:
        with open(config_path, "r") as f:
            config = json.load(f)
        return config
    except Exception as e:
        logging.error(f"Error reading config file: {e}")
        return None

def get_all_calendar_ids(service):
    # Retrieves all Google Calendar IDs associated with the authenticated account.
    calendar_ids = []
    try:
        # Fetch calendar list from the authenticated account
        calendars = []
        page_token = None
        while True:
            calendar_list_response = service.calendarList().list(pageToken=page_token).execute()
            calendars.extend(calendar_list_response.get("items", []))
            page_token = calendar_list_response.get("nextPageToken")
            if not page_token:
                break

        if not calendars:
            logging.info("No calendars found.")
            return []

        for calendar in calendars:
            calendar_ids.append(calendar["id"])

        return calendar_ids

    except Exception as e:
        logging.error(f"Error fetching calendar IDs: {e}")
        return []

def fetch_events(service, calendar_id, time_min, time_max):
    try:
        events_result = service.events().list(
            calendarId=calendar_id,
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy="startTime",
        ).execute()

        logging.info(f"Fetched {len(events_result.get('items', []))} events from calendar {calendar_id}")
        return events_result.get("items", [])
    except Exception as e:
        logging.error(f"Error fetching events from calendar {calendar_id}: {e}")
        return []

def main():
    args = setup_cli()
    creds = authenticate_oauth(args.google_credentials, args.token_json)
    if not creds:
        return

    config = load_config(args.config)
    if not config:
        return

    try:
        service = build("calendar", "v3", credentials=creds)
        calendar_list = get_all_calendar_ids(service)
        if not calendar_list:
            return

        now = datetime.datetime.now(datetime.timezone.utc)
        start_of_today = datetime.datetime(now.year, now.month, now.day, 0, 0, 0, 0, tzinfo=datetime.timezone.utc)
        time_min = start_of_today.isoformat()

        lookahead_days = config.get("lookahead_days", 60)
        time_max = (now + datetime.timedelta(days=lookahead_days)).isoformat()

        all_events = []
        for calendar_id in calendar_list:
            events = fetch_events(service, calendar_id, time_min, time_max)
            all_events.extend(events)

        # Sort events by start time before processing them
        all_events.sort(key=lambda x: x["start"].get("dateTime") or x["start"].get("date"))

        # Filter and display events based on calendar and location
        for event in all_events:
            event_calendar = event.get('organizer', {}).get('displayName', '').strip()
            event_location = event.get('location', 'No location')

            # First check: Check if the event calendar is in the config's calendar list
            if event_calendar in config.get("calendars", []):
                # If it matches the calendar, print event details
                print_event_details(event)
                continue  # Skip further checks for location since it's already a match

            # Second check: If not found in calendars, check location
            if event_location in config.get("location", []):
                # If it matches the location, print event details
                print_event_details(event)
                continue  # Skip printing details multiple times if a match is found

    except Exception as e:
        logging.error(f"Error in main execution: {e}")

# This function is responsible for printing the event details
def print_event_details(event):
    event_id = event.get('id', 'No ID')
    event_status = event.get('status', 'No status')
    event_html_link = event.get('htmlLink', 'No link')
    event_created = event.get('created', 'No creation date')
    event_updated = event.get('updated', 'No updated date')
    event_summary = event.get('summary', 'No title')
    event_location = event.get('location', 'No location')
    event_creator = event.get('creator', {}).get('email', 'No creator email')
    event_organizer = event.get('organizer', {}).get('displayName', 'No organizer name')

    # Start and end times (with timezone)
    event_start = event.get('start', {}).get('dateTime', 'No start time')
    event_end = event.get('end', {}).get('dateTime', 'No end time')

    # Recurring event ID and iCal UID
    recurring_event_id = event.get('recurringEventId', 'No recurring event ID')
    ical_uid = event.get('iCalUID', 'No iCal UID')

    # Attendees (if any)
    attendees = event.get('attendees', [])
    attendees_info = []

    # If no attendees, print the message once, otherwise gather attendee details
    if not attendees:
        attendees_info = None  # Set to None to indicate no attendees
    else:
        for attendee in attendees:
            attendee_name = attendee.get('displayName', 'No display name')
            attendee_email = attendee.get('email', 'No email')
            attendee_self = attendee.get('self', False)
            attendee_resource = attendee.get('resource', False)
            attendee_response_status = attendee.get('responseStatus', 'No response status')

            # Store full details of the attendee
            attendees_info.append({
                'email': attendee_email,
                'displayName': attendee_name,
                'self': attendee_self,
                'resource': attendee_resource,
                'responseStatus': attendee_response_status
            })

    # Print event details
    print(f"\n{'-'*50}")
    print(f"ID: {event_id}")
    print(f"Status: {event_status}")
    print(f"Link: {event_html_link}")
    print(f"Created: {event_created}")
    print(f"Updated: {event_updated}")
    print(f"Summary: {event_summary}")
    print(f"Location: {event_location}")
    print(f"Creator: {event_creator}")
    print(f"Organizer: {event_organizer}")
    print(f"Start: {event_start}")
    print(f"End: {event_end}")
    print(f"Recurring Event ID: {recurring_event_id}")
    print(f"iCal UID: {ical_uid}")

    # Only print the attendees section if there are attendees
    if attendees_info is not None:  # if there are attendees
        print("Attendees:")
        for attendee in attendees_info:
            print(f"  - Email: {attendee['email']}")
            print(f"    Display Name: {attendee['displayName']}")
            print(f"    Self: {attendee['self']}")
            print(f"    Resource: {attendee['resource']}")
            print(f"    Response Status: {attendee['responseStatus']}")
    else:
        print("No attendees found.")

    print(f"{'-'*50}")

if __name__ == "__main__":
    main()
