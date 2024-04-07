#!/usr/bin/env python3

'''

Helper for apps that use ParishSoft cloud data.

Most routines in this module are private to the module (i.e., those
starting with "_").  There's only a handful of public functions.

'''

import os
import re
import sys
import csv
import json
import time
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

_ps_api_base_url = 'https://ps-fs-external-api-prod.azurewebsites.net/api/v2'

_ct_text = 'text/plain'
_ct_json = 'application/json'

_session = None

_org_id = None

# 14 minutes ago (because we run via cron every 15 minutes)
_cache_limit = time.time() - (60 * 14)

# DEBUGGING: A day ago
#_cache_limit = time.time() - (24 * 60 * 60)

##############################################################################

def _setup_session(api_key):
    global _session
    if _session:
        return _session

    _session = requests.Session()
    _session.headers.update({'x-api-key': api_key})

    # See: https://urllib3.readthedocs.io/en/stable/reference/urllib3.util.html#urllib3.util.Retry
    retries = Retry(
        total=3,
        backoff_factor=0.2,
        allowed_methods={'POST', 'GET'},
    )
    _session.mount('https://', HTTPAdapter(max_retries=retries))

    return _session

##############################################################################

def _save_cache(endpoint, elements, cache_dir, log):
    filename = os.path.join(cache_dir,
                            f'cache-v2-{endpoint}.json'.replace('/', '-'))

    with open(filename, 'w') as fp:
        json.dump(elements, fp)
    log.debug(f"Saved cache: {filename}")

def _load_cache(endpoint, cache_dir, log):
    filename = os.path.join(cache_dir,
                            f'cache-v2-{endpoint}.json'.replace('/', '-'))
    if not os.path.exists(filename):
        log.debug(f"No cache exists: {filename}")
        return None

    s = os.stat(filename)
    if s.st_mtime < _cache_limit:
        log.debug(f"Cache file exists, but is too old: {filename}")
        return None

    with open(filename) as fp:
        elements = json.load(fp)
    log.debug(f"Loaded cache: {filename}")
    return elements

#-----------------------------------------------------------------------------

_keyed_caches = dict()

# Save a single key's value in a filename in the cache
def _save_keyed_cache(endpoint, elements, cache_dir, log, kwargs):
    filename = os.path.join(cache_dir,
                            f"cache-v2-{kwargs['keyed-endpoint']}.json".replace('/', '-'))
    key = kwargs['key']

    if filename not in _keyed_caches:
        _keyed_caches[filename] = dict()
    _keyed_caches[filename][key] = elements

# Load a single key's value from a filename in the cache
def _load_keyed_cache(endpoint, cache_dir, log, kwargs):
    filename = os.path.join(cache_dir,
                            f"cache-v2-{kwargs['keyed-endpoint']}.json".replace('/', '-'))
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

def _get_endpoint(session, endpoint, params, cache_dir, log, kwargs=None):
    if kwargs:
        elements = _load_keyed_cache(endpoint, cache_dir, log, kwargs)
    else:
        elements = _load_cache(endpoint, cache_dir, log)
    if elements is not None:
        return elements

    headers = {
        'Accept' : _ct_json,
        'Content-Type' : _ct_json,
    }

    url = f'{_ps_api_base_url}/{endpoint}'
    if params and len(params) > 0:
        url += f'&{params}'

    log.debug(f"Getting URL: {url}, headers {headers}")
    response = session.get(url, headers=headers)

    log.debug(f"Got response: {response}")
    #log.debug(f"Got response text: {response.text}")

    elements = list()
    if response.status_code >= 200 and response.status_code < 300:
        data = list()
        if response.text is not None and response.text != '':
            data = response.json()
        for element in data:
            elements.append(element)

    if kwargs:
        _save_keyed_cache(endpoint, elements, cache_dir, log, kwargs)
    else:
        _save_cache(endpoint, elements, cache_dir, log)

    return elements

#-----------------------------------------------------------------------------

