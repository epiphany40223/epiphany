#!/usr/bin/env python
#
# You need all the Python packages in requirements.txt.
#
# You probably want to use a Python virtual environment for this project.
# For example:
#
# $ virtualenv --python=python3.9 py39
# $ . ./py39/bin/activate
# $ pip3 install -r requirements.txt
#

import os
import sys
import datetime

import ECC
import ECC.Google
import ECC.GoogleAuth
import ECC.Calendars

import pytz

from google.api_core import retry
from oauth2client import tools
from datetimerange import DateTimeRange

default_app_json  = 'gcalendar-reservations-client-id.json'
default_user_json = 'user-credentials.json'

verbose = True
debug   = False
logfile = None

grace_period_before = datetime.timedelta(hours=1)
grace_period_after  = datetime.timedelta(minutes=15)

def set_thermostat(thermostats, occupied, log):
    # thermostats = list of thermostats
    # occupied = boolean indicating whether the thermos should be occupied or not

    # JMS Continue here
    from pprint import pprint, pformat
    log.debug(f"Setting thermostats: occupied = {occupied}")
    log.debug(pformat(thermostats))

####################################################################

def calculate_missing(all_thermostats, subset, log):
    output = dict()
    for name, thermostat in all_thermostats.items():
        if name not in subset:
            output[name] = thermostat

    return output

####################################################################

def find_occupied_thermostats(events, calendar, start, end, occupied, log):
    # Determine if the room is "occupied".  We determine that a room is
    # "occupied" if the current time is within the following timeframe of any
    # event:
    #
    # [start time of accepted event - grace_period_before,
    #     end time of accepted event + grace_period_after]

    # Sanity check to make sure that the calendar we're checking has thermostats
    # associated with it.
    key = 'thermostats'
    if key not in calendar:
        # Return an empty list (i.e., no thermostats)
        return list()

    now        = datetime.datetime.utcnow().astimezone(ECC.local_tz)
    one_second = datetime.timedelta(seconds=1)
    for event in events:
        log.debug("Checking event")

        # We only care about events that have been accepted.
        #
        # Per calendar-reservations.py, it's possible for non-staff to make
        # events on ECC resource calendars.  But those events will only be
        # accepted if they are from ECC email addresses.  Those are the events
        # we care about.
        #
        # Specifically: look for events where this calendar ID is an attendee with
        # an "accepted" responseStatus value.
        key = 'attendees'
        if key not in event:
            log.debug("No attendees")
            continue

        happy = False
        for attendee in event["attendees"]:
            if attendee["email"] == calendar['id']:
                if attendee["responseStatus"] == "accepted":
                    happy = True
                    break

        if not happy:
            continue

        # If we got here, this is an event that we care about. Recall that
        # Google Calendar events are recorded at the resolution of 1 minute.  So
        # to be absolutely sure that we're calculting >= and <= comparisons
        # correctly, subtract 1 second from the start time and add 1 second to
        # the end time.
        temp       = datetime.datetime.fromisoformat(event["start"]['dateTime'])
        tz_start   = pytz.timezone(event['start']['timeZone'])
        dtr_start  = temp.astimezone(tz_start)
        dtr_start -= grace_period_before
        dtr_start -= one_second

        temp       = datetime.datetime.fromisoformat(event["end"]['dateTime'])
        tz_end     = pytz.timezone(event['end']['timeZone'])
        dtr_end    = temp.astimezone(tz_end)
        dtr_end   += grace_period_after
        dtr_end   += one_second

        dtr = DateTimeRange(dtr_start, dtr_end)
        if now in dtr:
            # This event meets all the criteria: we need to set all relevant
            # thermostats to "occupied".
            for thermostat in calendar['thermostats']:
                name = thermostat['name']
                if name not in occupied:
                    log.debug(f"JMS SET OCCUPIED: {name}")
                    occupied[name] = thermostat

    return occupied

####################################################################

