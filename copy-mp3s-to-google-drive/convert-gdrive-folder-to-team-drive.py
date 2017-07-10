#!/usr/bin/env python

"""Script to "xcopy" a Google Drive folder to a Team Drive.

This script developed and tested with Python 3.6.x.  It has not been
tested with other versions (e.g., Python 2.7.x).

Pre-requisites:
- A client_id.json file downloaded from the Google Dashboard
  (presumably of the owning organization of the destination Team
  Drive: https://console.developers.google.com/apis/credentials)
- A Google Account who is both authorized to read everything in the
  source folder tree and authorized to write into the destination Team
  Drive folder.
- pip install --upgrade google-api-python-client
- pip install --upgrade recordclass

Input:
- Source folder ID

Actions:
- Checks source folder ID to ensure it is valid/readable folder
- Checks to ensure no existing Team Drive has same name
- Creates Team Drive of same name as source folder
- Finds all files/folders in source folder
  - Creates matching folder structure in destination Team Drive folder
  - Any file that is owned by a user in the Team Drive organization
    owner is moved to the respective folder in the new Team Drive
    folder structure
  - Any file that is not owner by a user in the Team Drive
    organization is:
    1. Copied to the respective folder in the new Team Drive folder
       structure
    2. Moved to a new sub folder "MOVED TO TEAM DRIVE" in the original
       folder
    3. If the original file is a Google Doc, Sheet, or Slides file, it
       has a short blurb inserted at the top indicating that this file
       is now stale and it has moved to a Team Drive (including a link
       to the new file).
    4. A README Google Doc file is put in the old folder location
       indicating the location of the new Team Drive folder.

--> GLITCH IN THE PLANS: in Team Drives, files can only have exactly
    one parent.  :-( So if the original file has multiple parents,
    we'll just have to gather than info and print out info at the end
    about the one location where the file ended up.

"""

import json
import sys
import os
import re
import time
import httplib2
import calendar
import uuid
import logging

from pprint import pprint

from recordclass import recordclass
from apiclient.discovery import build
from apiclient.http import MediaFileUpload
from apiclient.errors import HttpError
from oauth2client import tools
from oauth2client.file import Storage
from oauth2client.client import AccessTokenRefreshError
from oauth2client.client import OAuth2WebServerFlow

# Globals
app_cred_file = 'client_id.json'
user_cred_file = 'user-credentials.json'
user_agent = 'gxcopy'
doc_mime_type = 'application/vnd.google-apps.document';
sheet_mime_type = 'application/vnd.google-apps.spreadsheet';
folder_mime_type = 'application/vnd.google-apps.folder'
# JMS this is probably a lie, but it's useful for comparisons
team_drive_mime_type = 'application/vnd.google-apps.team_drive'
# Scopes documented here:
# https://developers.google.com/drive/v3/web/about-auth
scope = 'https://www.googleapis.com/auth/drive'

#-------------------------------------------------------------------

# Recordclasses are effecitvely namedtuples that are mutable (i.e.,
# support assignment). These are the recordclasses that are used in
# the rest of the script.

GFile = recordclass('GFile',
		   ['id',           # string
		    'webViewLink',  # string (URL)
		    'mimeType',     # string
		    'name',         # string
		    'parents',      # list of strings (each an ID)
		    'team_file'     # GFile or None
		    ])
Tree = recordclass('Tree',
		  ['root_folder',   # See comment in read_source_tree()
		   'contents'])
ContentEntry = recordclass('ContentEntry',
			  ['gfile',      # GFile
			   'is_folder',  # boolean
			   'traverse',   # boolean
			   'contents',   # list of ContentEntry's
			   'tree'        # Tree
			   ])
AllFiles = recordclass('AllFiles',
		      ['name',           # string
		       'webViewLink',    # string (URL)
		       'parents',        # list of strings (each an ID)
		       'team_file'       # GFile
		       ])
Parent = recordclass('Parent',
		     ['id',              # string
		      'name',            # string
		      'name_abs',        # string
		      'webViewLink'      # string (URL)
		      ])

