#!/usr/bin/env python

# First, need to install the Google API python client:
#     pip install --upgrade google-api-python-client

# This is very helpful to read:
# https://developers.google.com/identity/protocols/OAuth2
# We are using the "Installed Applications" scheme.

# This is very helpful to read:
# https://developers.google.com/api-client-library/python/start/get_started
# We are using Authorized API access (OAuth 2.0).

# Steps:
# 1. Request a(n application) token
# 2. Provider user consent
# 3. Get an authorization code from Google
# 4. Send the code to Google
# 5. Receive access token and refresh token
# 6. Can make API calls with the access token
# 7. If the access token is expired, use the refresh token.  If the
#    refresh token doesn't work, go back to step 2 (or step 1?).

import json
import sys
import os
import re
import time
import httplib2
import calendar

from pprint import pprint

from apiclient.discovery import build
from apiclient.http import MediaFileUpload
from oauth2client import tools
from oauth2client.file import Storage
from oauth2client.client import AccessTokenRefreshError
from oauth2client.client import OAuth2WebServerFlow

# Globals
app_cred_file = 'client_id.json'
user_cred_file = 'user-credentials.json'
user_agent = 'py_mp3_uploader'
target_team_drive = 'ECC Recordings'
folder_mime_type = 'application/vnd.google-apps.folder'
source_directory = 'C:\ftp\ecc-recordings'
mp3_mime_type = 'audio/mpeg'
# Scopes documented here:
# https://developers.google.com/drive/v3/web/about-auth
scope = 'https://www.googleapis.com/auth/drive'

# JMS delete me
source_directory = '.'

#-------------------------------------------------------------------

def load_app_credentials():
    # Read in the JSON file to get the client ID and client secret
    cwd  = os.getcwd()
    file = os.path.join(cwd, app_cred_file)
    if not os.path.isfile(file):
	print("Error: JSON file {0} does not exist".format(file))
	exit(1)
    if not os.access(file, os.R_OK):
	print("Error: JSON file {0} is not readable".format(file))
	exit(1)

    with open(file) as data_file:
	app_cred = json.load(data_file)

    print('=== Loaded application credentials from {0}'
	  .format(file))
    return app_cred

#-------------------------------------------------------------------

def load_user_credentials(scope, app_cred):
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

    print('=== Loaded user credentials from {0}'
	  .format(file))
    return user_cred

#-------------------------------------------------------------------

def authorize(user_cred):
    http    = httplib2.Http()
    http    = user_cred.authorize(http)
    service = build('drive', 'v3', http=http)

    print('=== Authorized to Google')
    return service

####################################################################

def upload_file(service, team_drive, dest_folder, upload_filename):
    try:
	print('=== Uploading file "{0}" (parent: {1})'
	      .format(upload_filename, dest_folder['id']))
	metadata = {
	    'name' : upload_filename,
	    'mimeType' : mp3_mime_type,
	    'parents' : [ dest_folder['id'] ]
	    }
	media = MediaFileUpload(upload_filename,
				mimetype=mp3_mime_type,
				resumable=True)
	file = service.files().create(body=metadata,
				      media_body=media,
				      supportsTeamDrives=True,
				      fields='id').execute()
	print('=== Successfully uploaded file: "{0}" (ID: {1})'
	      .format(upload_filename, file.get('id')))
	return True

    except:
	print('=== Google upload failed for some reason -- will try again later')
	return False

#-------------------------------------------------------------------

def create_folder(service, team_drive, folder_name, parent_id):
    print("=== Creating folder {0}, parent {1}".format(folder_name, parent_id))
    metadata = {
	'name' : folder_name,
	'mimeType' : folder_mime_type,
	'parents' : [ parent_id ]
	}
    folder = service.files().create(body=metadata,
				    supportsTeamDrives=True,
				    fields='id').execute()
    print('=== Created folder: "{0}" (ID: {1})'
	  .format(folder_name, folder.get('id')))
    return folder

#-------------------------------------------------------------------

def find_or_create_folder(service, team_drive, folder_name, parent_id):
    # Find a folder identified by this name/parent.  If it doesn't
    # exist, create it.
    try:
	# Don't worry about pagination, because we expect to only get
	# 0 or 1 results back.
	query = ("name='{0}' and mimeType='{1}' and trashed=false"
		 .format(folder_name, folder_mime_type))
	if parent_id is not None:
	    query = query + (" and '{0}' in parents"
			     .format(parent_id))
	print("=== Folder query: {0}".format(query))
	response = (service.files()
		    .list(q=query,
			  spaces='drive',
			  corpora='teamDrive',
			  fields='files(name,id,parents)',
			  teamDriveId=team_drive['id'],
			  includeTeamDriveItems=True,
			  supportsTeamDrives=True).execute())
	folders = response.get('files', [])

	# If we got more than 1 result back, let a human figure it out
	if len(folders) > 1:
	    print('Error: found more than one folder matching name="{0}", parents={1}!'.format(folder_name, parent_id))
	    print('Error: a human should fix this in the Google Drive web interface.')
	    print('Aborting')
	    exit(1)

	# If we got 0 results back, then go create that folder
	elif len(folders) == 0:
	    print("=== Folder not found")
	    return create_folder(service, team_drive, folder_name,
				 parent_id)

	# Otherwise, we found it.  Yay!
	else:
	    folder = folders[0]
	    print('=== Found target folder: "{0}" (ID: {1})'
		  .format(folder_name, folder['id']))
	    return folder

    except AccessTokenRefreshError:
	# The AccessTokenRefreshError exception is raised if the
	# credentials have been revoked by the user or they have
	# expired.
	print('The credentials have been revoked or expired, '
	      'please re-run the application to re-authorize')
	exit(1)

