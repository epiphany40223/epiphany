#!/usr/bin/env python
#
# You need all the Python packages in requirements.txt.
#
# You probably want to use a Python virtual environment for this project.
# For example:
#
# $ virtualenv --python=python3.8
# $ . ./venv/bin/activate
# $ pip3 install `cat requirements.txt`
#

import sys
sys.path.insert(0, '../../../python')

import ECC
import Google
import GoogleAuth

import datetime

from oauth2client import tools

default_app_json  = 'gcalendar-reservations-client-id.json'
default_user_json = 'user-credentials.json'

verbose = True
debug   = False
logfile = None

# dictionary of calendars that we're checking for events on
calendars = [
    {
        "name" : "Test calendar #1",
        "id": 'c_bj96menjelb4pecracnninf45k@group.calendar.google.com',
    },
    {
        "name" : "Test calendar #2",
        "id" : 'c_ncm1ib261lp6c02i46mors4isc@group.calendar.google.com',
    },
#    {
#        "name" : "Epiphany Events",
#        "id" : "churchofepiphany.com_9gueg54raienol399o0jtdgmpg@group.calendar.google.com",
#    }
]

#list of the domains the calendar will accept events from, will decline events from all others
acceptable_domains = {
    'cabral.org',
    'epiphanycatholicchurch.org',
    'churchofepiphany.com',
}

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

    return args

####################################################################

def check_response_status(events, calendar, log):
    #iterate through the list of events and find ones where responseStatus = needsAction

    needs_action_events = []
    for event in events:
        if "attendees" in event: #determines whether the event has any attendees
            for attendee in event["attendees"]:
                if attendee["email"] == calendar['id']:
                    if attendee["responseStatus"] == "needsAction":
                        needs_action_events.append(event)

    log.info(f"Found {len(needs_action_events)} needsAction events from {calendar['name']}")

    return needs_action_events

####################################################################

def respond_to_events(events, service, calendar, log):
    #accepts events from a domain in the list of acceptable domains, declines all others

    for event in events:
        organizer_email = event["organizer"]["email"]
        organizer_domain = organizer_email.split('@')[1]
        id = event["id"]

        if organizer_domain in acceptable_domains:
            response = 'accepted'
        else:
            response = 'declined'

        log.info(f"Event {event['summary']} {id}: will be {response}")

        response_body =   {
                "attendees" : [
                    {
                        "email" : calendar['id'],
                        "responseStatus" : response,
                    },
                ],
            }

        if not args.dry_run:
            service.events().patch(
                calendarId = calendar['id'],
                eventId = id,
                body = response_body,
            ).execute()
            log.info(f"Successfully {response} event {event['summary']} {id}")
        else:
            log.info(f"dry-run: would have {response} event {event['summary']} {id}")


####################################################################

def process_events(service, calendar, log):
    # Calendar events documentation: https://developers.google.com/calendar/v3/reference/events?hl=en_US

    log.info(f"Downloading events from {calendar['name']} (ID: {calendar['id']})")

    now = datetime.datetime.utcnow().isoformat() + 'Z' # 'Z' indicates UTC time
    page_token = None
    while True:

        #makes the call to the api to return a list of upcoming events
        events_result = service.events().list(calendarId=calendar['id'],
                                            timeMin=now,
                                            singleEvents=True,
                                            pageToken=page_token,
                                            maxResults=2500,
                                            orderBy='startTime').execute()
        events = events_result.get('items', [])

        #just returns if there are no upcoming events
        if not events:
            log.info('No upcoming events found.')
            break

        #returns the events the calendar has not responded to
        events_to_respond_to = check_response_status(events, calendar, log)

        #checks who the organizer of each event is and accepts or declines the event
        respond_to_events(events_to_respond_to, service, calendar, log)

        #continues to process events if there are more to process, returns if not
        page_token = events_result.get('nextPageToken')
        if not page_token:
            break

####################################################################

def main():
    args = setup_cli_args()

    log = ECC.setup_logging(info=args.verbose,
                            debug=args.debug,
                            logfile=args.logfile)

    # Note: these logins have been configured on the Google cloud
    # console to only allow logins with @epiphanycatholicchurch.org
    # accounts.  If the login flow runs in a browser where you are
    # logged in to a non-@epiphanycatholicchurch.org account, it will
    # display some kind of error.  No problem: just take the URL from
    # the console window and paste it into a browser that is logged in
    # to an @epiphanycatholicchurch.org account.

    apis = {
        'calendar': { 'scope'       : Google.scopes['calendar'],
                      'api_name'    : 'calendar',
                      'api_version' : 'v3' },
    }
    services = GoogleAuth.service_oauth_login(apis,
                                              app_json=args.app_id,
                                              user_json=args.user_credentials)
    calendar_service = services['calendar']

    #iterates through the list of calendars to check for upcoming events and respond to them
    for calendar in calendars:
        process_events(calendar_service, calendar, log)
    log.info(f"Finished responding to upcoming events")

if __name__ == '__main__':
    main()
