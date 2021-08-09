#!/usr/bin/env python3

"""This script is an adaptation/improvement of an older script that
copied a whole directory of files from one Google Drive shared folder
to a Google Drive Team Drive (now called Google Shared Drives).  It
was written when I was not very experience in Python, and it shows.
:-(

This script is a huge improvement over the original code, but I was still
working on a deadline, so this script still has shortcomings, built-in
assumptions, etc.  It could likely be optimized to run faster, especially when
copying large folders.  It is not perfect, and not suitable for general use.

-----------------------------------------------------------------------

This script attempts move files from their old location to the new
location.  If the file can't be moved, it is copied.

This script is useful because Google does not allow moving a folder
(and its entire contents) from My Drive to a Google Shared Drive.
This script can do as best a job as it can to move a folder hierarchy
from a My Drive location to a Google Shared Drive.

Specifically:

1. The script discovers and traverses the entire folder/file hierarchy
   of the source tree

2. The script discovers and traverses the entire folder/file hierarchy
   of the destination tree

3. The script then compares the Python data structures representing
   the two trees before doing anything.

    * This is a major improvement over the old script.  The reason for
      this comparison is because sometimes the overall operation would
      get interrupted (e.g., an error killed the script, a human
      killed the script, the script was running overnight and the
      laptop went to sleep and therefore ended up killing the script,
      ... etc.).  This was a disaster for the old script for a variety
      of reasons.

    * This script attempts to be much more friendly to getting interrupted:

        * It doesn't abort if a Google API fails.

        * It doesn't create all destination folders at once (they're
          created as they are needed).

        * Since files are copied to the destination if they can't be
          moved, check to make sure that the same file doesn't exist
          at the destination before moving/copying it.

        * Only create a folder at the destination if a folder with the
          same name does not already exist.

     * Specifically, the analysis marks each entry as:
         1. File: need to migrate
         2. File: already been migrated
         3. Folder: need to create at destination
         4. Folder: already been created at destination

4. After this analysis, it's a relatively straightforward process to
   go through and look at the marking and do the action that is
   required.

   NOTE: The file will end up being ***copied*** (vs. moved) to the
   target location if:

   a) the owner of the file is not part of the organization that owns
      the target Google Shared Drive
   b) the owner of the file is part of the organization that owns the
      target Google Shared Drive, but does not have write permissions
      on the target Google Shared Drive (!!!)

This script developed and tested with Python 3.6.x.  It has not been
tested with other versions (e.g., Python 2.7.x).

Pre-requisites:

- A client_id.json file downloaded from the Google Dashboard
  (presumably of the owning organization of the destination shared
  Drive: https://console.developers.google.com/apis/credentials)

- A Google Account who is both authorized to read everything in the
  source folder tree and authorized to write into the destination shared
  Drive folder.

- pip install -r requirements.txt

"""

import os
import sys
import time
import copy

# We assume that there is a "ecc-python-modules" sym link in this
# directory that points to the directory with ECC.py and friends.
moddir = os.path.join(os.getcwd(), 'ecc-python-modules')
if not os.path.exists(moddir):
    print("ERROR: Could not find the ecc-python-modules directory.")
    print("ERROR: Please make a ecc-python-modules sym link and run again.")
    exit(1)

sys.path.insert(0, moddir)

import ECC
import Google
import GoogleAuth
import googleapiclient

from oauth2client import tools
from apiclient.errors import HttpError

from pprint import pprint

# Globals
app_cred_file = 'client_id.json'
user_cred_file = 'user-credentials.json'

#-------------------------------------------------------------------

