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

import time
import datetime

from oauth2client import tools

from pprint import pprint
from pprint import pformat
from dateutil.parser import parse

default_app_json  = 'gcalendar-reservations-client-id.json'
default_user_json = 'user-credentials.json'

verbose = True
debug   = False
logfile = None

max_upload_retries = 5

test_calendar1_id = 'c_bj96menjelb4pecracnninf45k@group.calendar.google.com'
test_calendar2_id = 'c_ncm1ib261lp6c02i46mors4isc@group.calendar.google.com'

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

    global args
    args = tools.argparser.parse_args()

    # --debug implies --verbose
    if args.debug:
        args.verbose = True

    return args

####################################################################

def foo(service):
    # Calendar events documentation: https://developers.google.com/calendar/v3/reference/events?hl=en_US

    # Get upcoming 10 events (from https://developers.google.com/calendar/quickstart/python?hl=en_US)
    now = datetime.datetime.utcnow().isoformat() + 'Z' # 'Z' indicates UTC time
    events_result = service.events().list(calendarId=test_calendar1_id, timeMin=now,
                                        maxResults=10, singleEvents=True,
                                        orderBy='startTime').execute()
    events = events_result.get('items', [])

    if not events:
        print('No upcoming events found.')
    for event in events:
        start = event['start'].get('dateTime', event['start'].get('date'))
        print(f'{start}: {event["summary"]} ({event["status"]})')
        print(f'{event}')

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
    service = services['calendar']
    log.info(f"Got service: {service}")

    foo(service)

if __name__ == '__main__':
    main()