def _get_paginated_endpoint(session, endpoint, params, cache_dir, log,
                            limit_name='Limit', limit=100,
                            offset_name='Offset', offset_type='index',
                            kwargs=None):
    if params is None or len(params) == 0:
        cache_endpoint = endpoint
    else:
        cache_endpoint = f'{endpoint}?{params}'
    if kwargs:
        elements = _load_keyed_cache(cache_endpoint, cache_dir, log, kwargs)
    else:
        elements = _load_cache(cache_endpoint, cache_dir, log)
    if elements:
        return elements

    elements = []

    headers = {
        'Accept' : _ct_json,
        'Content-Type' : _ct_json,
    }

    # Per https://fsapi.parishsoft.app/index.html, we can ask for 100
    # elements at a time
    base_url = f'{_ps_api_base_url}/{endpoint}?{limit_name}={limit}'

    # Loop to get all the elements
    page_num = 1
    while True:
        if offset_type == 'index':
            url = f'{base_url}&{offset_name}={len(elements)}'
        else:
            url = f'{base_url}&{offset_name}={page_num}'

        if params and len(params) > 0:
            url += f'&{params}'

        log.debug(f"Getting URL: {url}")
        response = session.get(url, headers=headers)
        data = response.json()

        # There's (at least?) 2 flavors of paging in the data returned:
        # 1. a simple (Python) list
        # 2. a dictionary with 'pagingInfo' and 'data' keys
        if type(data) is list:
            log.debug(f"Got {len(data)} elements back")
            for element in data:
                elements.append(element)

            # If there's no more, we're done.
            if len(data) == 0:
                log.debug("Got empty elements array back -- we're done")
                break

        elif type(data) is dict:
            log.debug(f"Got {len(data['data'])} elements back")
            for element in data['data']:
                elements.append(element)
            pi = data['pagingInfo']

            # If there's no more, we're done
            if pi['pageNumber'] >= pi['totalPages']:
                log.debug("Got last page back -- we're done")
                break

        page_num += 1

    _save_cache(cache_endpoint, elements, cache_dir, log)

    return elements

##############################################################################

def _post_endpoint(session, endpoint, params, cache_dir, log, kwargs=None):
    if params is None or len(params) == 0:
        cache_endpoint = endpoint
    else:
        cache_endpoint = f'{endpoint}?{params}'
    if kwargs:
        elements = _load_keyed_cache(cache_endpoint, cache_dir, log, kwargs)
    else:
        elements = _load_cache(cache_endpoint, cache_dir, log)
    if elements is not None:
        return elements

    headers = {
        'Accept' : _ct_json,
        'Content-Type' : _ct_json,
    }

    url = f'{_ps_api_base_url}/{endpoint}'
    log.debug(f"Getting URL: {url}, headers {headers}, params {params}")

    # Explicitly make the request because we may need to modify it:
    # ParishSoft requires us to pass in "{}" for calls with no
    # parameters.  Python requests will -- by default -- not pass in
    # anything.
    if params is None:
        response = session.post(url, headers=headers, json='{}')
    else:
        response = session.post(url, headers=headers, json=params)

    log.debug(f"Got response: {response}")
    #log.debug(f"Got response text: {response.text}")

    elements = list()
    if response.status_code >= 200 and response.status_code < 300:
        data = list()
        if response.text is not None and response.text != '':
            data = response.json()
        for element in data:
            elements.append(element)

    _save_cache(cache_endpoint, elements, cache_dir, log)
    return elements

#-----------------------------------------------------------------------------

