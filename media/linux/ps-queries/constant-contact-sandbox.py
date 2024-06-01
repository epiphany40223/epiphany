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
moddir = '../../../python'
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

cc_client_id_filename = 'constant-contact-client-id.json'
cc_access_token_filename = 'constant-contact-access-token.json'

####################################################################
#
# Cross-reference CC contacts to ParishSoft members
#
####################################################################

def find_ps_member(contact, ps_members, log):
    email_address = contact['email_address']['address']

    def _value(contact, field_name):
        if field_name in contact:
            return contact[field_name]
        return ''

    first_name = _value(contact, 'first_name')
    last_name = _value(contact, 'last_name')

    log.info(f"== Looking for ParishSoft member for {first_name} {last_name} <{email_address}>")

    #-------------------------------------------

    def _search_member_emails(member, key, email_address):
            if key in member:
                for entry in member[key]:
                    if entry['EMailAddress'] == email_address:
                        return True
            return False

    # Do simple heuristics for now
    matches = list()

    # First, look for the email address
    key1 = 'preferred_emails'
    key2 = 'non_preferred_emails'
    for member in ps_members.values():
        found = False
        if key1 in member:
            if _search_member_emails(member, key1, email_address):
                found = True
            elif _search_member_emails(member, key2, email_address):
                found = True

        if found:
            matches.append(member)

    # Did we find only a single match?
    if len(matches) == 1:
        log.info("FOUND!")
        return matches[0]

    #-------------------------------------------

    # Doh. We found multiple.
    elif len(matches) > 1:
        log.warning(f"Found multiple ParishSoft Members with email address {email_address}")

    # Doh.  We didn't find any.
    else:
        log.warning(f"Found no ParishSoft Members with email address {email_address}")
        matches = [ member for member in ps_members.values() ]

    # Try searching for names in the remaining members
    log.warning(f"Searching remaining {len(matches)} ParishSoft Members...")
    new_matches = list()
    for member in matches:
        if member['last'] != last_name:
            continue
        if member['first'] != first_name and member['nickname'] != first_name:
            continue

        new_matches.append(member)

    # Did we find a single match?
    if len(new_matches) == 1:
        log.info("FOUND!")
        return new_matches[0]

    # Doh.  We found multiple.
    elif len(new_matches) > 1:
        log.warning(f"Found multiple ParishSoft Members with same first and last name")
        log.warning(pformat(new_matches))

    else:
        log.warning(f"Found no ParishSoft Members with same first and last name")

    return None

def link_cc_contacts_to_ps_members(cc_contacts,
                                    ps_members,
                                    log):
    result_key = 'PS MATCH RESULT'

    for contact in cc_contacts:
        key = 'memberDUID'
        contact[result_key] = {
            'msg' : 'no action',
            'action' : None,
        }

        if key in contact:
            # The contact has a ParishSoft DUID
            duid = int(contact[key])
            if duid in ps_members:
                # The contact's ParishSoft DUID represents current ParishSoft Member.
                # Huzzah!  Link the ParishSoft member to the contact.
                member = ps_members[duid]
                contact['ps_member'] = member
                if 'family' in member:
                    contact['familyDUID'] = member['familyDUID']
                contact[result_key]['msg'] = 'has a duid that matched to an active ParishSoft Member'
                continue

            else:
                # The contact's DUID does NOT represent a current
                # ParishSoft Member.  We'll try to match the contact to a ParishSoft
                # Member another way.
                del contact[key]
                contact[result_key]['msg'] = 'found DUID on CC record, but this is not a current ParishSoft Member; deleting DUID from CC record'
                contact[result_key]['action'] = 'delete from cc'

                # Fall through to below

        # If we get here, we didn't find a valid DUID.
        # So let's try a different way.
        member = find_ps_member(contact, ps_members, log)
        if member:
            contact['ps_member'] = member
            contact['memberDUID'] = member['memberDUID']
            if 'family' in member:
                contact['familyDUID'] = member['familyDUID']
            contact[result_key]['msg'] = 'searched and found corresponding ParishSoft Member'
            contact[result_key]['action'] = 'add to cc'
        else:
            contact[result_key]['msg'] = 'failed to find a corresponding ParishSoft Member'
            contact[result_key]['action'] = 'delete from cc'

