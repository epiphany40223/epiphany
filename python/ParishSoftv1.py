#!/usr/bin/env python3

'''

Helper for apps that use ParishSoft cloud data.

Most routines in this module are private to the module (i.e., those
starting with "_").  There's only a handful of public functions.

'''

import os
import json
import copy
import datetime
import requests

from pprint import pformat
from pprint import pprint
from urllib3.util import Retry
from requests.adapters import HTTPAdapter

import ECC

##############################################################################
#
# Global (but private) values

_ps_api_base_url = 'https://fsapi.parishsoft.app/api'

_ct_text = 'text/plain'
_ct_json = 'application/json'

_session = None

# Active Family group
active_family_group_name = "Active"

##############################################################################

def _setup_session():
    global _session
    if _session:
        return _session

    _session = requests.Session()

    # See: https://urllib3.readthedocs.io/en/stable/reference/urllib3.util.html#urllib3.util.Retry
    retries = Retry(
        total=3,
        backoff_factor=0.2,
        allowed_methods={'POST'},
    )
    _session.mount('https://', HTTPAdapter(max_retries=retries))

    return _session

# Login to the ParishSoft cloud using our API key and return the
# string token that we are issued (we use that token to authenticate
# all future API calls to the PS cloud).
def _login(api_key, log):
    session = _setup_session()

    if not api_key:
        raise Exception("ERROR: Must specify ParishSoft API key to login to the PS cloud")

    headers = {
        'Accept' : _ct_text,
        'Content-Type' : _ct_json,
    }
    payload = {
        'apiKey' : api_key,
    }
    log.debug(f"Logging in to ParishSoft cloud with API key {api_key}")
    response = session.post(f'{_ps_api_base_url}/Token/Authenticate',
                     headers=headers, json=payload)

    api_token = response.text
    log.debug(f"Got API token back: {api_token[0:8]}...")
    log.debug(f"Got API token back: {api_token}")

    return session, api_token

##############################################################################

def _save_cache(endpoint, elements, log):
    filename = f'cache-v1-{endpoint}.json'.replace('/', '-')

    with open(filename, 'w') as fp:
        json.dump(elements, fp)
    log.debug(f"Saved cache: {filename}")

def _load_cache(endpoint, log):
    filename = f'cache-v1-{endpoint}.json'.replace('/', '-')
    if not os.path.exists(filename):
        log.debug(f"No cache exists: {filename}")
        return None

    with open(filename) as fp:
        elements = json.load(fp)
    log.debug(f"Loaded cache: {filename}")
    return elements

#-----------------------------------------------------------------------------

_keyed_caches = dict()

# Save a single key's value in a filename in the cache
def _save_keyed_cache(endpoint, elements, log, kwargs):
    filename = f"cache-v1-{kwargs['keyed-endpoint']}.json".replace('/', '-')
    key = kwargs['key']

    if filename not in _keyed_caches:
        _keyed_caches[filename] = dict()
    _keyed_caches[filename][key] = elements

# Load a single key's value from a filename in the cache
def _load_keyed_cache(endpoint, log, kwargs):
    filename = f"cache-v1-{kwargs['keyed-endpoint']}.json".replace('/', '-')
    # JMS This is annoying, but it seems that json.dump() will write
    # int keys as strings :-(
    key = str(kwargs['key'])

    # If we don't have this file in the cache, try to load it
    if filename not in _keyed_caches:
        if not os.path.exists(filename):
            log.debug(f"No keyed cache exists: {filename}")
            return None

        with open(filename) as fp:
            _keyed_caches[filename] = json.load(fp)

    # We do have this file in the cache; look up the key we're looking
    # for
    if key in _keyed_caches[filename]:
        log.debug(f"Found keyed cache: {filename}, {key}")
        return _keyed_caches[filename][key]
    else:
        log.debug(f"Found keyed cache: {filename}, but {key} not present")
        return None

# At the end, write out *all* the accumulated keyed cache values
def _save_all_keyed_caches(log):
    log.debug(f"Saved all final keyed caches")
    for filename, value in _keyed_caches.items():
        with open(filename, 'w') as fp:
            json.dump(value, fp)
        log.debug(f"Saved final keyed cache {filename}")

##############################################################################

def _get_endpoint(session, api_token, endpoint, params, log, kwargs=None):
    if kwargs:
        elements = _load_keyed_cache(endpoint, log, kwargs)
    else:
        elements = _load_cache(endpoint, log)
    if elements is not None:
        return elements

    elements = []

    headers = {
        'Accept' : _ct_json,
        'Content-Type' : _ct_json,
        'Authorization' : f'Bearer {api_token}',
    }

    url = f'{_ps_api_base_url}/{endpoint}'
    if params and len(params) > 0:
        url += f'&{params}'

    log.debug(f"Getting URL: {url}")
    response = session.get(url, headers=headers)

    data = list()
    if response.text is not None and response.text != '':
        data = response.json()
    for element in data:
        elements.append(element)

    if kwargs:
        _save_keyed_cache(endpoint, elements, log, kwargs)
    else:
        _save_cache(endpoint, elements, log)

    return elements