def _post_paginated_endpoint(session, endpoint, params, cache_dir, log,
                             limit_name='Limit', limit=100,
                             offset_name='Offset', offset_type='index',
                             kwargs=None):
    if kwargs:
        elements = _load_keyed_cache(endpoint, cache_dir, log_kwargs)
    else:
        elements = _load_cache(endpoint, cache_dir, log)
    if elements is not None:
        return elements

    elements = []

    headers = {
        'Accept' : _ct_json,
        'Content-Type' : _ct_json,
    }

    # Per https://fsapi.parishsoft.app/index.html, we can ask for 100
    # elements at a time
    url = f'{_ps_api_base_url}/{endpoint}'

    # Loop to get all the elements
    # Page number starts with 1
    page_num = 1
    while True:
        if offset_type == 'index':
            value = len(elements)
        else:
            value = page_num

        if params:
            params[offset_name] = value
            params[limit_name] = limit
        else:
            params = {
                offset_name : value,
                limit_name : limit,
            }

        log.debug(f"Getting URL: {url}, params {params}")
        response = session.post(url, headers=headers, json=params)
        data = response.json()

        # If there's no more, we're done.
        #
        # JMS: I'm not quite sure why we can't look at the
        # totalResults value in the returned data to know how many
        # there are -- but many times we do the query and get 0 back
        # in that field.  Hence, we just have to keep requesting until
        # we get an empty array back.  Shrug.
        log.debug(f"Got {len(data)} elements back")
        if len(data) == 0:
            log.debug("Got empty elements array back -- we're done")
            break

        for element in data:
            elements.append(element)

        page_num += 1

    _save_cache(endpoint, elements, cache_dir, log)

    return elements

##############################################################################

def _normalize_dates(elements, fields):
    for element in elements:
        for field in fields:
            if field in element and element[field] is not None:
                temp = datetime.datetime.fromisoformat(element[field]).date()
                element[field] = temp

##############################################################################

def _get_org(session, cache_dir, log):
    elements = _post_endpoint(session,
                              endpoint='organizations/search',
                              params={}, cache_dir=cache_dir, log=log)


    # Sanity check: we should only get 1 org back, and the name should
    # be "Epiphany Parish"
    if len(elements) == 0:
        log.error("Got 0 organizations with this ParishSoft API key (expected 1)")
        exit(1)
    elif len(elements) != 1:
        log.error(f"Got {len(elements)} organizations with this ParishSoft API key (expected 1)")
        log.error(elements)
        exit(1)

    log.debug(f"Got org: {elements[0]['organizationID']} / {elements[0]['organizationReportName']}")

    org = elements[0]['organizationReportName']
    expected_org = 'Epiphany Catholic Church'
    if org != expected_org:
        log.error(f"Got unexpected ParishSoft organization name: {org} (expected {expected_org})")
        exit(1)

    # Save this in the global scope
    global _org_id
    _org_id = elements[0]['organizationID']

    return _org_id

##############################################################################

# Indexed by Family DUID
def _load_families(session, org_id, cache_dir, log):
    params = { 'organizationIDs': [ org_id ], }
    elements = _post_paginated_endpoint(session,
                                        endpoint='families/search',
                                        params=params,
                                        cache_dir=cache_dir,
                                        log=log,
                                        offset_name="PageNumber",
                                        offset_type="page")

    _normalize_dates(elements, ['dateModified'])

    families = { int(element['familyDUID']) : element for element in elements }

    # A bunch of families have multiple email addresses separated by
    # ";".  Split these into a Python list.
    key = 'py eMailAddresses'
    for family in families.values():
        family[key] = list()

        value = family['eMailAddress']
        if value:
            for address in value.split(';'):
                family[key].append(address.strip().lower())

    return families

# Indexed by Family Group ID
def _load_family_groups(session, cache_dir, log):
    elements = _get_endpoint(session,
                             endpoint='families/group/lookup/list',
                             cache_dir=cache_dir,
                             params=None, log=log)

    family_groups = { int(element['famGroupID']) : element['famGroup'] for element in elements }
    return family_groups

