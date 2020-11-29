#!/usr/bin/env python3

#
# Setup for this directory:
#
# 1. If on Linux or MacOS, create a virtual environment (you can do this in Windows too, but I think the mechanics might be a bit different)
#
# virtualenv --python=YOUR_PYTHON DIR_NAME
#
# My local python is "python3.8", so I use --python=python3.8.
# And since it's python 3.8, I use "py38" for DIR_NAME.
#
# 2. Activate the virtual environment:
#
# . ./DIR_NAME/bin/activate
#
# 3. Pip install the packages in requirements.txt.
#
# pip install `cat requirements.txt`
#
# Now you're good to go.
#

import sys
sys.path.insert(0, '../../../python')

import ECC
import Google
import GoogleAuth

from oauth2client import tools

# Globals

gapp_id         = 'client_id.json'
guser_cred_file = 'user-credentials.json'

####################################################################

def do_google_drive_things(service, log):
    results = service.files().list(corpora='drive',
                                driveId='0ALjviy3LdGU5Uk9PVA',
                                includeItemsFromAllDrives=True,
                                supportsAllDrives=True,
                                fields='files').execute()

    for entry in results['files']:
        log.info(f'Found file "{entry["name"]} (ID: {entry["id"]})')

####################################################################

def setup_cli_args():
    tools.argparser.add_argument('--logfile',
                                 help='Also save to a logfile')
    tools.argparser.add_argument('--debug',
                                 action='store_true',
                                 default=False,
                                 help='Be extra verbose')

    global gapp_id
    tools.argparser.add_argument('--app-id',
                                 default=gapp_id,
                                 help='Filename containing Google application credentials')
    global guser_cred_file
    tools.argparser.add_argument('--user-credentials',
                                 default=guser_cred_file,
                                 help='Filename containing Google user credentials')

    args = tools.argparser.parse_args()

    return args

####################################################################
#
# Main
#
####################################################################

def main():
    args = setup_cli_args()

    log = ECC.setup_logging(info=True,
                            debug=args.debug,
                            logfile=args.logfile)

    apis = {
        'drive' : { 'scope'       : Google.scopes['drive'],
                    'api_name'    : 'drive',
                    'api_version' : 'v3', },
    }
    services = GoogleAuth.service_oauth_login(apis,
                                              app_json=args.app_id,
                                              user_json=args.user_credentials,
                                              log=log)

    do_google_drive_things(services['drive'], log)


if __name__ == '__main__':
    main()
