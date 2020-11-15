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
from datetimerange import DateTimeRange

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
        "check_conflicts" : True,
    },
    {
        "name" : "Test calendar #2",
        "id" : 'c_ncm1ib261lp6c02i46mors4isc@group.calendar.google.com',
        "check_conflicts" : True,
    },
    {
        "name" : "Epiphany Events",
        "id" : "churchofepiphany.com_9gueg54raienol399o0jtdgmpg@group.calendar.google.com",
        "check_conflicts" : False,
    },
    {
       "name" : "Musicians calendar",
       "id" : "churchofepiphany.com_ga4018ieg7n3q71ihs1ovjo9c0@group.calendar.google.com",
        "check_conflicts" : True,
    },
    {
       "name" : "Area E (CC)",
       "id" : "churchofepiphany.com_2d3336353235303639373131@resource.calendar.google.com",
        "check_conflicts" : True,
    },
    {
       "name" : "Area F (CC)",
       "id" : "churchofepiphany.com_2d3336333531363533393538@resource.calendar.google.com",
        "check_conflicts" : True,
    },
    {
       "name" : "Area G (CC)",
       "id" : "churchofepiphany.com_2d33363137333031353534@resource.calendar.google.com",
        "check_conflicts" : True,
    },
    {
       "name" : "Area H (CC)",
       "id" : "churchofepiphany.com_2d33353938373132352d343735@resource.calendar.google.com",
        "check_conflicts" : True,
    },
    {
       "name" : "Area I (CC)",
       "id" : "churchofepiphany.com_2d33353739373832333731@resource.calendar.google.com",
        "check_conflicts" : True,
    },
    {
       "name" : "Area J (CC)",
       "id" : "churchofepiphany.com_2d333535383831322d32@resource.calendar.google.com",
        "check_conflicts" : True,
    },
    {
       "name" : "Area K (CC)",
       "id" : "churchofepiphany.com_2d3335333231363832383335@resource.calendar.google.com",
        "check_conflicts" : True,
    },
    {
       "name" : "Area L (CC)",
       "id" : "churchofepiphany.com_2d3335313431363234383230@resource.calendar.google.com",
        "check_conflicts" : True,
    },
    {
       "name" : "Chapel (WC)",
       "id" : "churchofepiphany.com_2d3431353233343734323336@resource.calendar.google.com",
        "check_conflicts" : True,
    },
    {
       "name" : "Coffee Bar Room (CC)",
       "id" : "churchofepiphany.com_2d38343237303931342d373732@resource.calendar.google.com",
        "check_conflicts" : True,
    },
    {
       "name" : "Connector table 1",
       "id" : "churchofepiphany.com_2d3538323334323031353338@resource.calendar.google.com",
        "check_conflicts" : True,
    },
    {
       "name" : "Connector table 2",
       "id" : "churchofepiphany.com_2d3538313436353238373034@resource.calendar.google.com",
        "check_conflicts" : True,
    },
    {
       "name" : "Connector table 3",
       "id" : "churchofepiphany.com_2d3538303631303232333033@resource.calendar.google.com",
        "check_conflicts" : True,
    },
    {
       "name" : "Dining Room (EH)",
       "id" : "churchofepiphany.com_34373539303436353836@resource.calendar.google.com",
        "check_conflicts" : True,
    },
    {
       "name" : "Kitchen (CC)",
       "id" : "churchofepiphany.com_34383131343230342d333531@resource.calendar.google.com",
        "check_conflicts" : True,
    },
    {
       "name" : "Kitchen (EH)",
       "id" : "churchofepiphany.com_2d36363539313732302d343738@resource.calendar.google.com",
        "check_conflicts" : True,
    },
    {
       "name" : "Library (CC)",
       "id" : "churchofepiphany.com_2d3131393638363634343630@resource.calendar.google.com",
        "check_conflicts" : True,
    },
    {
       "name" : "Lighthouse",
       "id" : "churchofepiphany.com_2d38303937383836353134@resource.calendar.google.com",
        "check_conflicts" : True,
    },
    {
       "name" : "Living Room (EH)",
       "id" : "churchofepiphany.com_37313933333139382d323530@resource.calendar.google.com",
        "check_conflicts" : True,
    },
    {
       "name" : "Media cart and projector",
       "id" : "churchofepiphany.com_2d37353236313138352d373236@resource.calendar.google.com",
        "check_conflicts" : True,
    },
    {
       "name" : "Narthex Gathering Area (WC)",
       "id" : "churchofepiphany.com_3334313632303539343135@resource.calendar.google.com",
        "check_conflicts" : True,
    },
    {
       "name" : "Nursery (CC)",
       "id" : "churchofepiphany.com_2d353231343439392d34@resource.calendar.google.com",
        "check_conflicts" : True,
    },
    {
       "name" : "Projector screen (large)",
       "id" : "churchofepiphany.com_2d39343734383435352d323039@resource.calendar.google.com",
        "check_conflicts" : True,
    },
    {
       "name" : "Projector screen (small)",
       "id" : "churchofepiphany.com_2d37313836393635372d313838@resource.calendar.google.com",
        "check_conflicts" : True,
    },
    {
       "name" : "Quiet Room (WC)",
       "id" : "churchofepiphany.com_2d36343734343332342d353333@resource.calendar.google.com",
        "check_conflicts" : True,
    },
    {
       "name" : "Worship Space",
       "id" : "churchofepiphany.com_33363131333030322d363435@resource.calendar.google.com",
        "check_conflicts" : True,
    }
]