def download_gcal_events(service, calendar, start, end, log):
    # Calendar events documentation: https://developers.google.com/calendar/v3/reference/events?hl=en_US

    log.info(f"Downloading events from {calendar['name']} (ID: {calendar['id']})")

    # We only need to check for events starting grace_period_after ago to
    # grace_period_before from now (downloading _all_ events without filtering
    # them takes far too long).
    startString = start.isoformat() + 'Z' # 'Z' indicates UTC time
    endString   = end.isoformat() + 'Z'
    log.debug(f"Looking for events {start} - {end}")

    # Make this a subroutine so that we can wrap it in retry.Retry()
    @retry.Retry(predicate=ECC.Google.retry_errors)
    def _download():
        events = list()
        page_token = None
        while True:

            # Get the list of events.
            # NOTE: there is a "q" parameter which supposedly takes a free text
            # query, but I cannot find any documentation for it, and none of my
            # guesses how to use it have yielded any useful results.  So for
            # now, we just get all the events within the desired timeframe and
            # then examine/filter them here in Python.
            events_result = service.events().list(calendarId=calendar['id'],
                                                timeMin=startString,
                                                timeMax=endString,
                                                singleEvents=True,
                                                pageToken=page_token,
                                                maxResults=2500,
                                                orderBy='startTime').execute()
            new_events = events_result.get('items', [])
            if not new_events:
                break

            events.extend(new_events)

            # continues to process events if there are more to process, returns if not
            page_token = events_result.get('nextPageToken')
            if not page_token:
                break

        return events

    events = _download()
    log.info(f"Found {len(events)} calendar events within calendar {calendar['name']}")
    return events

####################################################################
#
# Setup functions
#
####################################################################

def setup_cli_args():
    global default_app_json
    tools.argparser.add_argument('--app-id',
                                 default=default_app_json,
                                 help='Filename containing Google application credentials')
    global default_user_json
    tools.argparser.add_argument('--user-credentials',
                                 default=default_user_json,
                                 help='Filename containing Google user credentials')
    tools.argparser.add_argument('--slack-token-filename',
                                 required=True,
                                 help='File containing the Slack bot authorization token')

    global verbose
    tools.argparser.add_argument('--verbose',
                                 action='store_true',
                                 default=verbose,
                                 help='If enabled, emit extra status messages during run')
    global debug
    tools.argparser.add_argument('--debug',
                                 action='store_true',
                                 default=debug,
                                 help='If enabled, emit even more extra status messages during run')
    global logfile
    tools.argparser.add_argument('--logfile',
                                 default=logfile,
                                 help='Store verbose/debug logging to the specified file')

    tools.argparser.add_argument('--dry-run',
                                 action='store_true',
                                 help='Runs through the program without modifying any data')

    global args
    args = tools.argparser.parse_args()

    # --debug implies --verbose
    if args.debug:
        args.verbose = True

####################################################################

def main():
    setup_cli_args()

    log = ECC.setup_logging(info=args.verbose,
                            debug=args.debug,
                            logfile=args.logfile, rotate=True,
                            slack_token_filename=args.slack_token_filename)

    # Note: these logins have been configured on the Google cloud
    # console to only allow logins with @epiphanycatholicchurch.org
    # accounts.  If the login flow runs in a browser where you are
    # logged in to a non-@epiphanycatholicchurch.org account, it will
    # display some kind of error.  No problem: just take the URL from
    # the console window and paste it into a browser that is logged in
    # to an @epiphanycatholicchurch.org account.

    apis = {
        'calendar': { 'scope'       : ECC.Google.scopes['calendar'],
                      'api_name'    : 'calendar',
                      'api_version' : 'v3' },
    }
    services = ECC.GoogleAuth.service_oauth_login(apis,
                                              app_json=args.app_id,
                                              user_json=args.user_credentials)
    calendar_service = services['calendar']

    calendars = ECC.Calendars.calendars
    if args.debug:
        calendars = ECC.Calendars.calendars_debug

    now   = datetime.datetime.utcnow()
    start = now - grace_period_after
    end   = now + grace_period_before

    occupied = dict()
    for calendar in calendars:
        events = download_gcal_events(calendar_service, calendar, start, end, log)
        find_occupied_thermostats(events, calendar, start, end, occupied, log)

    # We now have a full list of occupied thermostats.
    # Compute the list of unoccupied thermostats.
    unoccupied = calculate_missing(ECC.Thermostats.thermostats_by_name, occupied, log)

    # Go ensure that each thermostat is set appropriately
    set_thermostat(occupied.values(), occupied=True, log=log)
    set_thermostat(unoccupied.values(), occupied=False, log=log)

if __name__ == '__main__':
    main()
