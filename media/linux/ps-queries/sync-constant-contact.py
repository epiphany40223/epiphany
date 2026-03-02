#!/usr/bin/env python3

import os
import re
import sys
import csv
import json
import time
import logging
import httplib2
import logging.handlers
import datetime
import requests
import copy

from collections import defaultdict

# We assume that there is a "ecc-python-modules" sym link in this
# directory that points to the directory with ECC.py and friends.
moddir = '../../../python'
if not os.path.exists(moddir):
    print("ERROR: Could not find the ecc-python-modules directory.")
    print("ERROR: Please make a ecc-python-modules sym link and run again.")
    exit(1)
# On MS Windows, git checks out sym links as a file with a single-line
# string containing the name of the file that the sym link points to.
if os.path.isfile(moddir):
    with open(moddir) as fp:
        dir = fp.readlines()
    moddir = os.path.join(os.getcwd(), dir[0])

sys.path.insert(0, moddir)

import ECC
import ParishSoftv2 as ParishSoft
import ConstantContact as CC
from ConstantContact import CCAPIError

from oauth2client import tools

from pprint import pprint
from pprint import pformat

# Globals

args = None
log = None

to_do_key = 'TO-DO ACTIONS'

####################################################################
####################################################################
####################################################################
####################################################################

# JMS Debug: delete me
def jms_sanity(cc_contacts, log):
    # JMS SANITY CHECK
    found_robbie = False
    found_denise = False
    for contact in cc_contacts:
        if contact['email_address']['address'] == 'djerome@mymestory.com':
            found_denise = True
        elif contact['email_address']['address'] == 'robbie@1stoppg.com':
            found_robbie = True

    # Totally weird. :-(
    # When we create Denise, Robbie disappears in the next run.
    # When we create Robbie, Denise disappears in the next run.
    log.debug(f"JMS Sanity: found Denise: {found_denise}, found Robbie: {found_robbie}")

####################################################################
####################################################################
####################################################################
####################################################################

def get_synchronizations(cc_contacts, cc_lists, ps_member_workgroups,
                         ps_members, ps_families, log):
    ecc = '@epiphanycatholicchurch.org'

    synchronizations = [
        {
            'source ps member wg' : 'Daily Gospel Reflections',
            'target cc list'      : 'SYNC Daily Gospel Reflections',
            'notifications'       : [ f'ps-constantcontact-sync{ecc},director-communications{ecc}', ],
        },
        {
            'source ps member wg' : 'Parish-wide Email',
            'target cc list'      : 'SYNC Parish-wide Email',
            'notifications'       : [ f'ps-constantcontact-sync{ecc},director-communications{ecc}', ],
        },
    ]
    # JMS Ready to delete, other than keeping this as an example of a
    # function-based source of PS Members
    jms_bogus = [
        {
            'source function'     : frtoan_letter_members_fn,
            'target cc list'      : 'SYNC Fr. Toan initial letter',
            'notifications'       : [ f'ps-constantcontact-sync{ecc}', ],
        },
    ]

    #----------------------
    # Resolve the sources into lists of PS Members and the targets
    # into CC lists

    def _resolve_ps_member_workgroup(sync):
        key = 'source ps member wg'
        if key not in sync:
            return

        key2 = 'py member duid'

        source_wg_name = sync[key]
        for wg in ps_member_workgroups.values():
            if wg['name'] == source_wg_name:
                members = dict()
                for item in wg['membership']:
                    if key2 not in item:
                        continue

                    duid = item[key2]
                    member = ps_members[duid]
                    if member['emailAddress']:
                        email = member['py emailAddresses'][0]
                        members[email] = member
                    else:
                        log.error(f"PS Member {member['py friendly name FL']} (DUID: {member['memberDUID']}) is in WG {source_wg_name}, but has no PS email address")

                log.info(f'Found: PS Member Workgroup named "{source_wg_name}" with {len(members)} PS Members')

                sync['SOURCE PS MEMBERS'] = members
                return

        # If we got here, we didn't find it
        log.error('Did not find a ParishSoft Member Workgroup named "{source_wg_name}"')
        log.error("Aborting in despair")
        exit(1)

    def _resolve_python_function(sync):
        key = 'source function'
        if key not in sync:
            return

        members = sync['source function'](cc_contacts, cc_lists,
                                          ps_member_workgroups,
                                          ps_members, ps_families,
                                          log)
        log.info(f"Invoked Python function for source PS members, got {len(members)} PS Members")
        sync['SOURCE PS MEMBERS'] = members

    def _resolve_cc_list(sync):
        key = 'target cc list'
        if key not in sync:
            log.error("Did not find \"{key}\" in synchronization")
            log.error(pformat(sync, depth=3))
            log.error("Aborting in despair")
            exit(1)

        found = False
        for l in cc_lists:
            if l['name'] == sync[key]:
                log.info(f'Found: CC list named "{sync[key]}"')
                sync[f'TARGET CC LIST'] = l
                found = True
                break

        if not found:
            log.error('Did not find a Constant Conact List named "{sync[key]}"')
            log.error("Aborting in despair")
            exit(1)

    #----------------------

    for sync in synchronizations:
        log.debug(f'Resolving synchronization: {sync}')
        _resolve_ps_member_workgroup(sync)
        _resolve_python_function(sync)
        _resolve_cc_list(sync)

    return synchronizations