#list of the domains the calendar will accept events from, will decline events from all others
acceptable_domains = {
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

####################################################################

def check_for_conflicts(events_to_check, events, calendar, service, log):
    if not calendar['check_conflicts']:
        log.info(f"Not checking {calendar['name']} for conflicts")
        return
 
    # iterate through the list of all of the events and finds any that conflict with the event in question
    conflicting_events = []
    accepted_events = []

    one_second = datetime.timedelta(seconds=1)

    for all_the_events in [events_to_check, events]:
        for event in all_the_events:
            # Victoria to put in a good comment here as to why we're adding/subtracting one second here
            # Handle the case where dateTime does not exist -- e.g., start only has date and end only has date.
            # If start with no startTime, then make the start time be 00:00
            # If end with no endTime, then make the end time be 23:59
            try:
                start = datetime.datetime.fromisoformat(event['start']['dateTime']) + one_second
                end = datetime.datetime.fromisoformat(event['end']['dateTime']) - one_second
                event['dtr'] = DateTimeRange(start, end)
            except Exception as e:
                log.error(f"Some kind of error trying to make datetimeranges: {e}")
                log.error(f"Calendar of the problem: {calendar['name']}")
                log.error(f"The event in question is: {event}")
                exit(1)

    log.debug(f"Len of events to check: {len(events_to_check)}")
    log.debug(f"Len of events: {len(events)}")

    orderable_events = dict()
    for event_to_check in events_to_check:
        dt = event_to_check['created']
        if dt not in orderable_events:
            orderable_events[dt] = list()
        orderable_events[dt].append(event_to_check)

    for created_dt in sorted(orderable_events):
        for event_to_check in orderable_events[created_dt]:
            conflicting = False
            for event in events:
                if event_to_check['dtr'].is_intersection(event['dtr']):
                    log.debug(f"Found a conflicting event: {event['id']}")
                    conflicting_events.append(event_to_check)
                    conflicting = True
            if not conflicting:
                log.debug(f"Found an event to accept!  Huzzah! {event['id']}")
                accepted_events.append(event_to_check)
                events.append(event_to_check)

    #declines all of the events that conflict with others, accepts all others
    respond_to_events(conflicting_events, 'declined', service, calendar, log)
    respond_to_events(accepted_events, 'accepted', service, calendar, log)

####################################################################

def respond_to_events(events_to_respond_to, response, service, calendar, log):

    for event in events_to_respond_to:
        log.info(f"Event {event['summary']} {event['id']}: will be {response}")

        response_body =   {
                "attendees" : [
                    {
                        "email" : calendar['id'],
                        "responseStatus" : response,
                    },
                ],
            }

        log.debug(f"Response body: {response_body}")

        if not args.dry_run:
            service.events().patch(
                calendarId = calendar['id'],
                sendUpdates = "all",
                eventId = event['id'],
                body = response_body,
            ).execute()
            log.info(f"Successfully {response} event {event['summary']} {event['id']}")
        else:
            log.info(f"dry-run: would have {response} event {event['summary']} {event['id']}")

####################################################################

def process_events(service, calendar, log):
    # Calendar events documentation: https://developers.google.com/calendar/v3/reference/events?hl=en_US

    log.info(f"Downloading events from {calendar['name']} (ID: {calendar['id']})")

    # Victoria to put in a good comment explaining why we start 31 days ago. :-)
    start = datetime.datetime.utcnow()
    start -= datetime.timedelta(days=31)
    now = start.isoformat() + 'Z' # 'Z' indicates UTC time
    page_token = None
    events = list()
    while True:

        #makes the call to the api to return a list of upcoming events
        events_result = service.events().list(calendarId=calendar['id'],
                                            timeMin=now,
                                            singleEvents=True,
                                            pageToken=page_token,
                                            maxResults=2500,
                                            orderBy='startTime').execute()
        new_events = events_result.get('items', [])

        #just returns if there are no upcoming events
        if not new_events:
            break
        
        events.extend(new_events)

        #continues to process events if there are more to process, returns if not
        page_token = events_result.get('nextPageToken')
        if not page_token:
            break

    events_to_decline = []
    acceptable_events = []
    all_other_events = []

    for event in events:
        found = False
        if "attendees" in event: #determines whether the event has any attendees
            for attendee in event["attendees"]:
                if attendee["email"] == calendar['id']:
                    if attendee["responseStatus"] == "needsAction":
                        found = True
                        organizer_email = event["organizer"]["email"]
                        organizer_domain = organizer_email.split('@')[1]
                        if (organizer_domain in acceptable_domains):
                            acceptable_events.append(event)
                        else:
                            events_to_decline.append(event)
                    elif attendee["responseStatus"] == "declined":
                        found = True
        if not found:
            all_other_events.append(event)

    # Decline all events that we know we can decline
    respond_to_events(events_to_decline, 'decline', service, calendar, log)

     #responds to the events depending on whether they conflict with another event or not
    check_for_conflicts(acceptable_events, all_other_events, calendar, service, log)

####################################################################

def main():
    setup_cli_args()

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