class GFile:
    MIGRATION_UNEVALUATED = 0

    MIGRATION_FILE_NEED_TO_MIGRATE = 1
    MIGRATION_FILE_ALREADY_MIGRATED = 2

    MIGRATION_FOLDER_NEED_TO_CREATE = 3
    MIGRATION_FOLDER_ALREADY_CREATED = 4

    @staticmethod
    def state_name(val):
        if val == GFile.MIGRATION_UNEVALUATED:
            return "MIGRATION_UNEVALUATED"
        elif val == GFile.MIGRATION_FILE_NEED_TO_MIGRATE:
            return "MIGRATION_FILE_NEED_TO_MIGRATE"
        elif val == GFile.MIGRATION_FILE_ALREADY_MIGRATED:
            return "MIGRATION_FILE_ALREADY_MIGRATED"
        elif val == GFile.MIGRATION_FOLDER_NEED_TO_CREATE:
            return "MIGRATION_FOLDER_NEED_TO_CREATE"
        elif val == GFile.MIGRATION_FOLDER_ALREADY_CREATED:
            return "MIGRATION_FOLDER_ALREADY_CREATED"
        else:
            return f"Unknown MIGRATION value ({val})"

    def __init__(self, id, mimeType, name, kind, webViewLink, parent_ids, parent_gfile):
        self.id = id                       # string
        self.name = name                   # string
        self.mimeType = mimeType           # string
        self.kind = kind                   # string
        self.webViewLink = webViewLink     # string (URL)
        self.parent_ids = parent_ids       # list of all parent ID strings (from Google)
        self.parent_gfile = parent_gfile   # GFile (just this object's single parent GFile)

        #------------------------------------------------------------------
        # This information will be set after __init__.

        # Location of this file after it has been migrated or copied
        self.migration_state = GFile.MIGRATION_UNEVALUATED
        self.migrated_gfile  = None

        # If we're a folder, we'll contain GFiles for our sub-entries, too,
        # indexed both by name (remember: multiple files can have the same name)
        # and by ID (because of shift-Z, multiple files can have the same ID,
        # too).
        self.is_folder       = False
        self.folder_contents_by_name = dict()
        self.folder_contents_by_id   = dict()

        # Used for traversal bookkeeping
        self.traverse        = False

        # Used for tracking status
        self._mkdir_done     = False

    def relative_name(self):
        if self.parent_gfile:
            # If I have a parent, get their names and then add mine.
            parts = self.parent_gfile.relative_name()
            parts.append(self.name)
        else:
            # If I have no parent, then I'm the root.
            # Just return an empty list with no names.
            parts = list()

        return parts

    # Google filenames cannot include \n.
    #
    # We can therefore hash all the dirnames and basename of a Google relative
    # filename into a unique string separated by \n's.  This *sounds* like a hack,
    # but it's conceptually no different than separating dirnames by '/'.
    def hashed_relative_name(self):
        return '\n'.join(self.relative_name())

    # Make this relative path at a destination folder if it does not already
    # exist.  If it does exist, get a GFile pointing to it.
    def mkdir(self, dest_folder):
        # Did we do this already?  Or are we a root?
        # If so, there's nothing to do.
        if self._mkdir_done or self.parent_gfile is None:
            return

        # Guarantee that my parent's directory exists at the destination
        self.parent_gfile.mkdir(dest_folder)

        # See if my folder exists at the destination
        parent_id_at_dest = self.parent_gfile.migrated_file.id

        #.......JMS continue here
















        # Done!
        self._mkdir_done = True

#-------------------------------------------------------------------

# Try recoverable failures a few times before giving up.
#
# Never abort, though -- it's a real pain to re-run this script a 2nd
# time if it aborts in the middle of a migration.
def doit(httpref, can_fail=False):
    max_tries = 3
    for count in range(max_tries):
        try:
            ret = httpref.execute()
            return ret

        except HttpError as err:
            log.error("*** Got HttpError:")
            log.error(err)
            if err.resp.status in [500, 503]:
                log.error("*** Seems recoverable; let's sleep and try again...")
                time.sleep(3)
                continue
            elif err.resp.status == 403 and can_fail:
                log.error("*** Got a 403, but we're allowed to fail this call")
                # Need to return None to indicate failure
                return None
            else:
                log.error("*** Doesn't seem recoverable (status {0}) -- aborting".format(err.resp.status))
                log.error(err)
                # Need to return None to indicate failure
                return None

        except:
            log.error("*** Some unknown error occurred")
            log.error(sys.exc_info()[0])
            # Need to return None to indicate failure
            return None

    # If we get here, it's failed multiple times -- time to bail...
    log.error(f"Error: we failed this {max_tries} times; there's no reason to believe it'll work if we do it again...")
    # Need to return None to indicate failure
    return None

#-------------------------------------------------------------------