####################################################################

# Just for Fr. Toan's letter
def frtoan_letter_members_fn(cc_contacts, cc_lists,
                             member_workgroups, members, families, log):
    log.debug("IN FR TOAN LETTER MEMBER FN")

    # Make a cross-reference list of CC contacts by email
    key = 'PS MEMBERS'
    key2 = 'py emailAddresses'
    contacts_by_email = dict()

    for contact in cc_contacts:
        if key not in contact:
            continue
        for member in contact[key]:
            if key2 not in member:
                continue
            email = member[key2][0]
            contacts_by_email[email] = contact

    key = 'py emailAddresses'
    send_email_members = dict()
    no_email_families = list()

    for family in families.values():
        # This catches both inactive families and families where all
        # members are deceased.
        if not ParishSoft.family_is_active(family):
            continue
        if family['sendNoMail']:
            continue

        found_member = False
        for member in family['py members']:
            if key not in member:
                continue
            if not member[key]:
                continue
            if not ParishSoft.member_is_active(member):
                continue

            happy = True
            email = member[key][0]
            if email in contacts_by_email:
                if contacts_by_email[email]['email_address']['permission_to_send'] == 'unsubscribed':
                    happy = False

            if happy:
                send_email_members[email] = member
                found_member = True

        if not found_member:
            no_email_families.append(family)

    log.info(f"Found {len(send_email_members)} Member emails we can send Fr. Toan's letter")

    send_usps_families = dict()
    for family in no_email_families:
        # We already know it's an active Family with at least 1 alive
        # Member, and didn't meet the email criteria

        if family['sendNoMail']:
            continue
        if family['primaryAddress1'] and family['primaryCity'] and \
           family['primaryPostalCode'] and family['primaryState']:
            send_usps_families[family['familyDUID']] = family

    log.debug(f"Found {len(send_usps_families)} Families to send USPS mail for Fr. Toan's letter")

    #---------------------------------

    def _write_usps(filename, families):
        fields = ['Family name',
                  'Family DUID',
                  'Street address 1',
                  'Street address 2',
                  'Street address 3',
                  'City', 'State', 'Zip']

        with open(filename, 'w') as fp:
            writer = csv.DictWriter(fp, fieldnames = fields)
            writer.writeheader()

            for duid, family in families.items():
                zip = family['primaryPostalCode']
                if family['primaryZipPlus']:
                    zip += '-' + family['primaryZipPlus']

                item = {
                    'Family name' : f'{family["firstName"]} {family["lastName"]}',
                    'Family DUID' : duid,
                    'Street address 1' : family['primaryAddress1'],
                    'Street address 2' : family['primaryAddress2'],
                    'Street address 3' : family['primaryAddress3'],
                    'City' : family['primaryCity'],
                    'State' : family['primaryState'],
                    'Zip' : zip
                }
                writer.writerow(item)
            log.info(f"Wrote {filename}")

    #---------------------------------

    _write_usps('fr-toan-letter-usps-addresses.csv',
                send_usps_families)

    #---------------------------------

    # Make a list of all Inactive Families where at least one Member
    # is alive
    inactive_families = dict()
    for duid, family in families.items():
        # This catches both inactive families and families where all
        # members are deceased.
        if ParishSoft.family_is_active(family):
            continue

        # So we have to check to make sure there's at least one Member
        # who is not deceased
        keep = False
        for member in family['py members']:
            if member['memberStatus'] != 'Deceased':
                keep = True
        if not keep:
            continue

        if family['sendNoMail']:
            continue
        if family['primaryAddress1'] and family['primaryCity'] and \
           family['primaryPostalCode'] and family['primaryState']:
            inactive_families[duid] = family

    _write_usps('fr-toan-letter-inactive-usps-addresses.csv',
                inactive_families)

    return send_email_members