#-------------------------------------------------------------------

def create_dest_folder(service, team_drive, year, month):
    # Look for the year folder at the top of the team drive
    year_folder = find_or_create_folder(service, team_drive, year,
					team_drive['id'])

    # Look for the month folder in the year folder
    month_folder = find_or_create_folder(service, team_drive, month,
					 year_folder['id'])

    return month_folder

#-------------------------------------------------------------------

def upload_mp3(service, team_drive, year, month, file):
    folder = create_dest_folder(service, team_drive, year, month)
    success = upload_file(service, team_drive, folder, file)

    # If we succeeded, remove the file from the local filesystem
    if success:
	print('=== Moved {0} to "Uploaded" folder'.format(file))
	try:
	    os.mkdir("Uploaded")
	except:
	    pass
	os.rename(file, os.path.join("Uploaded", file))

#-------------------------------------------------------------------

def watch_for_new_mp3s(service, team_drive, source_dir):
    seen_files = {}
    while True:
	print('=== Checking {0} at {1}'.format(source_dir,
					       time.asctime(time.localtime())))
	files = os.listdir(source_dir)
	for file in files:
	    m = re.match(pattern='^T\d+-(\d\d\d\d)(\d\d)\d\d-\d\d\d\d\d\d.mp3$',
			 flags=re.IGNORECASE,
			 string=file)
	    if m is None:
		continue

	    year = m.group(1)
	    month_num = m.group(2)
	    month = "{0}-{1}".format(month_num,
				     calendar.month_name[int(month_num)])

	    # If the filename matches the pattern, first check to see
	    # if the file is still being uploaded to us.  Check by
	    # file size.
	    s = os.stat(file)

	    # If the filename matches the pattern,
	    # check to see if it's file size is still changing.
	    if file not in seen_files:
		print("=== Found MP3 {0} with file size {1}"
		      .format(file, s.st_size))
		seen_files[file] = s.st_size
		continue

	    else:
		# If the file size is the same, then it's probably no
		# longer changing, and it's safe to upload.
		if seen_files[file] != s.st_size:
		    print("=== Found MP3 {0}; file size changed to {1}"
			  .format(file, s.st_size))
		    seen_files[file] = s.st_size
		    continue

		else:
		    print("=== Found MP3 {0}; file size did not change"
			  .format(file))
		    upload_mp3(service, team_drive, year, month, file)
		    del seen_files[file]

	# Once we're done traversing the files in the directory, clean
	# up any files in seen_files that no longer exist (must do
	# this in 2 loops: it's not safe to remove a key from a
	# dictionary that you're iterating over).
	to_remove = []
	for file in seen_files:
	    if not os.path.isfile(file):
		to_remove.append(file)
	for file in to_remove:
	    del seen_files[file]

	# Wait a little bit, and then check again
	time.sleep(30)

#-------------------------------------------------------------------

def find_team_drive(service, target_name):
    try:
	page_token = None
	while True:
	    response = (service.teamdrives()
			       .list(pageToken=page_token).execute())
	    for team_drive in response.get('teamDrives', []):
		if team_drive['name'] == target_name:
		    print('=== Found target Team Drive: "{0}" (ID: {1})'
			  .format(target_name, team_drive['id']))
		    return team_drive

	    page_token = response.get('nextPageToken', None)
	    if page_token is None:
		break

	# If we get here, we didn't find the target team drive
	print("Error: Could not find the target Team Drive ({0})"
	      .format(target_team_drive))
	print("Error: Aborting")
	exit(1)

    except AccessTokenRefreshError:
	# The AccessTokenRefreshError exception is raised if the
	# credentials have been revoked by the user or they have
	# expired.
	print('The credentials have been revoked or expired, '
	      'please re-run the application to re-authorize')
	exit(1)

#-------------------------------------------------------------------

def main():
    # Authorize the app and provide user consent to Google
    app_cred = load_app_credentials()
    user_cred = load_user_credentials(scope, app_cred)
    service = authorize(user_cred)

    # Find the target team drive to which we want to upload
    team_drive = find_team_drive(service, target_team_drive)

    # Endlessly watch for new files to appear in the source directory,
    # and upload them to Google
    watch_for_new_mp3s(service, team_drive, source_directory)

if __name__ == '__main__':
    main()
