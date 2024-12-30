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

import httplib2
import requests
import mimetypes

from pprint import pprint
from pprint import pformat
from googleapiclient.errors import HttpError
from google.api_core import exceptions
from google.api_core import retry
from google.auth import exceptions as auth_exceptions

# Globals

mime_types = {
    'doc'        : 'application/vnd.google-apps.document',
    'sheet'      : 'application/vnd.google-apps.spreadsheet',
    'folder'     : 'application/vnd.google-apps.folder',

    # JMS this is probably a lie, but it's useful for comparisons
    'team_drive'   : 'application/vnd.google-apps.team_drive',
    'shared_drive' : 'application/vnd.google-apps.team_drive',

    # Use the mime types as defined by a publicly-maintained python
    # module (vs. hard-coding our own values).
    'json'       : mimetypes.guess_type('file:///foo.json')[0],

    'mp3'        : mimetypes.guess_type('file:///foo.mp3')[0],

    'csv'        : mimetypes.guess_type('file:///foo.csv')[0],

    'pdf'        : mimetypes.guess_type('file:///foo.pdf')[0],

    'html'       : mimetypes.guess_type('file:///foo.html')[0],

    'xlsx'       : mimetypes.guess_type('file:///foo.xlsx')[0],
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

# Took idea for this from
# https://github.com/googleapis/python-api-core/blob/main/google/api_core/retry.py
retry_errors = retry.if_exception_type(
    exceptions.InternalServerError,
    exceptions.TooManyRequests,
    exceptions.ServiceUnavailable,
    requests.exceptions.ConnectionError,
    requests.exceptions.ChunkedEncodingError,
    auth_exceptions.TransportError,

    # According to https://developers.google.com/analytics/devguides/reporting/mcf/v3/limits-quotas,
    # 403 and 429 can be returned for exceeding API call quotas
    exceptions.Forbidden, # 403
    exceptions.TooManyRequests, # 429

    # However, from empirical evidence (didn't chase down the source code, but I
    # saw this happen a lot), when we get quota violations, the Google library
    # doesn't seem to raise either of the above exceptions.  Instead it raises
    # HttpError... which is unfortunately fairly generic.  It looks like this:
    #
    #  File "/Users/jsquyres/git/personal/epiphany/media/linux/pds-sqlite3-queries/py39/lib/python3.9/site-packages/googleapiclient/http.py", line 1123, in _process_response
    #    raise HttpError(resp, content, uri=self.uri)
    # googleapiclient.errors.HttpError: <HttpError 403 when requesting https://www.googleapis.com/upload/drive/v3/files/1aIoStpSOsup8XL5eNd8nhpJwM-IqN2gTkwVf_Qvlylc?supportsAllDrives=true&fields=id&alt=json&uploadType=resumable returned "User rate limit exceeded.". Details: "[{'domain': 'usageLimits', 'reason': 'userRateLimitExceeded', 'message': 'User rate limit exceeded.'}]">
    #
    # So let's add HttpError in here as well.  If we retry a few time for legit
    # HTTP errors because we're being overly broad... oh well.
    HttpError,
)

# Make a Google API call.  If it fails, try again.
#
@retry.Retry(predicate=retry_errors)
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

        except Exception as e:
            log.error("*** Some unknown error occurred")
            log.error(e)
            raise

    # If we get here, it's failed multiple times -- time to bail...
    log.error("Error: we failed this API call {count} times; there's no reason to believe it'll work if we do it again..."
              .format(count=max_retries))
    exit(1)