def create_folder(service, parent_folder, new_folder_name):
    log.debug(f"Creating new folder '{new_folder_name}', parent '{parent_folder.name}' (ID: {parent_folder.id})")
    metadata = {
        'name' : new_folder_name,
        'mimeType' : Google.mime_types['folder'],
        'parents' : [ parent_folder.id ]
    }

    folder = doit(service.files().create(body=metadata,
                                         supportsTeamDrives=True,
                                         fields='id,kind,webViewLink'))
    log.debug(f'Created folder: "{new_folder_name}" (ID: {folder["id"]})')

    gfile = GFile(id=folder['id'],
                 mimeType=Google.mime_types['folder'],
                 name=new_folder_name,
                 kind=folder['kind'],
                 parent_ids=[ parent_folder.id ],
                 parent_gfile=parent_folder,
                 webViewLink=folder['webViewLink'])

    return gfile

#-------------------------------------------------------------------

def migrate(service, source_root, dest_root):

    def _move_file(service, source_file, dest_folder):
        migrated_file = doit(service
                            .files()
                            .update(fileId=source_file.id,
                                    addParents=dest_folder.id,
                                    removeParents=source_file.parent_gfile.id,
                                    supportsAllDrives=True,
                                    fields='id'),
                            can_fail=True)
        if migrated_file is not None:
            log.info("--> Moved!")
            return True
        else:
            return False

    #---------------------------------------------------------------

    def _copy_file(service, source_file, dest_folder):
        copied_file = doit(service
                           .files()
                           .copy(fileId=source_file.id,
                                 body={ 'parents' : [ dest_folder.id ],
                                        'name' : source_file.name },
                                 supportsAllDrives=True,
                                 fields='id'))
        if copied_file is None:
            log.error("ERROR: Failed to copy file!")
        else:
            log.info("--> Copied")

    #---------------------------------------------------------------

    def _migrate(service, source_folder, source_root, dest_root):
        log.info(f"Migrating folder contents: {source_folder.relative_name()}")
        # We could easily have a single loop here and handle all files and
        # folders at the same time.  However, given that we usually use this
        # script with a really, really long list of files, it makes the logging
        # output *significantly* easier to read if we handle all the files in a
        # folder and then handle all the sub-folders.

        # First, migrate all the relevant files in this folder
        for entry in source_folder.folder_contents_by_id.values():
            if entry.is_folder:
                # Skip folders for the moment
                continue

            elif entry.migration_state == GFile.MIGRATION_FILE_ALREADY_MIGRATED:
                log.info(f"Already migrated: {entry.relative_name()} file")
            elif entry.migration_state == GFile.MIGRATION_FILE_NEED_TO_MIGRATE:
                log.info(f"NEED TO MIGRATE:  {entry.relative_name()} file")

                dest_folder = source_folder.migrated_gfile
                if dest_folder is None:
                    log.error("How is the dest folder None????")
                    exit(1)

                # Try to move the file to the shared drive
                moved = _move_file(service, entry, dest_folder)

                # If we failed to move it, then copy it
                if not moved:
                    _copy_file(service, entry, dest_folder)

            else:
                log.error(f"Unknown file entry state: {GFile.state_name(entry.migration_state)}")
                log.error("Cannot continue")
                exit(1)

        # Now create sub-folders and recurse into them
        for entry in source_folder.folder_contents_by_id.values():
            if not entry.is_folder:
                # Files were handled in the above loop
                continue

            elif not entry.traverse:
                # We're not supposed to traverse this branch
                continue

            elif entry.migration_state == GFile.MIGRATION_FOLDER_ALREADY_CREATED:
                log.info(f"Already created:  {entry.relative_name()} folder")
            elif entry.migration_state == GFile.MIGRATION_FOLDER_NEED_TO_CREATE:
                log.info(f"NEED TO CREATE:   {entry.relative_name()} folder")

                # We're traversing down the source tree.  This means that any
                # relevant corresponding parent folders for this folder will
                # have already been created in the dest tree.  Meaning: we only
                # need to do a "mkdir", not a "mkdir -p".
                dest_parent_folder = source_folder.migrated_gfile
                if dest_parent_folder is None:
                    # If we're at the root, then the dest_parent_folder is the root
                    dest_parent_folder = dest_root
                dest_folder = create_folder(service, dest_parent_folder, entry.name)
                entry.migrated_gfile = dest_folder

            else:
                log.error(f"Unknown file entry state: {GFile.state_name(entry.migration_state)}")
                log.error("Cannot continue")
                exit(1)

            # Recurse into this folder
            _migrate(service, entry, source_root, dest_root)

    #---------------------------------------------------------------

    # Start the recursion
    log.debug(f'Migrating folder tree: "{source_root.name}" (ID: {source_root.id}) to destination folder "{dest_root.name}" ID {dest_root.id}')
    _migrate(service, source_root, source_root, dest_root)