#-------------------------------------------------------------------

def diediedie(msg):
    print(msg)
    print("Aborting")

    # JMS Somehow let a human know

    exit(1)

#-------------------------------------------------------------------

def setup_logging(args):
    level=logging.ERROR

    if args.debug:
	level=logging.DEBUG
    elif args.verbose:
	level=logging.INFO

    logging.basicConfig(level=level)

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

    logging.debug('=== Loaded application credentials from {0}'
		  .format(file))
    return app_cred

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

    logging.debug('=== Loaded user credentials from {0}'
	      .format(file))
    return user_cred

def authorize(user_cred):
    http    = httplib2.Http()
    http    = user_cred.authorize(http)
    service = build('drive', 'v3', http=http)

    logging.debug('=== Authorized to Google')
    return service

####################################################################

def upload_file(service, team_drive, dest_folder, upload_filename):
    try:
	logging.info('=== Uploading file "{0}" (parent: {1})'
		 .format(upload_filename, dest_folder['id']))
	metadata = {
	    'name' : upload_filename,
	    'mimeType' : mp3_mime_type,
	    'parents' : [ dest_folder['id'] ]
	    }
	media = MediaFileUpload(upload_filename,
				mimetype=mp3_mime_type,
				resumable=True)
	file = doit(service.files().create(body=metadata,
					   media_body=media,
					   supportsTeamDrives=True,
					   fields='id'))
	logging.debug('=== Successfully uploaded file: "{0}" (ID: {1})'
		  .format(upload_filename, file.get('id')))
	return True

    except:
	logging.warn('=== Google upload failed for some reason -- will try again later')
	return False

#-------------------------------------------------------------------

# If the Google API call fails, try again...
def doit(httpref):
    count = 0
    while count < 3:
	try:
	    ret = httpref.execute()
	    return ret

	except HttpError as err:
	    logging.debug("*** Got HttpError:")
	    pprint(err)
	    if err.resp.status in [500, 503]:
		logging.debug("*** Seems recoverable; let's sleep and try again...")
		time.sleep(5)
		count = count + 1
		continue
	    else:
		logging.debug("*** Doesn't seem recoverable (status {0}) -- aborting".format(err.resp.status))
		logging.debug(err)
		raise

	except:
	    logging.error("*** Some unknown error occurred")
	    logging.error(sys.exc_info()[0])
	    raise

    # If we get here, it's failed multiple times -- time to bail...
    logging.error("=== Error: we failed this 3 times; there's no reason to believe it'll work if we do it again...")
    exit(1)

#-------------------------------------------------------------------

# parent_folder: gfile
# new_folder_name: string
def create_folder(service, parent_folder, new_folder_name):
    logging.debug("=== Creating new folder {0}, parent {1} (ID: {2})"
	      .format(new_folder_name, parent_folder.name, parent_folder.id))
    metadata = {
	'name' : new_folder_name,
	'mimeType' : folder_mime_type,
	'parents' : [ parent_folder.id ]
	}

    folder = doit(service.files().create(body=metadata,
					 supportsTeamDrives=True,
					 fields='id,name,mimeType,parents,webViewLink'))
    logging.debug('=== Created folder: "{0}" (ID: {1})'
		  .format(folder['name'], folder['id']))

    file = GFile(id=folder['id'],
		 mimeType=folder['mimeType'],
		 name=folder['name'],
		 parents=folder['parents'],
		 webViewLink=folder['webViewLink'],
		 team_file=None)
    file.team_file = file

    return file

#-------------------------------------------------------------------

