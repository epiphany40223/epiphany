#!/usr/bin/env python3

import httplib2
import json
import os

from oauth2client import tools
from oauth2client.file import Storage
from oauth2client.client import OAuth2WebServerFlow

#-------------------------------------------------------------------

# Globals
doc_mime_type = 'application/vnd.google-apps.document';
sheet_mime_type = 'application/vnd.google-apps.spreadsheet';
folder_mime_type = 'application/vnd.google-apps.folder'

# JMS this is probably a lie, but it's useful for comparisons
team_drive_mime_type = 'application/vnd.google-apps.team_drive'



# JMS Should these really be globals?
app_cred_file = 'client_id.json'
default_user_cred_file = 'user-credentials.json'
user_agent = 'gxcopy'

# Scopes documented here:
# https://developers.google.com/drive/v3/web/about-auth
# JMS is this really a global?
drive_scope = 'https://www.googleapis.com/auth/drive'

#-------------------------------------------------------------------

def load_app_credentials(app_cred_file):
    # Read in the JSON file to get the client ID and client secret
    cwd  = os.getcwd()
    file = os.path.join(cwd, app_cred_file)
    if not os.path.isfile(file):
        diediedie("Error: JSON file {0} does not exist".format(file))
    if not os.access(file, os.R_OK):
        diediedie("Error: JSON file {0} is not readable".format(file))

    with open(file) as data_file:
        app_cred = json.load(data_file)

    log.debug('Loaded application credentials from {0}'
                  .format(file))
    return app_cred

def load_user_credentials(scope, app_cred, user_cred_file=default_user_cred_file):
    # Get user consent
    client_id       = app_cred['installed']['client_id']
    client_secret   = app_cred['installed']['client_secret']
    flow            = OAuth2WebServerFlow(client_id, client_secret, scope)
    flow.user_agent = user_agent

    cwd       = os.getcwd()
    file      = os.path.join(cwd, user_cred_file)
    storage   = Storage(file)
    user_cred = storage.get()

    # If no credentials are able to be loaded, fire up a web
    # browser to get a user login, etc.  Then save those
    # credentials in the file listed above so that next time we
    # run, those credentials are available.
    if user_cred is None or user_cred.invalid:
        user_cred = tools.run_flow(flow, storage,
                                   tools.argparser.parse_args())

    log.debug('Loaded user credentials from {0}'
              .format(file))
    return user_cred

def authorize(user_cred):
    http    = httplib2.Http()
    http    = user_cred.authorize(http)
    service = build('drive', 'v3', http=http)

    log.debug('Authorized to Google')
    return service
