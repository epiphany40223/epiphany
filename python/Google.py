#!/usr/bin/env python3
#
# Utility Google functions
#
# Need to:
#
# pip3 install --upgrade httplib2
# pip3 install --upgrade google-api-python-client oauth2client
#

import time
import traceback

import httplib2

from pprint import pprint
from pprint import pformat
from apiclient.errors import HttpError

# Globals

mime_types = {
    'doc'        : 'application/vnd.google-apps.document',
    'sheet'      : 'application/vnd.google-apps.spreadsheet',
    'folder'     : 'application/vnd.google-apps.folder',

    'json'       : 'application/json',

    'mp3'        : 'audio/mpeg',

    'csv'        : 'text/csv',

    'xlsx'       : 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',

    # JMS this is probably a lie, but it's useful for comparisons
    'team_drive' : 'application/vnd.google-apps.team_drive',
}

# Scopes documented here:
# https://developers.google.com/drive/v3/web/about-auth
scopes = {
    'drive'    : 'https://www.googleapis.com/auth/drive',
    'admin'    : 'https://www.googleapis.com/auth/admin.directory.group',
    'group'    : 'https://www.googleapis.com/auth/apps.groups.settings',
    'reports'  : 'https://www.googleapis.com/auth/admin.reports.audit.readonly',
    'calendar' : 'https://www.googleapis.com/auth/calendar',
}

####################################################################

# Make a Google API call.  If it fails, try again.
#
def call_api(httpref, log, max_retries=3, can_fail=False):
    log.debug("Executing Google API call (will try up to {count} times): {h}"
              .format(count=max_retries, h=httpref))

    for count in range(max_retries):
        try:
            ret = httpref.execute()
            return ret

        except HttpError as err:
            log.debug("*** Got HttpError:")
            log.debug(pformat(err))
            if err.resp.status in [500, 503]:
                log.debug("*** Seems recoverable; let's sleep and try again...")
                time.sleep(5)
                continue
            elif err.resp.status == 403:
                log.debug("*** Permission denied, but that's ok -- we'll skip it for now...")
                return None
            else:
                log.debug("*** Doesn't seem recoverable (status {0}) -- aborting"
                          .format(err.resp.status))
                log.debug(err)
                raise

        except:
            log.error("*** Some unknown error occurred")
            log.error(sys.exc_info()[0])
            raise

    # If we get here, it's failed multiple times -- time to bail...
    log.error("Error: we failed this API call {count} times; there's no reason to believe it'll work if we do it again..."
              .format(count=max_retries))
    exit(1)