def report_csv(contacts, log):
    filename = 'cc-contacts-raw-data.csv'
    fields = ['Email address', 'First name', 'Last name',
              'Matched to ParishSoft Member', 'Active ParishSoft Member',
              'In Constant Contact Lists',
              'Constant Contact Status', 'Constant Contact opt-out reason',
              'CC Street address', 'CC City', 'CC State', 'CC Zip']

    with open(filename, 'w') as fp:
        writer = csv.DictWriter(fp, fieldnames = fields)
        writer.writeheader()
        for contact in contacts:
            # Yes, there are contacts that do not have a first or last
            # name.  Sigh.
            first_name = ''
            if 'first_name' in contact:
                first_name = contact['first_name']
            last_name = ''
            if 'last_name' in contact:
                last_name = contact['last_name']

            matched = 'No'
            active_ps_member = ''
            if 'memberDUID' in contact:
                matched = 'Yes'
                member = contact['ps_member']
                if member['Inactive']:
                    active_ps_member = 'No'
                else:
                    active_ps_member = 'Yes'
                if 'family' in member:
                    familyDUID = member['familyDUID']

            cc_status = contact['email_address']['permission_to_send']
            cc_opt_out_reason = ''
            if cc_status == 'unsubscribed':
                okey = 'opt_out_reason'
                if okey in contact['email_address']:
                    cc_opt_out_reason = contact['email_address'][okey]
                else:
                    cc_opt_out_reason = 'Unknown'

            num_cc_lists = len(contact['list_memberships_uuids'])

            cc_street = ''
            cc_city = ''
            cc_state = ''
            cc_zip = ''
            key = 'street_addresses'
            if key in contact and len(contact[key]) > 0:
                def _lookup(contact, key, field):
                    if field in contact[key][0]:
                        return contact[key][0][field]
                    return ''

                cc_street = _lookup(contact, key, 'street')
                cc_city = _lookup(contact, key, 'city')
                cc_state = _lookup(contact, key, 'state')
                cc_zip = _lookup(contact, key, 'postal_code')

            item = {
                'Email address' : contact['email_address']['address'],
                'First name' : first_name,
                'Last name' : last_name,
                'Matched to ParishSoft Member' : matched,
                'Active ParishSoft Member' : active_ps_member,
                'ParishSoft Family DUID'   : familyDUID,
                'In Constant Contact Lists' : num_cc_lists,
                'Constant Contact Status' : cc_status,
                'Constant Contact opt-out reason' : cc_opt_out_reason,
                'CC Street address' : cc_street,
                'CC City' : cc_city,
                'CC State' : cc_state,
                'CC Zip' : cc_zip,
            }

            writer.writerow(item)


####################################################################
#
# Cross-reference UUIDs in each contact to real names / objects
#
####################################################################

def cc_resolve(contacts, custom_fields_arg, lists_arg, log):
    # Make dictionaries of the custom fields and lists (by UUID) for
    # quick reference.
    custom_fields = dict()
    for cf in custom_fields_arg:
        custom_fields[cf['custom_field_id']] = cf['name']

    lists = dict()
    for l in lists_arg:
        lists[l['list_id']] = l['name']

    # Now go through each contact and resolve the UUIDs to names /
    # objects.
    for contact in contacts:
        # For the custom fields, just add a "name" field to the
        # existing data structure.
        key = 'custom_fields'
        if key in contact:
            for cf in contact[key]:
                uuid = cf['custom_field_id']
                if uuid in custom_fields:
                    # Use all caps NAME to denote that we put this
                    # data here; it wasn't provided by CC.
                    cf['NAME'] = custom_fields[uuid]

                # Also, for convenience, save that custom field name
                # out on the outter contact data structure (not under
                # 'custom_fields').  This just saves a little code
                # elsewhere (i.e., we can just look for the custom
                # field name, look at all the 'NAME' values in
                # contact['custom_fields'] and then take its
                # corresponding 'value').
                contact[custom_fields[uuid]] = cf['value']

        # For list memberships, save the original value in
        # 'list_membership_uuids' (just in case we need it for some
        # reason), and replace 'list_memberships' with an array of the
        # list names.
        key = 'list_memberships'
        key2 = 'list_memberships_uuids'
        if key in contact:
            contact[key2] = contact[key]
            contact[key] = list()
            for uuid in contact[key2]:
                if uuid in lists:
                    contact[key].append(lists[uuid])

