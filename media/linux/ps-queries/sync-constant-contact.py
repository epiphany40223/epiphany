#!/usr/bin/env python3

"""Script to iterate through Member Workgroups from ParishSoft
Family Suite and sync the information with a Constant Contact list

 - Use hard-coded lists of Member Workgroups and Constant Contact lists
 - Be sure that the name of the Member Workgroup matches the list exactly
 - For each:
 	- Find all PS Members that have a given Member WorkGroup
 	- Retrieve the relevant list from Constant Contact APIs
 	- Compare the list and workgroup:
 		- Find which PS members should be added to the list
 		- Find which members should be removed from the list
 		- Find which list members need their contact information changed

Make sure you install the PIP modules in requirements.txt:
	
	pip install -r requirements.txt
"""

import os
import re
import sys
import csv
import json
import time
import logging
import httplib2
import logging.handlers

# We assume that there is a "ecc-python-modules" sym link in this
# directory that points to the directory with ECC.py and friends.
moddir = os.path.join(os.getcwd(), 'ecc-python-modules')
if not os.path.exists(moddir):
    print("ERROR: Could not find the ecc-python-modules directory.")
    print("ERROR: Please make a ecc-python-modules sym link and run again.")
    exit(1)
sys.path.insert(0, moddir)

import ECC
import ParishSoftv2 as ParishSoft

from oauth2client import tools

from pprint import pprint
from pprint import pformat

# Globals

args = None
log = None

##
## Gets the synchronization pairs
##
## :returns:   Pairs of workgroups and contact lists
## :rtype:     List of Tuples
##

def get_synchronizations():
	ecc = '@epiphanycatholicchurch.org'

	synchronizations = [
		{
			'workgroups' : [''],
			'cclist'	 : f'',
			'notify'	 : f'',
		},
	]

	return synchronizations

##
## Compares the Member Workgroup to the Constant Contact list.
## Does not take any actions yet.
## 
## :returns:  The actions to take
## :rtype:	  List of Tuples
##

def compute_sync(sync, ps_members, list_members, log=None):
	actions = list()

	for pm in ps_members:
		found_in_cc_list = False
		for lm in list_members:
			if (pm['email'] == lm['email']):
				# CASE: Member exits in Workgroup and in C.C.
				# We're happy with these cases.
				found_in_cc_list = True
				lm['sync_found'] = True

			if not found_in_cc_list:
				# CASE: Member exists in Workgroup but not in
				# Constant Contact. Must be added to C.C.
				actions.append({
						'action'	: 'add',
						'email'		: pm['email'],
				})

	for lm in list_members:
		if 'sync_found' in lm and lm['sync_found']:
			continue

		actions.append({
			'action'	: 'delete',
			'email'		: lm['email'],
		})

	if len(actions) > 0:
		log.info(f'Actions for {sync['cclist']}')
		log.info(pformat(actions, depth=3))

	return actions

##
## Synchronizes the list based on the computed actions
##
## :param      args:     The arguments
## :param      sync:     The synchronized tuples
## :param      service:  The service
## :param      actions:  The actions
## :param      log:      The log
##