# Traverse the source tree.  For each entry:
#
# - If it's a folder, make the corresponding folder in the Team Drive
# - If it's a file:
#   - Try to move it to the Team Drive.
#   - If the move fails, copy it to the Team Drive.
#
# Keep in mind the distinction between the *source* values (i.e.,
# values from the source tree) and the *team* values (i.e., values
# From the newly-created Team Drive tree).
#
# service: team drive API service
# source_root: tree (created by read_source_tree())
# team_root: gfile
# all_files: hash indexed by ID (created by read_source_tree())
#
# This routine will not be called if this is a dry run, so no need for
# such protection inside this function.
def migrate_to_team_drive(service, source_root, team_root, all_files):
    logging.debug('Migrating folder to Team Drive: "{0}"'
		  .format(source_root.root_folder.name))
    for source_entry in source_root.contents:
        logging.debug('- Migrating entry: "{0}"'
                      .format(source_entry.gfile.name))
	source_id = source_entry.gfile.id

	# Folder
	if source_entry.is_folder:
	    migrate_folder_to_team_drive(service, source_root, team_root,
					 all_files, source_entry)

	# Non-folder (i.e., file)
	else:
	    migrate_file_to_team_drive(service, source_root, team_root,
				       all_files, source_entry)

def migrate_folder_to_team_drive(service, source_root, team_root,
				 all_files, source_folder_entry):
    logging.debug('- Making sub folder: "{0}" in "{1}"'
		  .format(source_root.root_folder.name,
			  source_folder_entry.gfile.name))

    # Make the folder in the Team Drive
    source_id = source_folder_entry.gfile.id
    team_folder = create_folder(service, team_root,
				source_folder_entry.gfile.name)
    all_files[source_id].team_file = team_folder

    # Traverse into the source subfolder
    if source_folder_entry.traverse:
	migrate_to_team_drive(service,
			      source_folder_entry.tree,
			      all_files[source_id].team_file,
			      all_files)

    # If this is a non-traversable folder, that's... unexpected.
    else:
	logger.warning('Found an unexpectedly non-traversable folder:\n  "{0}" (ID: {1})'
		       .format(source_folder_entry.gfile.name,
			       source_folder_entry.gfile.id))
	logger.warning('This folder has NOT been copied to the Team Drive.')
	logger.warning('This shouldn\t happen!')

def migrate_file_to_team_drive(service, source_root, team_root,
			       all_files, source_file_entry):
    logging.debug('- Migrating file: "{0}" in "{1}"'
		  .format(source_root.root_folder.name,
			  source_file_entry.gfile.name))

    # Try to just move the file
    migrated_file = doit(service.files().update(fileId=source_file_entry.gfile.id,
                                                addParents=team_root.id,
                                                removeParents=source_file_entry.gfile.parents[0],
                                                fields='id,parents'))
    if migrated_file is None:
        # JMS try to copy
        pass
    else:
        # JMS happiness
        pass

    # JMS continue here

#-------------------------------------------------------------------

def print_multiparents(service, root, all_files):
    print('Files/folders with multiple parents (will not be copied over to the Team Drive):')
    print('')

    seen = dict()
    (found, seen) = traverse_multiparents(service, root, all_files, seen)

    if found:
	logging.error("Found at least one file/folder with multiple parents.")
	logging.error("These files/folders must be converted to having a single parent before converting over to a Team Drive.")
    else:
	print("--> None found -- yay!")

    return found

def traverse_multiparents(service, root, all_files, seen):
    ret = False

    # Iterate through all the entries in this root
    for entry in root.contents:
	id = entry.gfile.id
	if len(entry.gfile.parents) > 1 and not id in seen:
	    # Found an item with multiple parents (we only have to
	    # save "seen" IDs for those with multiple parents).
	    seen[id] = True
	    ret = True

	    type = "File"
	    if entry.is_folder:
		type = "Folder"

	    print('- {0} "{1}"\n  ID: {2}\n  URL: {3}\n  Appears in:'
		  .format(type, entry.gfile.name, id, entry.gfile.webViewLink))
	    # Print all the places this entry appears
	    for parent in all_files[id].parents:
		print('    Folder: "{0}"\n      ID: {1}\n      URL: {2}'
		      .format(parent.name_abs, parent.id,
			      parent.webViewLink))
	    print('')

    # Traverse into the sub folders of this root (the tree is already
    # marked to know how to traverse it as a DAG -- be sure to follow
    # those markings!)
    for entry in root.contents:
	if entry.is_folder and entry.traverse:
	    (sub_ret, seen) = traverse_multiparents(service, entry.tree,
						    all_files, seen)
	    if sub_ret:
		ret = True

    # Return whether we (or any recursive traversals) found any
    # multi-parent files.
    return (ret, seen)