#-------------------------------------------------------------------

def print_multiparents(service, root, all_files):
    def _traverse(service, folder, all_files, seen):
        found_multiparents = False

        # Iterate through all the names in this folder and record if any
        # have multiparents.
        for id, entry in folder.folder_contents_by_id.items():
            # Look for files with multiparents that we have not yet already displayed
            if len(entry.parent_ids) > 1 and not id in seen:
                seen[id] = True
                found_multiparents = True

                type = "Folder" if entry.is_folder else "File"
                log.warning(f'- {type} "{entry.name}"')
                log.warning(f'  ID: {entry.id}')
                log.warning(f'  URL: {entry.webViewLink}')
                log.warning( '  Appears in:')
                # Print all the places this entry appears
                for parent_id in all_files[id].parent_ids:
                    if parent_id in all_files:
                        parent = all_files[parent_id]
                        log.warning(f'    Folder: "{parent.relative_name()}"')
                        log.warning(f'    ID: {parent.id}')
                        log.warning(f'    URL: {parent.webViewLink}')
                    else:
                        log.warning( '    Folder: "...parent not in the source tree..."')
                        log.warning(f'    ID: {parent_id}')
                        log.warning(f'    URL: https://drive.google.com/drive/folders/{parent_id} (probably)')

                log.warning('')

        # Traverse into the sub folders of this folder. Ensure to obey
        # entry.traverse so that we don't traverse into the same folder more than
        # once (i.e., a folder with multiple parents in this source tree).
        for entry in folder.folder_contents_by_id.values():
            if entry.is_folder and entry.traverse:
                sub_ret = _traverse(service, entry, all_files, seen)
                if sub_ret:
                    found_multiparents = True

        # Return whether we (or any recursive traversals) found any
        # multi-parent files.
        return found_multiparents

    #---------------------------------------------------------------

    log.info('')
    log.info('Files/folders with multiple parents (will not be copied over to the shared Drive):')
    log.info('')

    seen = dict()
    found = _traverse(service, root, all_files, seen)

    if not found:
        log.info("--> None found -- yay!")

    return found

#-------------------------------------------------------------------