####################################################################
#
# Constant Contact general API
#
####################################################################

def cc_api_headers(client_id, access_token, include=None, limit=None):
    headers = {
        'Authorization' : f'Bearer {access_token["access_token"]}',
        'Cache-Control' : 'no-cache',
    }

    params = dict()
    if include or limit:
        if include:
            params['include'] = include
        if limit:
            params['limit'] = limit

    return headers, params

def cc_api_get_all(client_id, access_token,
                   api_endpoint, json_response_field,
                   log, include=None):
    # CC docs say 500 is the max
    headers, params = cc_api_headers(client_id, access_token,
                                     include=include, limit=500)

    base_url = f"{client_id['endpoints']['api']}/v3/{api_endpoint}"

    log.info(f"Loading all Constant Contact items from endpoint {api_endpoint}")

    items = list()
    url = base_url
    while url:
        log.debug(f"Getting URL: {url}")
        # JMS Need to surround this in a retry
        r = requests.get(url, headers=headers, params=params)
        if r.status_code != 200:
            log.error(f"Got a non-200 GET (all) status: {r.status_code}")
            log.error(r.text)
            exit(1)

        response = json.loads(r.text)
        #pprint(response)
        for item in response[json_response_field]:
            items.append(item)
        log.debug(f"Loaded {len(response[json_response_field])} items")

        url = None
        key = '_links'
        key2 = 'next'
        if key in response and key2 in response[key]:
            url = f"{client_id['endpoints']['api']}{response[key][key2]['href']}"

    log.info(f"Loaded {len(items)} total items")

    return items

def cc_api_get(client_id, access_token, uuid,
               api_endpoint, log, include=None):
    headers, params = cc_api_headers(client_id, access_token,
                                     include=include)

    url = f"{client_id['endpoints']['api']}/v3/{api_endpoint}/{uuid}"
    log.info(f"Loading a single Constant Contact item from endpoint {api_endpoint}")

    log.debug(f"Getting URL: {url}")
    # JMS Need to surround this in a retry
    r = requests.get(url, headers=headers, params=params)
    if r.status_code != 200:
        log.error(f"Got a non-200 GET status: {r.status_code}")
        log.error(r.text)
        exit(1)

    response = json.loads(r.text)
    return response

def cc_api_put(client_id, access_token,
               api_endpoint, body, log):
    headers, params = cc_api_headers(client_id, access_token)
    headers['Content-Type'] = 'application/json'

    url = f"{client_id['endpoints']['api']}/v3/{api_endpoint}"
    log.info(f"Putting a single Constant Contact item to endpoint {api_endpoint}")

    log.debug(f"Putting URL: {url}")
    log.debug(pformat(body))
    r = requests.put(url, headers=headers,
                     data=json.dumps(body))
    if r.status_code != 200:
        log.error(f"Got a non-200 PUT status: {r.status_code}")
        log.error(r.text)
        exit(1)

    response = json.loads(r.text)
    return response

####################################################################
#
# Constant Contact authentication
#
####################################################################

def cc_load_client_id(filename, log):
    with open(args.cc_client_id) as fp:
        client_id = json.load(fp)
        log.info(f"Read Constant Contact client_id file: {filename}")
        log.debug(client_id)
        return client_id

def set_valid_from_to(start, response):
    # The JSON that comes back from CC contains an "expires_in" field,
    # that's just a number of seconds from "now".  So add 2 fields to
    # the response: when "now" is, and when the access token expires.
    seconds = datetime.timedelta(seconds=int(response['expires_in']))
    response['valid from'] = start
    response['valid to'] = start + seconds