# Indexed by Family Workgroup DUID
def _load_family_workgroups(session, cache_dir, log):
    log.debug("Loading Family Workgroups")
    elements = _get_paginated_endpoint(session,
                                       endpoint='families/workgroup/list',
                                       cache_dir=cache_dir,
                                       params=None, log=log)

    family_groups = {
        int(element['workgroupDUID']) : {
            'name' : element['workgroupName'],
            'duid' : element['workgroupDUID'],
            'id' : element['workgroupID']
        } for element in elements
    }
    return family_groups

# Workgroups indexed by Family Workgoup DUID
# Membership is a list (not indexed)
def _load_family_workgroup_memberships(session, family_workgroups,
                                       cache_dir, log):
    log.debug("Loading Family Workgroup memberships")
    results = {}
    for duid, wg in family_workgroups.items():
        log.debug(f"Loading membership of Family Workgroup DUID {duid}: {wg['name']}")
        elements = _get_paginated_endpoint(session,
                                           endpoint=f'families/workgroup/{duid}/list',
                                           params=None, log=log,
                                           cache_dir=cache_dir,
                                           offset_name="PageNumber",
                                           offset_type="page")
        log.debug(f"Got {len(elements)} members of Family WorkGroup DUID {duid}: {wg['name']}")
        results[duid] = {
            'duid' : duid,
            'id' : wg['id'],
            'name' : wg['name'],
            'membership' : elements,
        }

        first = True
        if first:
            log.debug(pformat(wg))
            first = False

    return results

#-----------------------------------------------------------------------------

# Indexed by Member DUID
def _load_members(session, org_id, cache_dir, log):
    params = { 'organizationIDs': [ org_id ], }
    elements = _post_paginated_endpoint(session,
                                        endpoint='members/search',
                                        params=params,
                                        cache_dir=cache_dir,
                                        log=log,
                                        limit_name='maximumRows',
                                        offset_name='startRowIndex',
                                        offset_type='page')

    _normalize_dates(elements, ['birthdate', 'dateModified', 'dateOfDeath'])

    members = { int(element['memberDUID']) : element for element in elements }

    return members

# Indexed by Member Status ID
def _load_member_statuses(session, api_key, org_id, cache_dir, log):
    elements = _get_endpoint(session,
                             endpoint='members/memberstatus/list',
                             cache_dir=cache_dir,
                             params=None, log=log)

    member_statuses = { int(element['memberStatusID']) : element['memberStatusName'] for element in elements }
    return member_statuses

# Returns a list of strings -- not indexed
def _load_member_types(session, api_key, org_id, cache_dir, log):
    elements = _get_endpoint(session,
                             endpoint='members/membertype/list',
                             cache_dir=cache_dir,
                             params=None, log=log)

    return elements

# Indexed by Member DUID
def _load_member_contactinfos(session, org_id, cache_dir, log):
    params = { 'organizationIDs': [ org_id ], }
    elements = _post_paginated_endpoint(session,
                                        endpoint='members/contact/list',
                                        params=params, log=log,
                                        cache_dir=cache_dir,
                                        offset_type='page')

    _normalize_dates(elements, ['dateOfBirth', 'dateOfDeath'])

    member_contactinfos = { int(element['memberDUID']) : element for element in elements }
    return member_contactinfos

# Indexed by Member Workgroup DUID
def _load_member_workgroups(session, api_key, org_id, cache_dir, log):
    # As of 16 Mar 2024, there is no API to get the Member Workgroup
    # IDs -- the members/workgroup/list API just returns a list of
    # names (with no IDs).  As such, Andrew Halsted at ParishSoft ran
    # a report on the back-end and provided the mapping for us.
    #
    # We'll therefore call the members/workgroup/list API to get the
    # current list of names and then use a CSV of the data Andrew
    # provided to us to fill in the IDs.  If we make any new member
    # workgroups, we'll discover this by not having an ID for it.
    log.debug("Loading Member Workgroups")
    names = _get_endpoint(session,
                          endpoint='members/workgroup/list',
                          cache_dir=cache_dir,
                          params=None, log=log)

    filename = 'ps-provided-member-workgroups.csv'
    log.debug(f"Loading local cache file: {filename}")
    elements = {}
    with open(filename) as fp:
        reader = csv.DictReader(fp)
        for row in reader:
            id = row['Workgroup ID']
            name = row['Name']

            if name in names and id not in elements:
                elements[id] = {
                    'id' : id,
                    'name' : name,
                }

    return elements