# Traverse all the files/folders in the source folder and see if there is a
# corresponding entity in the dest folder.
def link_src_dest(source_root, dest_root):

    # Look up a set of folder names at a root
    def _lookup_folder(root, folder):
        names = folder.relative_name()

        folder = root
        for part in names:
            if part not in folder.folder_contents_by_name.keys():
                # Did not find the corresponding name
                return None
            # That part name is here.  Is it a folder?
            found = False
            for entry in folder.folder_contents_by_name[part]:
                if entry.is_folder:
                    folder = entry
                    found = True
                    break
            if found:
                # Yes, we found it!  "folder" has been reset, so continue on to
                # check the next part.
                continue

            # If we got here, we didn't find a folder with that name
            return None

        # If we got here, we found it!
        return folder

    #---------------------------------------------------------------

    def _gfile_match_heuristic(source_entry, dest_entry):
        if (source_entry.name == dest_entry.name and
            source_entry.kind == dest_entry.kind and
            source_entry.mimeType == dest_entry.mimeType):
            return True

        return False

    #---------------------------------------------------------------

    # Convenience: list this logic once rather than several times below
    def _mark_to_migrate(entry):
        if entry.is_folder:
            entry.migration_state = GFile.MIGRATION_FOLDER_NEED_TO_CREATE
        else:
            entry.migration_state = GFile.MIGRATION_FILE_NEED_TO_MIGRATE

    def _mark_good(entry):
        if entry.is_folder:
            entry.migration_state = GFile.MIGRATION_FOLDER_ALREADY_CREATED
        else:
            entry.migration_state = GFile.MIGRATION_FILE_ALREADY_MIGRATED

    #---------------------------------------------------------------

    def _link(source_folder, source_root, dest_root):
        log.debug(f"Analyzing source folder: {source_folder.relative_name()} (ID: {source_folder.id})")

        # Look up the corresponding desintation folder
        dest_folder = _lookup_folder(dest_root, source_folder)
        if dest_folder is None:
            log.debug(f"--> There is no corresponding destination folder")
            # We didn't find a corresponding folder at the dest.  So mark all
            # the entries in this folder as "MIGRATE_NEED_TO_*"
            for source_entry in source_folder.folder_contents_by_id.values():
                _mark_to_migrate(source_entry)

        else:
            log.debug(f"--> Corresponding destination folder (ID: {dest_folder.id})")
            # We found a corresponding folder at the dest.  Traverse this folder
            # looking for name matches in the corresponding dest folder.
            for name, source_entries in source_folder.folder_contents_by_name.items():
                log.debug(f"Analyzing source file name: {name}")
                # This is a bit of a quandry, because Google allows us to have
                # multiple files with the same name.  They will have a unique ID,
                # and may have the same or different kind and mimeType values.
                # Other than that, we can't really know if their file contents are
                # different or not.

                if name not in dest_folder.folder_contents_by_name:
                    # It's easy if there's no corresponding name at the destination:
                    # we need to migrate all the sources to the destination.
                    for source_entry in source_entries:
                        _mark_to_migrate(source_entry)
                    continue

                # If the name exists at the dest, then check all the files at the
                # source with this name vs. all the files at the dest with this
                # name, and see if we can find a match.
                dest_entries = copy.deepcopy(dest_folder.folder_contents_by_name[name])
                for source_entry in source_entries:
                    for i, dest_entry in enumerate(dest_entries):
                        if _gfile_match_heuristic(source_entry, dest_entry):
                            # Matched!  For simplicity, remove the matched file from
                            # the dest_entries so that we don't match it again with
                            # another source file.
                            _mark_good(source_entry)
                            source_entry.migrated_gfile = dest_entry
                            dest_entries.pop(i)
                            break

                    # If we didn't find a match, mark the source file accordingly.
                    if source_entry.migration_state == GFile.MIGRATION_UNEVALUATED:
                        _mark_to_migrate(source_entry)

        # Now that we've examined all the files in this folder, traverse into
        # all the sub folders and check them, too.  Note: we could do some
        # optimizations here: e.g., if we find a folder with
        # NEED_TO_CREATE_FOLDER, then obviously everything in there can just be
        # marked as NEED_TO_* without checking anything further.  That adds some
        # additional complexity here in the code -- let's skip that optimization
        # for the moment and see if the run-time performance would make such an
        # optimization worth it.
        for source_entry in source_folder.folder_contents_by_id.values():
            if source_entry.is_folder:
                _link(source_entry, source_root, dest_root)

    #---------------------------------------------------------------

    # Initiate the recursion on the source root
    _link(source_root, source_root, dest_root)

#-------------------------------------------------------------------

def create_index_by_id(folder, ids):
    for id, entry in folder.folder_contents_by_id.items():
        ids[id] = entry

        if entry.is_folder and entry.traverse:
            create_index_by_id(entry, ids)

#-------------------------------------------------------------------

