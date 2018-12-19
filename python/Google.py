#!/usr/bin/env python3
#
# Utility Google functions
#

mime_types = {
    'doc'        : 'application/vnd.google-apps.document',
    'sheet'      : 'application/vnd.google-apps.spreadsheet',
    'folder'     : 'application/vnd.google-apps.folder',

    'json'       : 'application/json',

    'mp3'        : 'audio/mpeg',

    'csv'        : 'text/csv',

    # JMS this is probably a lie, but it's useful for comparisons
    'team_drive' : 'application/vnd.google-apps.team_drive',
}

# Scopes documented here:
# https://developers.google.com/drive/v3/web/about-auth
scopes = {
    'drive'   : 'https://www.googleapis.com/auth/drive',
    'admin'   : 'https://www.googleapis.com/auth/admin.directory.group',
    'group'   : 'https://www.googleapis.com/auth/apps.groups.settings',
    'reports' : 'https://www.googleapis.com/auth/admin.reports.audit.readonly',
}