# Indexed by Member Workgroup DUID
# Membership is a list (not indexed)
def _load_member_workgroup_memberships(session, member_workgroups,
                                       cache_dir, log):
    results = {}
    for duid, wg in member_workgroups.items():
        log.debug(f"Loading membership of Member Workgroup DUID {duid}: {wg['name']}")
        elements = _get_paginated_endpoint(session,
                                           endpoint=f'members/workgroup/{duid}/list',
                                           cache_dir=cache_dir,
                                           params=None, log=log,
                                           offset_name="PageNumber",
                                           offset_type="page")
        log.debug(f"Got {len(elements)} members of Member WorkGroup DUID {duid}: {wg['name']}")
        results[duid] = {
            'duid' : duid,
            'id' : wg['id'],
            'name' : wg['name'],
            'membership' : elements,
        }

    return results

##############################################################################

# Indexed by Ministry Type ID (not sure if this is a DUID or not...?)
def _load_ministry_types(session, cache_dir, log):
    log.debug("Loading Ministry Types")
    elements = _get_paginated_endpoint(session,
                                       endpoint='ministry/type/list',
                                       params=None, log=log,
                                       cache_dir=cache_dir,
                                       offset_name="PageNumber",
                                       offset_type="page")

    # Here, we allowlist only specific ministries.  We have lots of
    # historical records, and we don't need to load ministries that
    # are old / defunct.
    ministry_types = dict()
    for element in elements:
        name = element['name']

        # Keep ministries that start with three digits or are
        # specifically-named.
        want = False
        if re.match(r'\d\d\d\-', name):
            want = True
        elif name == 'E-Soul Life' or name == 'E-Taize Prayer':
            want = True

        if want:
            id = element['id']
            ministry_types[int(id)] = {
                'name' : name,
                'id' : id,
            }

    return ministry_types

# Indexed by Ministry Type ID
# Membership is a list (not indexed)
def _load_ministry_type_memberships(session, ministry_types, cache_dir, log):
    results = {}
    for id, type in ministry_types.items():
        log.debug(f"Loading membership of Ministry Type ID {id}: {type['name']}")
        elements = _get_paginated_endpoint(session,
                                           endpoint=f'ministry/{id}/minister/list',
                                           params=None, log=log,
                                           cache_dir=cache_dir,
                                           offset_name="PageNumber",
                                           offset_type="page")
        log.debug(f"Got {len(elements)} members of Ministry Type ID {id}: {type['name']}")

        _normalize_dates(elements, ['startDate', 'endDate'])

        results[id] = {
            'id' : type['id'],
            'name' : type['name'],
            'membership' : elements,
        }

    return results

##############################################################################

def _link_family_groups(families, family_groups, log):
    for family in families.values():
        key = 'famGroupID'
        if key in family:
            fam_duid = family[key]
            if fam_duid in family_groups:
                family['py family group'] = family_groups[fam_duid]
            else:
                log.warning(f'Could not find family group ID {fam_duid}')

def _link_family_workgroups(families, family_workgroup_memberships, log):
    for family in families.values():
        family['py workgroups'] = dict()

    key = 'membership'
    for wg_id, wg in family_workgroup_memberships.items():
        if key not in wg:
            continue
        for element in wg[key]:
            fam_duid = element['familyId']
            if fam_duid in families:
                family = families[fam_duid]

                # Put extra cross-references back up to the members /
                # families dictionaries to assist when deleting a
                # Member or Family: this makes it easier to find all
                # relevant Member Workgroup entries and delete them,
                # too.  Put DUIDs here instead of object references
                # because putting object references makes pprint()
                # output a nightmare.
                element['py family duid'] = fam_duid
                families[fam_duid]['py workgroups'][wg['name']] = {
                    'duid' : wg['duid'],
                    'id' : wg['id'],
                    'name' : wg['name'],
                    'family duid' : family['familyDUID'],
                }