#-------------------------------------------------------------------

# Find a list of contents of a particular root folder (GFile), and
# recursively call down into each folder.  Make a somewhat complicated
# data structure to represent the tree (remember that both files and
# folders can have multiple parents).
#
# tree:
#   .root_folder, a GFile instance:
#      .id
#      .mimeType: folder mime type
#      .name
#      .parents: list
#      .team_id: None (will be populated later)
#   .contents: list, each entry is an instance of ContentEntry, representing an item in this folder
#      .gfile, a GFile instance:
#         .id
#         .mimeType
#         .name
#         .parents
#         .team_id: None (will never be populated)
#      .is_folder: boolean, True if folder
#      .traverse: boolean, True if this is 1st time we've seen this folder
#      .tree: if traverse==True, a tree, otherwise None
#
# all_files: hash indexed by ID, each entry is:
#    .name
#    .webViewLink
#    .parents: list, each entry dictionary with these keys:
#       .parent_folder_name
#       .parent_folder_name_abs (contains entire name since root)
#       .parent_folder_id
#       .parent_folder_url: None (*may* be populated later)
#    .team_file: None (will be populated later)
#
def read_source_tree(service, prefix, root_folder, all_files):
    logging.info('=== Discovering contents of folder: "{0}" (ID: {1})'
		 .format(root_folder.name, root_folder.id))

    parent_folder_name_abs = '{0}/{1}'.format(prefix, root_folder.name)
    logging.debug('=== parent folder name abs: {0}=={1}'
		  .format(prefix, root_folder.name))
    tree = Tree(root_folder=root_folder, contents=[])

    # Iterate through everything in this root folder
    page_token = None
    query = "'{0}' in parents and trashed=false".format(root_folder.id)
    logging.debug("=== Query: {0}".format(query))
    while True:
	response = doit(service.files()
			.list(q=query,
			      spaces='drive',
			      corpora='user',
			      fields='nextPageToken,files(name,id,mimeType,parents,webViewLink)',
			      pageToken=page_token,
			      supportsTeamDrives=True))
	for file in response.get('files', []):
	    logging.info('=== Found: "{0}"'.format(file['name']))
	    id = file['id']
	    traverse = False
	    is_folder = False
	    if file['mimeType'] == folder_mime_type:
		is_folder = True

	    # We have already seen this file before
	    if id in all_files:
		logging.debug('--- We already know this file; cross-referencing...')
		# If this is a folder that we already know, then do
		# not traverse down into it (again).
		if is_folder:
		    logging.debug('--- Is a folder, but we already know it; NOT adding to pending traversal list')
		    traverse = False

	    # We have *NOT* already seen this file before
	    else:
		logging.debug('--- We do not already know this file; saving...')
		all_files[id] = AllFiles(name=file['name'],
					 webViewLink=file['webViewLink'],
					 parents=[],
					 team_file=None)

		# If it's a folder, add it to the pending traversal list
		if is_folder:
		    traverse = True
		    logging.debug("--- Is a folder; adding to pending traversal list")

	    # Save this content entry in the list of contents for this
	    # folder
	    gfile = GFile(id=id, mimeType=file['mimeType'],
			  webViewLink=file['webViewLink'],
			  name=file['name'], parents=file['parents'],
			  team_file=None)
	    content_entry = ContentEntry(gfile=gfile,
					 is_folder=is_folder,
					 traverse=traverse,
					 contents=[],
					 tree=None)
	    tree.contents.append(content_entry)

	    # Save this file in the master list of *all* files found.
	    # Basically, add a parent listing to this ID in the
	    # all_files index.
	    parent_wvl = '<Unknown>'
	    if root_folder.id in all_files:
		parent_wvl = all_files[root_folder.id].webViewLink

	    parent = Parent(id=root_folder.id, name=root_folder.name,
			    name_abs=parent_folder_name_abs,
			    webViewLink=parent_wvl)
	    all_files[id].parents.append(parent)

	page_token = response.get('nextPageToken', None)
	if page_token is None:
	    break

    # Traverse all the sub folders
    for entry in tree.contents:
	if entry.traverse:
	    new_prefix = '{0}/{1}'.format(parent_folder_name_abs,
					  entry.gfile.name)
	    logging.debug("== Traversing down into {0}"
			  .format(new_prefix))
	    (t, all_files) = read_source_tree(service,
					      parent_folder_name_abs,
					      entry.gfile, all_files)
	    entry.tree = t

    # Done!
    return (tree, all_files)