# Do the CC OAuth2 login.
#
# As of June 2023, per
# https://developer.constantcontact.com/api_guide/auth_overview.html,
# there are 4 Constant Contact OAuth2 flows available:
#
# 1. "Authorization Code Flow": this flow requires that the user visit
# a web page, authorize themselves to CC, and then CC redirects their
# browser to a URL of our choice where this app should be waiting to
# receive the CC authorization token (e.g., we'd tell CC to redirect
# to a URI of the form "http://localhost/...").  Frankly, I don't
# really want to setup a (temporary) local web server to receive this
# redirect, so we won't use this flow.
#
# 2. "PKCE Flow": this flow assumes that the app is running in a place
# where we can't store the client secret from
# https://app.constantcontact.com/pages/dma/portal/appList; it
# generates a challenge string that the user has to copy/paste into a
# web browser, and then copy-paste the response back into this app for
# verification.  Seems too much trouble.
#
# 3. "Device flow": this flow queries a CC authorization server to
# receive a unique OTP, and then presents a URL for the user to visit
# in their browser with that OTP.  After they authorize with their CC
# account, then the app is free to continue and request a CC
# authorization code.
#
# *** This is the flow we're using ("device flow") ***
#
# 4. "Implicit flow": this is similar to "authorization code flow" in
# that this app would need to setup a temporary local web server to
# receive the CC authorization code.  A key difference, however, is
# that these authorization codes are not refresh-able.  That's a
# deal-breaker for us.
def cc_oauth2_device_flow(args, client_id, log):
    post_data = {
        "client_id" : client_id['client id'],
        "response type" : "code",

        # The scope should be a space-delimited list of scopes from
        # https://v3.developer.constantcontact.com/api_guide/scopes.html.
        "scope" : 'contact_data offline_access',

        # The CC docs don't describe the "state" param They have one
        # example in the docs that is a string ("235o250eddsdff"), so
        # I'm assuming it can be a random number expressed as a
        # string.
        "state" : random.randrange(4294967296)
    }

    r = requests.post(client_id['endpoints']['auth'],
                      data = post_data)
    response = json.loads(r.text)
    log.debug("CC OAuth2 Device Flow got POST reply:")
    log.debug(pformat(response))

    print(f"\nGo to this URL and authenticate:")
    print(f"   {response['verification_uri_complete']}\n")

    _ = input("Hit enter when you have successfully completed that authorization: ")

    # Record the timestamp before we request the access token
    start = datetime.datetime.utcnow()

    # Now get an access token
    device_code = response['device_code']
    post_data = {
        "client_id" : client_id['client id'],
        'device_code' : device_code,

        # This value is from
        # https://developer.constantcontact.com/api_guide/device_flow.html
        'grant_type' : 'urn:ietf:params:oauth:grant-type:device_code',
    }
    r = requests.post(client_id['endpoints']['token'],
                      data = post_data)

    response = json.loads(r.text)
    log.debug("CC OAuth2 Device Flow got POST reply:")
    log.debug(pformat(response))

    set_valid_from_to(start, response)

    return response

# The Constant Contact OAuth2 refresh process is straightforward: post
# to a the token URL requesting a refresh.
def cc_oauth2_device_flow_refresh(client_id, access_token, log):
    # Record the timestamp before we request the access token
    start = datetime.datetime.utcnow()

    post_data = {
        "client_id" : client_id['client id'],
        "refresh_token" : access_token['refresh_token'],
        # This value is hard-coded from
        # https://developer.constantcontact.com/api_guide/server_flow.html
        'grant_type' : 'refresh_token',
    }

    r = requests.post(client_id['endpoints']['token'],
                      data = post_data)
    response = json.loads(r.text)
    log.debug("CC OAuth2 refresh flow got POST reply:")
    log.debug(pformat(response))

    set_valid_from_to(start, response)

    return response

def cc_save_access_token(filename, access_token, log):
    # The access_token dictionary has 2 datetime.datetime value, which
    # json.dump() won't serialize.  :-( So we have to convert those 2
    # values into strings so that they can be saved to a JSON file.
    data = copy.deepcopy(access_token)

    vfrom = access_token['valid from'].isoformat()
    vto = access_token['valid to'].isoformat()
    data['valid from'] = vfrom
    data['valid to'] = vto

    log.debug(f"Writing Constant Contact access token to {filename}")
    with open(filename, 'w') as fp:
        json.dump(data, fp, sort_keys=True, indent=4)

def cc_load_access_token(filename, log):
    # Convert the date/time strings in the JSON to python
    # datetime.datetime objects, for convenience.
    log.debug(f"Reading Constant Contact access token file {filename}")
    with open(filename) as fp:
        access_token = json.load(fp)

    vfrom = datetime.datetime.fromisoformat(access_token['valid from'])
    vto = datetime.datetime.fromisoformat(access_token['valid to'])

    access_token['valid from'] = vfrom
    access_token['valid to'] = vto
    log.debug(f"Read: {access_token}")

    return access_token