def _link_member_contactinfos(members, member_contactinfos, log):
    for mem_duid, member in members.items():
        member['py workgroups'] = dict()
        member['py ministries'] = dict()
        if mem_duid in member_contactinfos:
            member['py contactInfo'] = member_contactinfos[mem_duid]

def _link_member_workgroups(members, member_workgroup_memberships, log):
    for member in members.values():
        member['py workgroups'] = dict()

    key = 'membership'
    for wg_id, wg in member_workgroup_memberships.items():
        if key not in wg:
            continue
        for element in wg[key]:
            mem_duid = element['memberId']
            if mem_duid in members:
                member = members[mem_duid]
                family = member['py family']
                fam_duid = family['familyDUID']

                # Put extra cross-references back up to the members /
                # families dictionaries to assist when deleting a
                # Member or Family: this makes it easier to find all
                # relevant Member Workgroup entries and delete them,
                # too.  Put DUIDs here instead of object references
                # because putting object references makes pprint()
                # output a nightmare.
                element['py member duid'] = mem_duid
                element['py family duid'] = fam_duid
                members[mem_duid]['py workgroups'][wg['name']] = {
                    'duid' : wg['duid'],
                    'id' : wg['id'],
                    'name' : wg['name'],
                    'member duid' : mem_duid,
                    'family duid' : fam_duid,
                }

def _link_member_ministries(members, ministry_type_memberships, log):
    for member in members.values():
        member['py ministries'] = dict()

    key = 'membership'
    for min_id, ministry in ministry_type_memberships.items():
        if key not in ministry:
            continue

        for record in ministry[key]:
            mem_duid = record['memberId']
            if mem_duid in members:
                member = members[mem_duid]
                family = member['py family']
                fam_duid = family['familyDUID']

                # Put extra cross-references back up to the members /
                # families dictionaries to assist when deleting a
                # Member or Family: this makes it easier to find all
                # relevant Member Workgroup entries and delete them,
                # too.  Put DUIDs here instead of object references
                # because putting object references makes pprint()
                # output a nightmare.
                record['py member duid'] = mem_duid
                record['py family duid'] = fam_duid
                members[mem_duid]['py ministries'][ministry['name']] = {
                    'id' : ministry['id'],
                    'name' : ministry['name'],
                    'role' : record['ministryRoleName'],
                    'start date' : record['startDate'],
                    'member duid' : mem_duid,
                    'family duid' : fam_duid,
                }

def _make_member_friendly_name(members, log):
    k1 = 'py contactInfo'
    k2 = 'nickName'
    for member in members.values():
        if k1 in member and k2 in member[k1] and member[k1][k2] is not None:
            fl = f'{member[k1][k2]} {member["lastName"]}'
            lf = f'{member["lastName"]}, {member[k1][k2]}'
        else:
            fl = f'{member["firstName"]} {member["lastName"]}'
            lf = f'{member["lastName"]}, {member["firstName"]}'

        member['py friendly name FL'] = fl
        member['py friendly name LF'] = lf

def _link_families_and_members(families, members, log):
    for fam_duid, family in families.items():
        family['py members'] = list()

        for member in members.values():
            if member['familyDUID'] == fam_duid:
                member['py family'] = family
                family['py members'].append(member)

##############################################################################

# Our current definition of an "Active" Family is that they are
# not in the "Inactive" Family Group.
def family_is_active(family):
    key = 'py family group'
    if key in family and family[key] == 'Inactive':
        return False

    return True

# Our current definition of a "Parishioner" Family is one who is in
# Epiphany's organization.
def family_is_parishioner(family, org_id=None):
    if org_id is None:
        org_id = _org_id

    key = 'registeredOrganizationID'
    if key in family and family[key] == org_id:
        return True

    return False