#-------------------------------------------------------------------

# In a (perhaps misguided?) attempt to reduce the number of types of
# APIs that need to be activated for this script, find the owner of
# the Team Drive that we just created by making a trivial file in that
# Team Drive, and then look at the owner meta data (vs. querying
# information about this Google Account).  Then remove the trivial
# file.
def find_team_drive_owner(service, team_drive):
    metadata = {
	'name' : 'Temporary test file from conversion script',
	'mimeType' : doc_mime_type,
	'parents' : [ team_drive.id ]
	}
    test_file = doit(service.files().create(body=metadata,
					    supportsTeamDrives=True,
					    fields='id,lastModifyingUser'))

    owner = test_file['lastModifyingUser']
    logging.info("=== Team Drive owner: {0}".format(owner['emailAddress']))

    doit(service.files().delete(fileId=test_file['id'],
				supportsTeamDrives=True))

    return owner
    # displayName
    # emailAddress
    # kind: drive#user
    # me: True
    # permissionId: number

#-------------------------------------------------------------------

# This routine will not be called if this is a dry run, so no need for
# such protection inside this function.
def create_team_drive(service, source_folder):
    logging.debug('=== Creating Team Drive: "{0}"'
	  .format(source_folder.name))
    metadata = {
	'name' : source_folder.name,
	}
    u = uuid.uuid4()
    tdrive = doit(service.teamdrives().create(body=metadata,
					      requestId=u))
    logging.info('=== Created Team Drive: "{0}" (ID: {1})'
	  .format(source_folder.name, tdrive['id']))

    file = GFile(id=tdrive['id'], mimeType=team_drive_mime_type,
		 webViewLink=None,
		 name=tdrive['name'], parents=['root'], team_file=None)
    return file

#-------------------------------------------------------------------

# Ensure there is no Team Drive of the same folder name
def verify_no_team_drive_name(service, args, source_folder):
    page_token = None
    while True:
	response = doit(service.teamdrives()
			.list(pageToken=page_token))
	for team_drive in response.get('teamDrives', []):
	    if team_drive['name'] == source_folder.name:
		# By default, abort if a Team Drive of the same name
		# already exists.  But if the user said it was ok,
		# keep going if it already exists.
		if args.debug_team_drive_already_exists_ok:
		    logging.info('Team Drive "{0}" already exists, but proceeding anyway...'
				 .format(source_folder.name))
		    file = GFile(id=team_drive['id'],
				 mimeType=team_drive_mime_type,
				 webViewLink=None,
				 name=team_drive['name'],
				 parents=['root'],
				 team_file=None)
		    return file
		else:
		    logging.error('Found existing Team Drive of same name as source folder: "{0}" (ID: {1})'
				  .format(source_folder.name, team_drive['id']))
		    logging.error("There cannot be an existing Team Drive with the same name as the source folder")
		    exit(1)

	page_token = response.get('nextPageToken', None)
	if page_token is None:
	    break

    # If we get here, we didn't find a team drive with the same name.
    # Yay!
    logging.info("=== Verified: no existing Team Drives with same name as source folder ({0})"
	     .format(source_folder.name))
    return