def google_read_folder_tree(service, source_folder):
    log.info(f'Discovering contents of folder: {source_folder.relative_name()} (ID: {source_folder.id})')

    num_folders = 0
    num_files = 0

    # Iterate through everything in this root folder
    all_file_ids = dict()
    page_token = None
    query = f"'{source_folder.id}' in parents and trashed=false"
    log.debug(f"Query: {query}")
    while True:
        response = doit(service.files()
                        .list(q=query,
                              corpora='allDrives',
                              includeItemsFromAllDrives=True,
                              fields='nextPageToken,files(name,id,kind,mimeType,parents,webViewLink)',
                              pageToken=page_token,
                              supportsAllDrives=True))

        # Iterate through each of the files found
        sentinel = '000 DO NOT MIGRATE'
        for file in response.get('files', []):
            log.info(f'Found: "{file["name"]}" (ID: {file["id"]})')

            # SPECIAL EXCEPTION:
            # Skip any folder named "000 DO NOT MIGRATE"
            if file['name'] == sentinel:
                log.warning(f"Found file with sentinel name ('{sentinel}') -- skipping!")
                continue

            # Save this content entry in the list of contents for this
            # folder
            gfile = GFile(id=file['id'],
                          mimeType=file['mimeType'],
                          name=file['name'],
                          kind=file['kind'],
                          webViewLink=file['webViewLink'],
                          parent_ids=file['parents'],
                          parent_gfile=source_folder)

            # gfile.is_folder and gfile.traverse both default to False
            if file['mimeType'] == Google.mime_types['folder']:
                gfile.is_folder = True
                num_folders += 1
            else:
                num_files += 1

            # We have already seen this file before
            if file['id'] in all_file_ids:
                log.debug('--- We already know this file; cross-referencing...')

                # If this is a folder that we already know, then do
                # not traverse down into it (again).
                if gfile.is_folder:
                    log.debug('--- Is a folder, but we already know it; NOT adding to pending traversal list')

            # We have *NOT* already seen this file before
            else:
                log.debug('--- We do not already know this file; saving...')
                all_file_ids[file['id']] = gfile
                # Admittedly, this is a hack.  But it works. :-)
                # Google filenames cannot contain newlines, so an easy way to
                # hash a list of Google filenames is to join them by \n.
                all_file_ids['\n'.join(gfile.relative_name())] = gfile

                # If it's a folder, add it to the pending traversal list
                if gfile.is_folder:
                    gfile.traverse = True
                    log.debug("--- Is a folder; adding to pending traversal list")

            # Add this gfile to the parent folder's dict of lists of GFiles
            # (because multiple files in the same folder can have the same name)
            if gfile.name not in source_folder.folder_contents_by_name:
                source_folder.folder_contents_by_name[gfile.name] = list()
            source_folder.folder_contents_by_name[gfile.name].append(gfile)

            # The folder_contents_by_id entries are GFiles (not lists of
            # GFiles), because there can never be two files with the same ID in
            # the same folder.  But check for this error condition, anyway.
            if gfile.id in source_folder.folder_contents_by_id:
                log.error("Somehow there's two files with the same ID in this source folder!")
                log.error(f"Folder: {source_folder.relative_name()} (ID: {source_folder.id})")
                f1 = source_folder.folder_contents_by_id[gfile.id]
                log.error(f"File 1: {f1.relative_name()} (ID: {f1.id})")
                log.error(f"File 2: {gfile.relative_name()} (ID: {gfile.id})")
                log.error("Cannot continue")
                exit(1)

            source_folder.folder_contents_by_id[gfile.id] = gfile

        page_token = response.get('nextPageToken', None)
        if page_token is None:
            break

    # Traverse all the sub folders
    for name, entries in source_folder.folder_contents_by_name.items():
        for entry in entries:
            if entry.traverse:
                log.debug(f"Traversing down into {entry.relative_name()}")
                nfolders, nfiles = google_read_folder_tree(service, entry)

                num_folders += nfolders
                num_files += nfiles

    return num_folders, num_files

#-------------------------------------------------------------------

# Given a folder ID, verify that it is a valid folder.
# If valid, return a GFile instance of the folder.
def google_lookup_folder_by_id(service, id, parent_gfile):
    log.info(f"Verifying folder ID: {id}....")
    folder = doit(service.files().get(fileId=id,
                                      fields='id,kind,mimeType,name,webViewLink,parents',
                                      supportsAllDrives=True))

    if folder is None:
        log.error(f"Could not find file ID {id}")
        exit(1)
    elif folder['mimeType'] != Google.mime_types['folder']:
        log.error(f"File ID {id} is not a folder")
        exit(1)

    log.info(f"Valid folder ID: {id} ({folder['name']})")
    log.debug(f"Folder: {folder}")
    if not 'parents' in folder:
        folder['parents'] = []

    gfile = GFile(id=folder['id'], mimeType=folder['mimeType'],
                  webViewLink=folder['webViewLink'],
                  name=folder['name'],
                  kind=folder['kind'],
                  parent_ids=folder['parents'],
                  parent_gfile=parent_gfile)

    return gfile

#-------------------------------------------------------------------

