#!/usr/bin/env python3

#
# Upload a file to Google Drive based on provided information
#

import os
import sys

import ECC
import Google
import GoogleAuth

from apiclient.http import MediaFileUpload
from google.api_core import retry

###########################################################

def setup_services(app_json, user_json, log):
    # Note: these logins have been configured on the Google cloud
    # console to only allow logins with @epiphanycatholicchurch.org
    # accounts.  If the login flow runs in a browser where you are
    # logged in to a non-@epiphanycatholicchurch.org account, it will
    # display some kind of error.  No problem: just take the URL from
    # the console window and paste it into a browser that is logged in
    # to an @epiphanycatholicchurch.org account.

    apis = {
        'drive'   : { 'scope'       : Google.scopes['drive'],
                      'api_name'    : 'drive',
                      'api_version' : 'v3' },
    }
    services = GoogleAuth.service_oauth_login(apis, app_json, user_json, log=log)

    return services['drive']

###########################################################

def verify_target_google_folder(service, folder_id, log):
    http = service.files().get(fileId=folder_id,
                               fields='id,mimeType,name,webViewLink,parents',
                               supportsTeamDrives=True)
    folder = Google.call_api(http, log=log)

    if folder is None or folder['mimeType'] != Google.mime_types['folder']:
        log.error(f'Error: Could not find any contents of folder ID: {folder_id}')
        exit(1)

    log.info(f"Valid folder ID: {folder_id} ({folder['name']})")


###########################################################

def upload_to_google(service, filename, filetype, folder_id, log):

    try:
        log.info('Uploading file to google "{file}"'
                 .format(file=filename))
        metadata = {
            'name'     : filename,
            'mimeType' : Google.mime_types[filetype],
            'parents'  : [ folder_id ],
            'supportsTeamDrives' : True,
        }
        media = MediaFileUpload(filename,
                                mimetype=Google.mime_types[filetype],
                                resumable=True)
        http = service.files().create(body=metadata,
                                      media_body=media,
                                      supportsTeamDrives=True,
                                      fields='id')
        response = Google.call_api(http, log)

        log.info('Successfully uploaded file: "{filename}" (ID: {id})'
                 .format(filename=filename, id=response['id']))
        return

    except Exception as e:
        log.error('Google upload failed for some reason:')
        log.error(e)
        raise e

    log.error("Google upload failed!")


###########################################################