#-----------------------------------------------------------------------------

# Our current definition of an "Active" Member is that they do not
# have the "Inactive" or "Deceased" Member Status.
def member_is_active(member):
    key = 'memberStatus'
    if key in member and (member[key] == 'Inactive' or member[key] == 'Deceased'):
        return False

    return True

#-----------------------------------------------------------------------------

def _filter(families, members,
            family_workgroup_memberships,
            member_workgroup_memberships,
            ministry_type_memberships,
            active_only, parishioners_only,
            org, log):

    # If there's nothing to do, then do nothing
    if not active_only and not parishioners_only:
        return

    # We have something to filter.

    # Filter Members.  Parishioners are labeled at the Family level,
    # so we only have to check here for inactive Members.
    mem_active_key = 'py active'
    members_to_delete = list()
    for id, member in members.items():
        if member_is_active(member):
            member[mem_active_key] = True
        else:
            member[mem_active_key] = False
            members_to_delete.append(member['memberDUID'])

    # Now filter Families.  Also look for Families that no longer have
    # any Active Members (e.g., if we deleted them above).
    families_to_delete = list()
    for family in families.values():
        want = True
        if active_only and not family_is_active(family):
            want = False

        if parishioners_only and not family_is_parishioner(family, org):
            want = False

        # Are all Members of this Family inactive?
        any_active_member = False
        for member in family['py members']:
            if mem_active_key in member and member[mem_active_key]:
                any_active_member = True
        if not any_active_member:
            want = False

        # If we don't want the Family, delete it.  But we can't delete
        # while we're iterating through the families dictionary, so
        # just save the Family DUID in a to-be-deleted list.
        if not want:
            families_to_delete.append(family['familyDUID'])

    log.debug(f"Filtering: deleting {len(members_to_delete)} out of {len(members)} Members")
    log.debug(f"Filtering: deleting {len(families_to_delete)} out of {len(families)} Families")

    # Now do the actual deletions.
    #
    # Re-creating the Family Workgroups, Member Workgroups, and
    # Ministries lists for each Family deletion seems inefficient as
    # hell.  But there's only a few thousand families, so it's not
    # inefficient enough to matter (it still runs in less than a
    # second).
    for mem_duid in members_to_delete:
        # Delete from Member Workgroups
        for id in member_workgroup_memberships.keys():
            member_workgroup_memberships[id]['membership'][:] = \
                [ element for element in member_workgroup_memberships[id]['membership']
                  if element['py member duid'] != mem_duid ]

        # Delete from Member Workgroups
        for id in member_workgroup_memberships.keys():
            member_workgroup_memberships[id]['membership'][:] = \
                [ element for element in member_workgroup_memberships[id]['membership']
                  if element['py member duid'] != mem_duid ]

        # Delete from Ministries
        for id in ministry_type_memberships.keys():
            ministry_type_memberships[id]['membership'][:] = \
                [ element for element in ministry_type_memberships[id]['membership']
                  if element['py member duid'] != mem_duid ]

        # Delete this Member from their Family
        family = member['py family']
        for i, member in enumerate(family['py members']):
            if member['memberDUID'] == mem_duid:
                del family['py members'][i]
                break

        # Delete from Members
        del members[mem_duid]

    for fam_duid in families_to_delete:
        family = families[fam_duid]

        # Delete from Family Workgroups
        for id in family_workgroup_memberships.keys():
            family_workgroup_memberships[id]['membership'][:] = \
                [ element for element in family_workgroup_memberships[id]['membership']
                  if element['py family duid'] != fam_duid ]

        # Delete from Member Workgroups
        for id in member_workgroup_memberships.keys():
            member_workgroup_memberships[id]['membership'][:] = \
                [ element for element in member_workgroup_memberships[id]['membership']
                  if element['py family duid'] != fam_duid ]

        # Delete from Ministries
        for id in ministry_type_memberships.keys():
            ministry_type_memberships[id]['membership'][:] = \
                [ element for element in ministry_type_memberships[id]['membership']
                  if element['py family duid'] != fam_duid ]

        # Delete from Members
        for member in family['py members']:
            mem_duid = member['memberDUID']
            # We may have already deleted this member, above
            if mem_duid in members:
                del members[mem_duid]

        # Delete from Families
        del families[fam_duid]