#-----------------------------------------------------------------------------

def _get_paginated_endpoint(session, api_token, endpoint, params, log, limit=100):
    elements = _load_cache(endpoint, log)
    if elements:
        return elements

    elements = []

    headers = {
        'Accept' : _ct_json,
        'Content-Type' : _ct_json,
        'Authorization' : f'Bearer {api_token}',
    }

    # Per https://fsapi.parishsoft.app/index.html, we can ask for 100
    # elements at a time
    base_url = f'{_ps_api_base_url}/{endpoint}?Limit={limit}'

    # Loop to get all the families
    while True:
        url = f'{base_url}&Offset={len(elements)}'
        if params and len(params) > 0:
            url += f'&{params}'

        log.debug(f"Getting URL: {url}")
        response = session.get(url, headers=headers)
        data = response.json()

        # If there's no more, we're done.
        #
        # JMS: I'm not quite sure why we can't look at the
        # totalResults value in the returned data to know how many
        # there are -- but many times we do the query and get 0 back
        # in that field.  Hence, we just have to keep requesting until
        # we get an empty array back.  Shrug.
        if len(data) == 0:
            log.debug("Got empty elements array back -- we're done")
            break

        for element in data:
            elements.append(element)

    _save_cache(endpoint, elements, log)

    return elements

##############################################################################

def _get_org(session, api_token, log):
    elements = _get_endpoint(session, api_token,
                             endpoint='Organizations',
                             params=None, log=log)

    # Sanity check: we should only get 1 org back, and the name should
    # be "Epiphany Catholic Church"
    if len(elements) == 0:
        log.error("Got 0 organizations with this ParishSoft API key (expected 1)")
        exit(1)
    elif len(elements) != 1:
        log.error("Got {len(elements) organizations with this ParishSoft API key (expected 1)")
        log.error(data)
        exit(1)

    log.debug(f"Got org: {elements[0]['organizationID']} / {elements[0]['organizationReportName']}")

    org = elements[0]['organizationReportName']
    expected_org = 'Epiphany Catholic Church'
    if org != expected_org:
        log.error("Got unexpected ParishSoft organization name: {org} (expected {expected_org})")
        exit(1)

    return elements[0]['organizationID']

##############################################################################

def _load_families(session, api_token, org_id, log):
    elements = _get_paginated_endpoint(session, api_token,
                                       endpoint='Families',
                                       params=None,
                                       log=log)

    families = { int(element['familyDUID']) : element for element in elements }
    return families

def _load_family_groups(session, api_token, org_id, log):
    elements = _get_endpoint(session, api_token,
                             endpoint='Families/Groups',
                             params=None, log=log)

    family_groups = { int(element['famGroupID']) : element['famGroup'] for element in elements }
    return family_groups

def _load_family_workgroups(session, api_token, org_id, log):
    elements = _get_endpoint(session, api_token,
                             endpoint='Families/WorkGroups',
                             params=None, log=log)

    family_groups = { int(element['workgroupID']) : element['workgroupName'] for element in elements }
    return family_groups

#-----------------------------------------------------------------------------

def _load_members(session, api_token, org_id, log):
    elements = _get_paginated_endpoint(session, api_token,
                                       endpoint='Members',
                                       params=None,
                                       log=log)

    members = { int(element['memberDUID']) : element for element in elements }
    return members

def _load_member_statuses(session, api_token, org_id, log):
    elements = _get_endpoint(session, api_token,
                             endpoint='Members/MemberStatuses',
                             params=None, log=log)

    member_statuses = { int(element['memberStatusID']) : element['memberStatus'] for element in elements }
    return member_statuses

def _load_member_types(session, api_token, org_id, log):
    elements = _get_endpoint(session, api_token,
                             endpoint='Members/MemberTypes',
                             params=None, log=log)

    member_types = [ element['MemberType'] for element in elements ]
    return member_types

def _load_member_workgroups(session, api_token, org_id, log):
    elements = _get_endpoint(session, api_token,
                             endpoint='Members/WorkGroups',
                             params=None, log=log)

    member_workgroups = [ element['Name'] for element in elements ]
    return member_workgroups

def _merge_member_contactinfos(session, api_token, org_id, members, log):
    elements = _get_endpoint(session, api_token,
                             endpoint='Members/ContactInfo',
                             params=None, log=log)

    # The contactInfo field seems to only have a few unique
    # fields: fax, gender, middleName, nickName, and pager.
    #
    # Copy these fields up into top-level values on the member
    # (vs. having to go through a lower-level 'contactinfo'
    # object).
    for element in elements:
        mid = element['memberDUID']
        if mid in members:
            member = members[mid]
            member['dateOfBirth'] = element['dateOfBirth']
            member['gender'] = element['gender']
            member['middleName'] = element['middleName']
            member['nickName'] = element['nickName']