#-------------------------------------------------------------------

# Given a folder ID, verify that it is a valid folder.
# If valid, return a GFile instance of the folder.
def verify_folder_id(service, id):
    response = doit(service.files().get(fileId=id,
					fields='id,mimeType,name,webViewLink,parents',
					supportsTeamDrives=True))

    if response is not None and response['mimeType'] == folder_mime_type:
	logging.info("=== Valid folder ID: {0} ({1})"
		 .format(id, response['name']))

	folder = GFile(id=response['id'], mimeType=response['mimeType'],
		       webViewLink=response['webViewLink'],
		       name=response['name'], parents=response['parents'],
		       team_file=None)
	return folder

    else:
	logging.error("Error: Could not find any contents of folder ID: {0}"
		  .format(id))
	exit(1)

#-------------------------------------------------------------------

def main():
    tools.argparser.add_argument('--source-folder-id',
				 required=True,
				 help='Source folder ID')

    tools.argparser.add_argument('--app-id',
				 default=app_cred_file,
				 help='Filename containing Google application credentials')

    tools.argparser.add_argument('--dry-run',
				 action='store_true',
				 help='Go through the motions but make no actual changes')

    tools.argparser.add_argument('--copy-all',
				 action='store_true',
				 help='Instead of moving files that are capable of being moved to the new Team Drive, *copy* all files to the new Team Drive')

    tools.argparser.add_argument('--list-multiparents',
				 action='store_true',
				 help='Just find and list all files/folders in the source folder that have multiple parents (and do nothing else -- do not make a new Team Drive, etc.)')

    tools.argparser.add_argument('--ignore-multiparents',
				 action='store_true',
				 help='If any file or folder has multiple parents, ignore them and proceed with the conversion anyway (multi-parent files/folders will NOT be put in the new Team Drive)')

    tools.argparser.add_argument('--verbose',
				 action='store_true',
				 help='Be a bit verbose in what the script is doing')
    tools.argparser.add_argument('--debug',
				 action='store_true',
				 help='Be incredibly verbose in what the script is doing')
    tools.argparser.add_argument('--debug-team-drive-already-exists-ok',
				 action='store_true',
				 help='For debugging only: don\'t abort if the team drive already exists')

    args = tools.argparser.parse_args()

    # Setup logging
    setup_logging(args)

    # Authorize the app and provide user consent to Google
    app_cred = load_app_credentials(args.app_id)
    user_cred = load_user_credentials(scope, app_cred)
    service = authorize(user_cred)

    # Verify source folder ID.  Do this up front, before doing
    # expensive / slow things.
    source_folder = verify_folder_id(service, id=args.source_folder_id)

    # If this is not a dry run, do some checks before we read the
    # source tree.
    team_drive = None
    if not args.dry_run and not args.list_multiparents:
	# Ensure there is no Team Drive of the same folder name
	team_drive = verify_no_team_drive_name(service, args,
					       source_folder)

    # Read the source tree
    all_files = dict()
    (source_root, all_files) = read_source_tree(service, '',
						source_folder,
						all_files)

    # Print the list of files with multiple parents
    found = print_multiparents(service, source_root, all_files)
    if found:
	return 1
    if (args.dry_run or
	args.list_multiparents):
	return 0

    #------------------------------------------------------------------
    # If we get here, it means we're good to go to create the new Team
    # Drive and move/copy all the files to it.
    #------------------------------------------------------------------

    # Make a Team Drive of the same folder name
    if team_drive is None:
	team_drive = create_team_drive(service, source_folder)

    # Find owner (and their organization) of the Team Drive
    owner = find_team_drive_owner(service, team_drive)

    # Create a folder tree skeleton in the new Team Drive (i.e., just
    # folders -- no files yet).
    logging.debug("=== Creating folders in new Team Drive")
    migrate_to_team_drive(service, source_root, team_drive, all_files)

    logging.debug("=== END OF MAIN")

if __name__ == '__main__':
    exit(main())