# Load the Constant Contact access token, either from a file, or do
# the Constant Contact OAuth2 authentication and/or refresh flows.
def cc_get_access_token(args, client_id, log):
    access_token = None

    # If the user supplied an auth_code file that does not exist, then
    # do the CC OAuth2 flow.
    if not os.path.exists(args.cc_access_token):
        log.info(f"Constant Contact access token file {args.cc_access_token} does not exist -- authorizing...")
        access_token = cc_oauth2_device_flow(args, client_id, log)
        cc_save_access_token(args.cc_access_token, access_token, log)

    # If the user supplied an auth_code file that exists and has
    # content, read it.
    elif os.path.exists(args.cc_access_token):
        access_token = cc_load_access_token(args.cc_access_token, log)

    # If we get here with no access token, error
    if access_token is None:
        log.error("No Constant Contact access token available")
        log.error("Aborting in despair")
        exit(1)

    # Check to ensure that the access token is still valid.
    now = datetime.datetime.utcnow()
    log.debug(f"Valid from: {access_token['valid from']}")
    log.debug(f"Now:        {now}")
    log.debug(f"Valid to:   {access_token['valid to']}")
    if access_token['valid from'] > now:
        log.error("Constant Contact access token is not valid yet (!)")
        log.error("Aborting in despair")
        exit(1)

    elif now > access_token['valid to']:
        log.warning("Constant Contact access token is no longer valid")
        log.debug("Attempting to refresh")

        # Refresh the token
        access_token = cc_oauth2_device_flow_refresh(client_id,
                                                     access_token, log)
        if access_token is None:
            log.warning("Unable to refresh Constant Contact access token")
            log.warning("Try manual authorization...")
            access_token = cc_oauth2_device_flow(args, client_id, log)
            cc_save_access_token(args.cc_access_token, access_token, log)

        # If we successfully refreshed, save the refreshed token
        cc_save_access_token(args.cc_access_token, access_token, log)

    # If all we were doing is authorizing, quit.
    if args.cc_auth_only:
        log.info("--cc-auth-only was specified; exiting")
        exit(0)

    return access_token

def setup_cli_args():

    tools.argparser.add_argument('--ps-api-keyfile',
                                 required=True,
                                 help='File containing the ParishSoft API key')
    tools.argparser.add_argument('--ps-cache-dir',
                                 default='.',
                                 help='Directory to cache the ParishSoft data')

    tools.argparser.add_argument('--dry-run',
                                 action='store_true',
                                 help='Do not actually update the Google Group; just show what would have been done')

    tools.argparser.add_argument('--verbose',
                                 action='store_true',
                                 default=True,
                                 help='If enabled, emit extra status messages during run')

    tools.argparser.add_argument('--debug',
                                 action='store_true',
                                 default=True,
                                 help='If enabled, emit even more extra status messages during run')

    tools.argparser.add_argument('--logfile',
                                 default="log.txt",
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

def main():
    args = setup_cli_args()

    log = ECC.setup_logging(info=args.verbose,
                            debug=args.debug,
                            logfile=args.logfile, rotate = True,
                            slack_token_filename=None)

    log.info("Loading ParishSoft info...")
    families, members, family_workgroups, member_workgroups, ministries = \
        ParishSoft.load_families_and_members(api_key=args.api_key,
                                             active_only=True,
                                             parishoners_only=False,
                                             cache_dir=args.ps_cache_dir,
                                             log=log)

    # Read Constant Contact client ID and token files
    cc_client_id  = cc_load_client_id(args.cc_client_id, log)
    cc_access_token = cc_get_access_token(args, cc_client_id, log)

    cc_contact_custom_fields = \
        cc_api_get_all(cc_client_id, cc_access_token,
                        'contact_custom_fields', 'custom_fields',
                        log)

    cc_lists = \
        cc_api_get_all(cc_client_id, cc_access_token,
                        'contact_lists', 'lists',
                        log)

    cc_contacts = \
        cc_api_get_all(cc_client_id, cc_access_token,
                        'contacts', 'contacts',
                        log,
                        include='custom_fields,list_memberships,street_addresses')

    exit(1)

    cc_resolve(cc_contacts, cc_contact_custom_fields,
                cc_lists, log)

    link_cc_contacts_to_ps_members(cc_contacts, members, log)



if __name__ == '__main__':
    main()