def _load_member_id_workgroups(session, api_token, members, log):
    kwargs = {
        'keyed-endpoint' : 'Members/mid/WorkGroups',
    }

    count = 0
    for mid, member in members.items():
        count += 1

        log.debug(f"Getting {count} of {len(members)}: Member workgroups for {mid} / {member['display_MemberFullName']}")
        kwargs['key'] = int(mid)
        elements = _get_endpoint(session, api_token,
                                 endpoint=f'Members/{mid}/WorkGroups',
                                 params=None, log=log,
                                 kwargs=kwargs)

        member['workGroups'] = [ element['Label'] for element in elements ]

def _load_member_id_ministryrecords(session, api_token, members, log):
    kwargs = {
        'keyed-endpoint' : 'MinistryScheduler/MinistryRecords',
    }

    count = 0
    for mid, member in members.items():
        count += 1

        log.debug(f"Getting {count} of {len(members)}: Member ministry records for {mid} / {member['display_MemberFullName']}")
        kwargs['key'] = int(mid)
        elements = _get_endpoint(session, api_token,
                                 endpoint=f'MinistryScheduler/MinistryRecords/{mid}',
                                 params=None, log=log,
                                 kwargs=kwargs)

        member['active ministries'] = [ element for element in elements ]

##############################################################################

def _link_families_and_members(families, members, log):
    log.debug("Linking families and members")
    mkey = 'members'
    fkey = 'family'

    for mid, member in members.items():
        fid = member['familyDUID']
        if fid not in families:
            continue

        family = families[fid]
        member[fkey] = family
        if mkey not in family:
            family[mkey] = list()
        family[mkey].append(member)

        # Set some PDS equivalents, just for old times' sake :-)
        family['FamRecNum'] = fid
        member['MemRecNum'] = mid

# This function filters families and members *in place*.
def _filter_families_and_members(families, members,
                                 org_id, family_groups,
                                 active_only, parishioners_only,
                                 log):
    fids_to_delete = dict()

    log.debug(f"Filtering: active={active_only}, parishioner={parishioners_only}")

    # "Active" Families are defined as being in the "Active"
    # Family group.
    if active_only:
        fgid = -1
        for id, name in family_groups.items():
            if name == active_family_group_name:
                fgid = id
                break

        for fid, family in families.items():
            if family['famGroupID'] != fgid:
                # We cannot delete a family while we are traversing
                # the families dictionary.  So just save the FID for
                # deleting later.
                fids_to_delete[fid] = True

    if parishioners_only:
        org_id = int(org_id)
        for fid, family in families.items():
            roid = family['registeredOrganizationID']
            if roid != org_id:
                fids_to_delete[fid] = True

    # Delete any family -- and corresponding members -- that we marked
    # for deletion
    for fid in fids_to_delete.keys():
        for member in families[fid]['members']:
            mid = member['memberDUID']
            del members[mid]

        del families[fid]

##############################################################################

# Convert all date strings to Python datetimes
def _normalize_dates(elements, fields, log):
    for element in elements.values():
        for field in fields:
            if field not in element:
                continue
            val = element[field]
            if val is None or val == '':
                continue
            d = datetime.datetime.fromisoformat(element[field]).date()
            element[field] = d

##############################################################################

# Load PS Families and Members.  Return them as 2 giant hashes,
# appropriately cross-linked to each other.
def load_families_and_members(api_key=None,
                              active_only=True, parishioners_only=True,
                              log=None):
    if not api_key:
        raise Exception("ERROR: Must specify ParishSoft API key to login to the PS cloud")

    session, api_token = _login(api_key, log)

    org = _get_org(session, api_token, log)

    families = _load_families(session, api_token, org, log)
    family_groups = _load_family_groups(session, api_token, org, log)
    family_workgroups = _load_family_workgroups(session, api_token, org, log)

    members = _load_members(session, api_token, org, log)
    member_statuses = _load_member_statuses(session, api_token, org, log)
    member_types = _load_member_types(session, api_token, org, log)
    member_workgroups = _load_member_workgroups(session, api_token, org, log)
    _merge_member_contactinfos(session, api_token, org, members, log)

    # Link families and members together
    _link_families_and_members(families, members, log)

    # Filter based on active/parishioner status.  Do this now so
    # that we only retrieve the rest of the data based on the
    # filtered results of this operation.
    _filter_families_and_members(families, members,
                                 org, family_groups,
                                 active_only, parishioners_only,
                                 log)

    # This queries every Member (which is why we waited until after we
    # filtered out undesired Members).
    _load_member_id_workgroups(session, api_token, members, log)
    _load_member_id_ministryrecords(session, api_token, members, log)

    # Save everything we downloaded from ParishSoft's API
    _save_all_keyed_caches(log)

    # Convert date strings to Python dates
    _normalize_dates(members, ['birthdate', 'dateofDeath', 'dateModified' ], log)
    _normalize_dates(families, ['dateModified'], log)

    return families, members