##############################################################################

# Load PS Families and Members.  Return them as 2 giant hashes,
# appropriately cross-linked to each other.
def load_families_and_members(api_key=None,
                              active_only=True, parishioners_only=True,
                              log=None, cache_dir=None):
    if not api_key:
        raise Exception("ERROR: Must specify ParishSoft API key to login to the PS cloud")

    # Setup Python session
    session = _setup_session(api_key)

    # Get the organization ID
    org_id = _get_org(session, cache_dir, log)

    # Load all the Family data
    families = _load_families(session, org_id, cache_dir, log)
    family_groups = _load_family_groups(session, cache_dir, log)
    family_workgroups = _load_family_workgroups(session, cache_dir, log)
    family_workgroup_memberships = \
        _load_family_workgroup_memberships(session, family_workgroups,
                                           cache_dir, log)

    # Load all the Member data
    members = _load_members(session, org_id, cache_dir, log)
    member_statuses = _load_member_statuses(session, api_key, org_id,
                                            cache_dir, log)
    member_types = _load_member_types(session, api_key, org_id,
                                      cache_dir, log)
    member_contactinfos = _load_member_contactinfos(session, org_id,
                                                    cache_dir, log)
    member_workgroups = _load_member_workgroups(session, api_key, org_id,
                                                cache_dir, log)
    member_workgroup_memberships = \
        _load_member_workgroup_memberships(session, member_workgroups,
                                           cache_dir, log)

    # Load all the Ministry data
    ministry_types = _load_ministry_types(session, cache_dir, log)
    ministry_type_memberships = \
        _load_ministry_type_memberships(session, ministry_types,
                                        cache_dir, log)

    # Save everything we downloaded from ParishSoft's API
    _save_all_keyed_caches(log)

    # Cross link the various data
    _link_families_and_members(families, members, log)
    _link_family_groups(families, family_groups, log)
    _link_family_workgroups(families, family_workgroup_memberships, log)
    _link_member_contactinfos(members, member_contactinfos, log)
    _link_member_workgroups(members, member_workgroup_memberships, log)
    _link_member_ministries(members, ministry_type_memberships, log)

    # Once we have linked the member contactinfos, construct the
    # "friendly" name (with the nickname, which is in the contactinfo)
    _make_member_friendly_name(members, log)

    # Filter the data.  We have to do this after everything is cross
    # linked, because we can't filter workgroup or ministry data until
    # we link them to their various families / members.
    _filter(families, members,
            family_workgroup_memberships,
            member_workgroup_memberships,
            ministry_type_memberships,
            active_only, parishioners_only, org_id, log)

    # Return all the data
    return \
        families, \
        members, \
        family_workgroup_memberships, \
        member_workgroup_memberships, \
        ministry_type_memberships

def get_member_public_phones(member):
    phones = list()

    # If they're unlisted, return nothing
    if not member['family_PublishPhone']:
        return phones

    for meta in [{ 'key' : 'mobilePhone', 'type' : 'cell', },
                 { 'key' : 'homePhone',   'type' : 'home', },
                 ]:
        if meta['key'] in member:
            number = member[meta['key']]
            if number is None:
                continue

            phones.append({
                'number' : number,
                'type' : meta['type'],
            })

    return phones

def get_member_private_phones(member):
    # Do something similar to above, but include work phone too
    pass

def get_member_public_email(member):
    # If they're unlisted, return nothing
    if not member['family_PublishEMail']:
        return None

    key = 'emailAddress'
    if key in member:
        return member[key]
    return None