def do_sync(args, sync, service, actions, log=None):

	log.info(f"Synchronizing workgroups: {sync['workgroups']}, list: {sync['cclist']}")

	# Process each action
	changes = list()
	for action in actions:
		msg = None

		if action['action'] == 'add'
			msg = _sync_add(args, sync, service=service, action=action, email=action['email'], log=log)

		elif action['action'] == 'delete':
			msg = _sync_delete(args, sync, service=service, action=action, email=action['email'], log=log)

		else:
			log.error(f'Unknown action: {action['action']} -- PS Member {action['email']} (skipped)')

		if msg and not args.dry_run:
			email = action['email']
			i 	  = len(changes) + 1
			changes.append(f"<tr>\n<td>{i}.</td>\n<td>{mem_names}</td>\n<td>{action['email']}</td>\n<td>{msg}</td>\n</tr>")

	if len(changes) > 0 and not args.dry_run:
		rationale = list()

		subject = 'Update to Constant Contact List for '
		for k in sync['workgroups']:
			subject = subject + ', ' + k
			rationale.append(f'<li> Members with the "{k}" keyword</li>')


        style = r'''table { border-collapse: collapse; }
th, td {
    text-align: left;
    padding: 8px;
    border-bottom: 1px solid #ddd;
}
tr:nth-child(even) { background-color: #f2f2f2; }'''

        changes = '\n'.join(changes)
        rationale = '\n'.join(rationale)
        body = f"""<html>
<head>
<style>
{style}
</style>
</head>
<body>
<p>The following changes were made to the Constant Contact list {sync['cclist']}:</p>

<p><table border=0>
<tr>
<th>&nbsp;</th>
<th>Name</th>
<th>Email address</th>
<th>Action</th>
</tr>
{changes}
</table></p>

<p>These email addresses were obtained from PS:</p>

<p><ol>
{rationale}
</ol></p>
</body>
</html>
"""

		# Send the email
		ECC.send_email(to_addr=sync['notify'], subject=subject, body=body,
			content_type='text/html', log=log)



@retry.Retry(predicate=Google.retry_errors)
def _sync_add(args, sync, service, action, name, log=None):
	email = action['email']
	if log:
		log.info(f'Adding PS Member {name} ({email}) to Constant Contact list')

	try:
		if not args.dry_run:
			service.members().insert

####################################################################
#
# Setup functions
#
####################################################################

def setup_cli_args():
    tools.argparser.add_argument('--smtp-auth-file',
                                 required=True,
                                 help='File containing SMTP AUTH username:password')
    tools.argparser.add_argument('--slack-token-filename',
                                 help='File containing the Slack bot authorization token')

    tools.argparser.add_argument('--ps-api-keyfile',
                                 required=True,
                                 help='File containing the ParishSoft API key')
    tools.argparser.add_argument('--ps-cache-dir',
                                 default='.',
                                 help='Directory to cache the ParishSoft data')

    global gapp_id
    tools.argparser.add_argument('--app-id',
                                 default=gapp_id,
                                 help='Filename containing Google application credentials')
    global guser_cred_file
    tools.argparser.add_argument('--user-credentials',
                                 default=guser_cred_file,
                                 help='Filename containing Google user credentials')

    tools.argparser.add_argument('--dry-run',
                                 action='store_true',
                                 help='Do not actually update the Google Group; just show what would have been done')

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

    # --dry-run implies --verbose
    if args.dry_run:
        args.verbose = True

    # --debug also implies --verbose
    if args.debug:
        args.verbose = True

    # Read the PS API key
    if not os.path.exists(args.ps_api_keyfile):
        print(f"ERROR: ParishSoft API keyfile does not exist: {args.ps_api_keyfile}")
        exit(1)
    with open(args.ps_api_keyfile) as fp:
        args.api_key = fp.read().strip()

    return args

#
#
#
#
#

def main():
	args = setup_cli_args()

	log = ECC.setup_logging(info=args.verbose,
							debug=args.debug,
							logfile=args.logfile, rotate = True,
							slack_token_filename=args.slack_token_filename)
	ECC.setup_email(args.smtp_auth_file, smtp_debug=args.debug, log=log)

	log.info("Loading ParishSoft info...")
	families, members, family_workgroups, member_workgroups, ministries = \
		ParishSoft.load_families_and_members(api_key=args.api_key,
											 active_only=True,
											 parishoners_only=False,
											 cache_dir=args.ps_cache_dir,
											 log=log)

	apis = {
	}
	services = ''

	synchronizations = get_synchronizations()
	for sync in synchronizations:
		matching_members = find_matching_members(members,
												 sync, log=log)
		

if __name__ == '__main__':
	main()