def add_cli_args():
    tools.argparser.add_argument('--source-folder-id',
                                 required=True,
                                 help='Source folder ID')
    tools.argparser.add_argument('--dest-folder-id',
                                 help='Destinaton Shared Drive folder ID')

    tools.argparser.add_argument('--app-id',
                                 default=app_cred_file,
                                 help='Filename containing Google application credentials')
    tools.argparser.add_argument('--user-credentials',
                                 default=user_cred_file,
                                 help='Filename containing Google user credentials')

    tools.argparser.add_argument('--dry-run',
                                 action='store_true',
                                 help='Go through the motions but make no actual changes')

    tools.argparser.add_argument('--copy-all',
                                 action='store_true',
                                 help='Instead of moving files that are capable of being moved to the new shared Drive, *copy* all files to the new shared Drive')

    tools.argparser.add_argument('--list-multiparents',
                                 action='store_true',
                                 help='Just find and list all files/folders in the source folder that have multiple parents (and do nothing else -- do not copy or move files, etc.)')

    tools.argparser.add_argument('--ignore-multiparents',
                                 action='store_true',
                                 help='If any file or folder has multiple parents, ignore them and proceed with the conversion anyway (multi-parent files/folders will NOT be put in the destination)')

    tools.argparser.add_argument('--logfile',
                                 required=False,
                                 help='Store verbose/debug logging to the specified file')

    args = tools.argparser.parse_args()

    return args

#-------------------------------------------------------------------

def main():
    global args
    args = add_cli_args()

    # Setup logging
    #
    # For some reason that I don't have the time to figure out
    # tonight, when we added --debug and --verbose as CLI args,
    # args.debug and args.verbose are always False, even when supplied
    # on the command line.  The heck with it: I'm just hard-coding the
    # values tonight.
    global log
    log = ECC.setup_logging(info=True, debug=True,
                            logfile=args.logfile, log_millisecond=False)

    apis = {
        'drive' : { 'scope'       : Google.scopes['drive'],
                    'api_name'    : 'drive',
                    'api_version' : 'v3', },
    }
    services = GoogleAuth.service_oauth_login(apis,
                                              app_json=args.app_id,
                                              user_json=args.user_credentials,
                                              log=log)
    service = services['drive']

    # Lookup the source and destination folders
    source_folder = google_lookup_folder_by_id(service, id=args.source_folder_id,
                        parent_gfile=None)
    dest_folder = google_lookup_folder_by_id(service, id=args.dest_folder_id,
                        parent_gfile=None)

    # Manually make the desintation root be the migrated destination of the
    # source root
    source_folder.migrated_state = GFile.MIGRATION_FOLDER_ALREADY_CREATED
    source_folder.migrated_gfile = dest_folder

    # Read the folder trees
    log.info("=== Reading source folder tree")
    source_num_folders, source_num_files = google_read_folder_tree(service, source_folder)
    source_files_by_id = dict()
    create_index_by_id(source_folder, source_files_by_id)
    log.info(f"=== Found a total of {source_num_folders} folders and {source_num_files} files")

    # Print the list of files with multiple parents
    found = print_multiparents(service, source_folder, source_files_by_id)
    if args.dry_run:
        log.info("Exiting (because --dry-run)")
        return 0
    elif args.list_multiparents:
        log.info("Exiting (because --list-multiparents)")
        return 0
    if found:
        if args.ignore_multiparents:
            log.warning("Because of --ignore-multiparents, these files will be COPIED")
        else:
            log.error("Found at least one file/folder with multiple parents.")
            log.error("These files/folders must be converted to having a single parent before converting over to a shared Drive.")
            return 1

    log.info("=== Reading dest folder tree")
    dest_num_folders, dest_num_files = google_read_folder_tree(service, dest_folder)
    dest_files_by_id = dict()
    create_index_by_id(dest_folder, dest_files_by_id)
    log.info(f"=== Found a total of {dest_num_folders} folders and {dest_num_files} files")

    # Link the GFiles in the source_folder to their corresponding entries (if
    # any) in the dest_folder.
    log.info("=== Analyzing source and destination trees...")
    link_src_dest(source_folder, dest_folder)

    # Emit a listing of all files/folders and their migration status
    def _debug_display_analysis(folder):
        for id, entry in folder.folder_contents_by_id.items():
            log.debug(f"Entry: {entry.relative_name()}, state={GFile.state_name(entry.migration_state)}")
        for entry in folder.folder_contents_by_id.values():
            if entry.is_folder and entry.traverse:
                _debug_display_analysis(entry)

    log.debug("=== Results of analysis:")
    _debug_display_analysis(source_folder)

    # Actually do the migration
    log.info("=== Migrating files...")
    migrate(service, source_folder, dest_folder)

if __name__ == '__main__':
    exit(main())