#-------------------------------------------------

# Just for Fr. Toan's letter
def report_csv(contacts, log):
    filename = 'cc-contacts-raw-data.csv'
    fields = ['Email address', 'First name', 'Last name',
              'Matched to PDS Member', 'Active PDS Member', 'PDS envelope ID',
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
            active_pds_member = ''
            pds_env_id = ''
            if 'pds_mid' in contact:
                matched = 'Yes'
                member = contact['pds_member']
                if member['Inactive']:
                    active_pds_member = 'No'
                else:
                    active_pds_member = 'Yes'
                key = 'family'
                if key in member:
                    pds_env_id = "' " + member[key]['ParKey'].strip()

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
                'Matched to PDS Member' : matched,
                'Active PDS Member' : active_pds_member,
                'PDS envelope ID' : pds_env_id,
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

# Make a friendly name string from a CC contact structure
def cc_contact_name_string(contact, log):
    name = ''

    key = 'PS MEMBERS'
    if key in contact:
        names = list()
        for member in contact[key]:
            n = f"{member['py friendly name FL']} (DUID: {member['memberDUID']})"
        name = ', '.join(names)

    # If we didn't find a ParishSoft name + DUID, use the CC name + CC
    # PS DUID entry
    if len(name) == 0:
        key = 'first_name'
        if key in contact:
            name += contact[key]

        key = 'last_name'
        if key in contact:
            name += ' ' + contact[key]

        key = 'CUSTOM FIELDS'
        if key in contact:
            for item, value in contact[key].items():
                if item == 'ps_member_duids':
                    name += f' (DUID: {value["value"]})'
                    break

    name = name.strip()
    return name

####################################################################

def update_contacts_from_ps_members(contacts, notify_emails, log):
    log.info("Looking for CC Contacts that need to be updated from PS Member data...")

    # JMS WE ARE NOT CURRENTLY UPDATING NAMES FROM PARISHSOFT
    return


    key = 'PS MEMBERS'
    for contact in contacts:
        # We only care about Contacts with PS Members
        if key not in contact:
            continue

        email = contact['email_address']['address']
        ps_first, ps_last = \
            ParishSoft.salutation_for_members(contact[key])

        # Apparently, CC doesn't like first names with periods in them (!!)
        # E.g., "K.C." will fail to be set at CC.
        ps_first = ps_first.replace('.', '').strip()
        if contact['first_name'] != ps_first:
            old = contact['first_name']
            contact['first_name'] = ps_first
            name = cc_contact_name_string(contact, log)
            s = f"Update contact {name} {email} first name: {old} --> {ps_first}"
            log.debug(s)
            contact[to_do_key]['notifications'].append({
                'description' : s,
                'emails' : notify_emails,
            })
            contact[to_do_key]['update'] = True

        if contact['last_name'] != ps_last:
            old = contact['last_name']
            contact['last_name'] = ps_last
            name = cc_contact_name_string(contact, log)
            s = f"Update contact {name} {email} last name: {old} --> {ps_last}"
            log.debug(s)
            contact[to_do_key]['notifications'].append({
                'description' : s,
                'emails' : notify_emails,
            })
            contact[to_do_key]['update'] = True

####################################################################

def remove_cc_contacts_with_no_ps_members(cc_contacts, members,
                                          notify_emails, log):
    log.info("Sanity checking PS Member DUIDs on CC Contacts...")

    key = 'PS MEMBERS'
    for contact in cc_contacts:
        if key not in contact or len(contact[key]) == 0:
            name = cc_contact_name_string(contact, log)
            s = f'No PS Members left on contact {name} {contact["email_address"]["address"]}" -- marked for deletion'
            log.debug(s)

            # JMS UNCOMMENT ME WHEN WE START DELETING
            #contact[to_do_key]['notifications'].append({
            #    'description' : s,
            #    'emails' : notify_emails,
            #})
            #contact[to_do_key]['delete'] = True

####################################################################

def remove_unsubscribed_contacts(cc_contacts, synchronizations, log):
    log.info("Removing CC-unsubscribed contacts from PS data")

    # On the contact
    key1 = 'PS MEMBERS'
    # On the sync
    key2 = 'SOURCE PS MEMBERS'
    key3 = 'py emailAddresses'
    for contact in cc_contacts:
        if contact['email_address']['permission_to_send'] != 'unsubscribed':
            continue

        # This person unsubscribed via CC; remove them from synchronizations

        if key1 not in contact:
            # If this contact doesn't have any PS Members, then by
            # definition, they are not in any PS data structures (such
            # as Member Workgroups).  This shouldn't happen: all CC
            # contacts should have PS Members, but we might as well do
            # some defensive programming here.
            continue

        if len(contact[key1]) == 0:
            continue

        email = contact['email_address']['address']
        log.info(f'Deleting CC unsubscribed {email} from all synchronizations')
        for sync in synchronizations:
            for member in contact[key1]:
                if key3 not in member:
                    continue
                member_email = member[key3][0]
                if member_email in sync[key2]:
                    m = sync[key2][member_email]
                    log.debug(f'Deleting CC unsubscribed PS Member {m["py friendly name FL"]} <{member_email}> from synchronization {sync["target cc list"]}')
                    del sync[key2][member_email]

####################################################################

def get_union_of_ps_members(synchronizations, log):
    log.info("Computing the union of all source PS members from synchronizations")

    union = dict()
    for sync in synchronizations:
        log.debug(f"- getting PS members for CC list {sync['target cc list']}")
        for member in sync['SOURCE PS MEMBERS'].values():
            if member['emailAddress']:
                email = member['py emailAddresses'][0]
                union[email] = member

    log.debug(f"Found a total of {len(union)} PS Members for which we need contacts")
    return union

####################################################################

def create_missing_contacts(cc_contacts, needed_ps_members, log):
    log.info("Finding PS members for which we need to create a CC contact")

    # Make a quick lookup list of emails for which we have contacts
    contact_emails = dict()
    for contact in cc_contacts:
        email = contact['email_address']['address']
        contact_emails[email] = True

    # Find all Members for which we do not have a contact.
    #
    # Assemble the information first (before actually making CC API
    # calls to make the contacts) because we have to scan all the PS
    # members first to discover all the DUIDs for a given contact.
    contacts_to_create = dict()
    for email, member in needed_ps_members.items():
        if email not in contact_emails:
            # This is a PS member that does not have a corresponding
            # CC contact
            if email not in contacts_to_create:
                contacts_to_create[email] = {
                    'email' : email,
                    'ps members' : list(),
                }
            contacts_to_create[email]['ps members'].append(member)

    # Now that we have all the information, create the corresponding
    # CC contacts locally in memory
    log.debug(f"Create CC contact for {len(contacts_to_create)} email addresses")
    for email, data in contacts_to_create.items():
        log.info(f"Creating contact data structure for {email}")
        contact = CC.create_contact_dict(email,
                                         data['ps members'],
                                         log)
        contact[to_do_key] = {
            'create' : True,
            'notifications' : list(),
        }
        cc_contacts.append(contact)

####################################################################

def compute_sync(synchronizations, contacts, log):
    log.info("Resolving PS Members from synchronizations to CC contacts")

    # The SOURCE PS MEMBERS represents the set of PS members that we
    # want in this CC list.  The TARGET CC LIST represents the list of
    # contacts that are already in the list.
    #
    # We need to compute the difference between the two, keeping in
    # mind that there may be multiple PS Members that map to a single
    # CC contact.

    key1 = 'SOURCE PS MEMBERS'
    key2 = 'TARGET CC LIST'
    for sync in synchronizations:
        for key in [key1, key2]:
            if key not in sync:
                log.error("Did not find {key} in synchronization \"{sync['target cc list']}\"")
                log.error("Aborting in despair")
                exit(1)

        # UUID of this list
        list_uuid = sync[key2]['list_id']
        list_name = sync['target cc list']

        sync_name = sync['target cc list']

        # First, find PS Members who are not in the CC list
        for member_email, member in sync[key1].items():
            if member_email not in sync[key2]['CONTACTS']:
                # Need to add this list UUID to the contact
                # corresponding to the PS member
                contact = member['CONTACT']
                name = cc_contact_name_string(contact, log)
                s = f"Add {name} {member_email} to {list_name}"
                log.debug(s)
                log.debug(f"Adding UUID: {list_uuid}")
                log.debug(f"to list: {contact['list_memberships']}")

                contact['list_memberships'].append(list_uuid)
                contact['LIST MEMBERSHIPS'].append(list_name)

                contact[to_do_key]['notifications'].append({
                    'description' : s,
                    'emails' : sync['notifications'],
                })
                contact[to_do_key]['update'] = True

        # Now find CC contacts who are not PS Members
        for contact_email, contact in sync[key2]['CONTACTS'].items():
            if contact_email not in sync[key1]:
                # Need to remove this list UUID from the contact
                # corresponding to this email
                name = cc_contact_name_string(contact, log)
                s = f"Remove {name} {contact_email} from {list_name}"
                log.debug(s)
                log.debug(f"Removing UUID: {list_uuid}")
                log.debug(f"from list: {contact['list_memberships']}")

                contact['list_memberships'].remove(list_uuid)
                contact['LIST MEMBERSHIPS'].remove(list_name)

                contact[to_do_key]['notifications'].append({
                    'description' : s,
                    'emails' : sync['notifications'],
                })
                contact[to_do_key]['update unsub'] = True

####################################################################

def delete_contacts_with_no_lists(cc_contacts, notify_emails, log):
    for contact in cc_contacts:
        if len(contact['list_memberships']) == 0:
            email = contact['email_address']['address']
            name = cc_contact_name_string(contact, log)
            s = f'Contact {name} {email} no longer on any lists; marking for deletion'
            log.debug(s)

            # JMS UNCOMMENT ME WHEN WE START DELETING
            #contact[to_do_key]['notifications'].append({
            #    'description' : s,
            #    'emails' : notify_emails,
            #})
            #contact[to_do_key]['delete'] = True

####################################################################

def perform_cc_actions(cc_contacts, client_id, access_token,
                       notify_emails, log):
    keys = {}
    for contact in cc_contacts:
        for key in contact[to_do_key]:
            if key not in keys:
                keys[key] = 0
            keys[key] += 1
    log.debug("Counts of CC actions to perform:")
    log.debug(pformat(keys))

    emails_to_send = defaultdict(list)

    for contact in cc_contacts:
        cc_email = contact['email_address']['address']

        if len(contact[to_do_key]) == 0:
            continue

        to_do = contact[to_do_key]
        for notify in to_do['notifications']:

            # Add this to the list of things we need to email.  An
            # email gets sent to each address that should be notified
            # of this action.
            description = notify['description']
            log.info(description)

            for email in notify['emails']:
                emails_to_send[email].append(description)

            # Check for deleting first: if we're deleting a contact,
            # that trumps all other actions (i.e., we never need to
            # create/update/unsubscribe a contact if we're just going
            # to delete it).
            if 'delete' in to_do:




                # JMS We're not deleting any contacts yet
                # JMS WRITE ME
                log.debug(f"CC action: delete {cc_email}: {contact[to_do_key]}")




            else:
                # If we're not deleting, handle multiple actions

                if 'create' in to_do or 'update' in to_do:
                    # We need to update this contact at CC
                    log.info(f"CC action: create or update: {contact[to_do_key]['notifications']}")
                    try:
                        CC.create_or_update_contact(contact, client_id, access_token, log)
                    except CCAPIError as e:
                        log.error(f"Failed to create/update contact: {e}")
                        exit(1)

                if 'update unsub' in to_do:
                    # The CC.create_contact() function will update a
                    # bunch of things, but it can only *add* lists to
                    # which a contact is subscribed.  If the contact
                    # needs to be removed from lists, we have to make
                    # a second call.  This isn't necessarily
                    # super-efficient -- we could probably add more
                    # clever logic here to combine these two into a
                    # single call... but there's no real need to.  So
                    # let's just have (more or less) clear code.
                    #
                    # NOTE: This will only ever happen to contacts
                    # that already existed at CC.  Contacts that were
                    # just created at CC won't fall down into this
                    # block.
                    log.info(f"CC action: update unsub: {contact[to_do_key]['notifications']}")
                    try:
                        CC.update_contact_full(contact, client_id, access_token, log)
                    except CCAPIError as e:
                        log.error(f"Failed to update contact (unsub): {e}")
                        exit(1)

    # If we did something, send an email about it
    subject = 'Constant Contact synchronization from ParishSoft update'
    for email, descriptions in emails_to_send.items():
        body = """The following changes happened in Constant Contact:

<p><ol>
"""
        for description in descriptions:
            body += f'<li>{description}</li>\n'
        body += '</ol>\n\nYour friendly daemon,<br />\nClarence'

        ECC.send_email(to_addr=email,
                       subject=subject, body=body,
                       content_type='text/html', log=log)

####################################################################

def setup_cli_args():
    tools.argparser.add_argument('--cc-auth-only',
                                default=False,
                                action='store_true',
                                help='Only authorizes to Constant Contact, does not do any work')

    tools.argparser.add_argument('--ps-api-keyfile',
                                 required=True,
                                 help='File containing the ParishSoft API key')

    tools.argparser.add_argument('--ps-cache-dir',
                                 default='datacache',
                                 help='Directory to cache the ParishSoft data')

    tools.argparser.add_argument('--cc-client-id',
                                default='constant-contact-client-id.json',
                                help="File containing the Constant Contact Client ID")

    tools.argparser.add_argument('--cc-access-token',
                                default='constant-contact-access-token.json',
                                help='File containing the Constant Contact access token')

    tools.argparser.add_argument('--notify-email',
                                 required=True,
                                 help='Email address for general CC updates')
    tools.argparser.add_argument('--service-account-json',
                                 default='ecc-emailer-service-account.json',
                                 help='File containing the Google service account JSON key')
    tools.argparser.add_argument('--impersonated-user',
                                 default='no-reply@epiphanycatholicchurch.org',
                                 help='Google Workspace user to impersonate via DWD')

    tools.argparser.add_argument('--dry-run',
                                 action='store_true',
                                 help='Do not actually update the Google Group; just show what would have been done')

    tools.argparser.add_argument('--verbose',
                                 action='store_true',
                                 default=True,
                                 help='If enabled, emit extra status messages during run')

    tools.argparser.add_argument('--debug',
                                 action='store_true',
                                 default=False,
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

####################################################################

# JMS Extra work
def jms_extra(cc_contacts, cc_lists, members, member_workgroups, families, log):
    results = []

    dgr_list = None
    dgr_id = None
    sdgr_list = None
    sdgr_id = None

    # Find both CC lists
    for list in cc_lists:
        if list['name'] == 'Daily Gospel Reflections':
            dgr_list = list
            dgr_id = list['list_id']
        elif list['name'] == 'SYNC Daily Gospel Reflections':
            sdgr_list = list
            sdgr_id = list['list_id']

    # Find PS DGR workgroup
    ps_dgr_wg = None
    for wg_id, wg in member_workgroups.items():
        if wg['name'] == 'Daily Gospel Reflections':
            ps_dgr_wg = wg
            break
    if ps_dgr_wg is None:
        print("ERROR: Could not find PS DGR WG")
        exit(1)

    # For each CC DGR contact
    # 1. Add them to all_emails
    # 2. Make a list of PS DUIDs corresponding to PS Members
    key = 'PS MEMBERS'
    all_emails = {}
    for email, contact in dgr_list['CONTACTS'].items():
        email = email.lower().strip()
        all_emails[email] = {
            'duids' : [],
        }
        all_emails[email]['dgr contact'] = contact

        if key in contact:
            for member in contact[key]:
                all_emails[email]['duids'].append(str(member['memberDUID']))

    # Do the same thing for the CC SYNC DGR list
    for email, contact in sdgr_list['CONTACTS'].items():
        email = email.lower().strip()
        if email not in all_emails:
            all_emails[email] = {
                'duids' : [],
            }
        all_emails[email]['sdgr contact'] = contact

        if key in contact:
            for member in contact[key]:
                all_emails[email]['duids'].append(str(member['memberDUID']))

    # For each PS DGR WorkGroup member:
    # 1. Add them to all_emails
    # 2. Add their email address to a list
    ps_dgr_wg_emails = []
    for entry in ps_dgr_wg['membership']:
        email = entry['emailAddress']
        if email:
            email = email.lower().strip()
            ps_dgr_wg_emails.append(email)
            if email not in all_emails:
                all_emails[email] = {
                    'duids' : [],
                }
            all_emails[email]['wg entry'] = entry

            duid = str(entry['py member duid'])
            if duid not in all_emails[email]['duids']:
                all_emails[email]['duids'].append(duid)

    fields = ['First name', 'Last name', 'Email', 'In CC DGR',
              'In CC SYNC DGR', 'In PS DGR WG', 'PS Active', 'PS DUID']
    filename = 'daily-gospel-reflections-cc-contact-analysis.csv'
    with open(filename, "w") as fp:
        writer = csv.DictWriter(fp, fieldnames=fields)
        writer.writeheader()

        for email, data in all_emails.items():
            contact = None
            in_cc_dgr = False
            if 'dgr contact' in data:
                in_cc_dgr = True
                contact = data['dgr contact']

            in_cc_sdgr = False
            if 'sdgr contact' in data:
                in_cc_sdgr = True
                # Contact is the same between dgr and sdgr; doesn't
                # matter if we overwrite it
                contact = data['sdgr contact']

            wg_entry = None
            in_ps_sdgr_wg = False
            if 'wg entry' in data:
                in_ps_sdgr_wg = True
                wg_entry = data['wg entry']

            ps_member_active = ''
            ps_duid = ', '.join(data['duids'])
            for duid_str in data['duids']:
                duid = int(duid_str)
                member = members[duid]
                ps_member_active = True
                if not ParishSoft.member_is_active(member):
                    ps_member_active = False
                elif not ParishSoft.family_is_active(member['py family']):
                    ps_member_active = False

            first = ''
            if contact and 'first_name' in contact:
                first = contact['first_name']
            elif wg_entry:
                first = wg_entry['firstName']

            last = ''
            if contact and 'last_name' in contact:
                last = contact['last_name']
            elif wg_entry:
                last = wg_entry['lastName']
            if contact:
                log.debug(pformat(contact, depth=2))

            item = {
                'First name' : first,
                'Last name' : last,
                'Email' : email,
                'In CC DGR' : in_cc_dgr,
                'In CC SYNC DGR' : in_cc_sdgr,
                'In PS DGR WG' : in_ps_sdgr_wg,
                'PS Active' : ps_member_active,
                'PS DUID' : ps_duid,
            }
            writer.writerow(item)

    log.info(f"Wrote {filename}")

####################################################################

def main():
    args = setup_cli_args()

    log = ECC.setup_logging(info=args.verbose,
                            debug=args.debug,
                            logfile=args.logfile, rotate = True,
                            slack_token_filename=None)
    ECC.setup_email(service_account_json=args.service_account_json,
                   impersonated_user=args.impersonated_user,
                   log=log)

    log.info("Loading ParishSoft info...")
    families, members, family_workgroups, member_workgroups, ministries = \
        ParishSoft.load_families_and_members(api_key=args.api_key,
                                             active_only=True,
                                             parishioners_only=False,
                                             cache_dir=args.ps_cache_dir,
                                             log=log)

    # Read Constant Contact client ID and token files
    log.info("Loading Constant Contact data...")
    cc_client_id  = CC.load_client_id(args.cc_client_id, log)
    cc_access_token = CC.get_access_token(args.cc_access_token, cc_client_id, log)

    if args.cc_auth_only:
        log.info("Only authorizing to Constant Contact; exiting")
        exit(0)

    # Download all data from Constant Contact
    try:
        cc_contact_custom_fields = \
            CC.api_get_all(cc_client_id, cc_access_token,
                           'contact_custom_fields', 'custom_fields',
                           log)
    except CCAPIError as e:
        log.error(f"Failed to download CC contact custom fields: {e}")
        exit(1)
    log.debug("Downloaded CC contact custom fields")
    log.debug(pformat(cc_contact_custom_fields))

    try:
        cc_lists = \
            CC.api_get_all(cc_client_id, cc_access_token,
                           'contact_lists', 'lists',
                           log)
    except CCAPIError as e:
        log.error(f"Failed to download CC lists: {e}")
        exit(1)
    log.debug("Downloaded CC lists")
    log.debug(pformat(cc_lists))

    try:
        cc_contacts = \
            CC.api_get_all(cc_client_id, cc_access_token,
                           'contacts', 'contacts',
                           log,
                           include='custom_fields,list_memberships,street_addresses',
                           # Get all contacts -- even those who have been
                           # deleted.
                           status='all')
    except CCAPIError as e:
        log.error(f"Failed to download CC contacts: {e}")
        exit(1)
    log.debug(f"Downloaded {len(cc_contacts)} CC contacts")
    log.debug(pformat(cc_contacts))

    #jms_sanity(cc_contacts, log)

    #----------------------------------------

    # We have all the CC contacts.  Preprocess the data a little
    # before using it.

    for contact in cc_contacts:
        # Make each contact email addresses be lower case
        contact['email_address']['address'] = \
            contact['email_address']['address'].lower()

        # Make an empty list of actions to be performed for each
        # contact
        contact[to_do_key] = { 'notifications' : list() }

    # Link various Constant Contact data structures together
    CC.link_cc_data(cc_contacts, cc_contact_custom_fields,
                    cc_lists, log)

    #jms_sanity(cc_contacts, log)

    # JMS Extra work
    #jms_extra(cc_contacts, cc_lists, members, member_workgroups, families, log)

    #----------------------------------------

    # Link Constant Contact Contacts to ParishSoft Members by the
    # ps_member_duids field
    log.info("Linking CC Contacts to PS Members...")
    CC.link_contacts_to_ps_members(cc_contacts, members, log)
    #jms_sanity(cc_contacts, log)

    # Find CC members that need updates from PS Member data
    notify_emails = [ x.strip() for x in args.notify_email.split(',') ]
    update_contacts_from_ps_members(cc_contacts,
                                    notify_emails, log)
    #jms_sanity(cc_contacts, log)

    # Check for contacts with no PS Members
    remove_cc_contacts_with_no_ps_members(cc_contacts, members,
                                          notify_emails, log)
    #jms_sanity(cc_contacts, log)

    # Get the synchronizations we're supposed to do
    synchronizations = get_synchronizations(cc_contacts, cc_lists,
                                            member_workgroups,
                                            members, families, log)
    #jms_sanity(cc_contacts, log)

    # Remove PS Members from synchronizations who explicitly
    # unsubscribed
    remove_unsubscribed_contacts(cc_contacts, synchronizations, log)
    #jms_sanity(cc_contacts, log)

    # Get the union of all source PS members from the synchronizations
    all_sync_ps_members = get_union_of_ps_members(synchronizations, log)
    #jms_sanity(cc_contacts, log)

    # Find members that do not have corresponding contacts
    # and make any CC Contacts that are needed that do not yet exist
    create_missing_contacts(cc_contacts, all_sync_ps_members, log)
    #jms_sanity(cc_contacts, log)

    # Now we have contacts (in memory) for every list we need to
    # synchronize.  Resolve all the synchronization PS members to
    # CC contacts.
    compute_sync(synchronizations, cc_contacts, log)
    #jms_sanity(cc_contacts, log)

    # For any Contacts who are no longer subscribed to any CC lists,
    # mark them to be deleted.
    delete_contacts_with_no_lists(cc_contacts,
                                  notify_emails, log)
    #jms_sanity(cc_contacts, log)

    # We've figured out all the actions we need to take at CC.  Now do
    # all those actions.
    perform_cc_actions(cc_contacts, cc_client_id, cc_access_token,
                       notify_emails, log)
    #jms_sanity(cc_contacts, log)

    # JMS Should also send an email to someone notifying them of the
    # actions we performed.

if __name__ == '__main__':
    main()
