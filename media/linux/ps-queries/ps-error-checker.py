#!/usr/bin/env python3

# This script is really just for debugging / reference.  It didn't
# play a part in the sending of emails, etc.  It was edited and run on
# demand just as a help for writing / debugging the other scripts.

import os
import sys
import argparse

# We assume that there is a "ecc-python-modules" sym link in this
# directory that points to the directory with ECC.py and friends.
moddir = os.path.join(os.getcwd(), 'ecc-python-modules')
if not os.path.exists(moddir):
    print("ERROR: Could not find the ecc-python-modules directory.")
    print("ERROR: Please make a ecc-python-modules sym link and run again.")
    exit(1)
if os.path.isfile(moddir):
    with open(moddir) as fp:
        dir = fp.readlines()
    moddir = os.path.join(os.getcwd(), dir[0])

sys.path.insert(0, moddir)

import ECC
import ECCEmailer
import ParishSoftv2 as ParishSoft

from pprint import pprint
from pprint import pformat

from datetime import datetime

#HJCTODO: Make pretty
emailhead = '''
<html>
<head>
<style>
    table {
        border-collapse: collapse;}
    th, td {
        text-align: left;
        padding: 8px;
        border-bottom: 1px solid #ddd;}\ntr:nth-child(even) {background-color: #f2f2f2; }</style></head><body>
        '''

##############################################################################

def _family_in_inactive_group(family):
    key = 'py family group'
    if key in family and family[key] == 'Inactive':
        return True
    return False

##############################################################################

#HJCTODO: Create sort function for families, members, workgroups

##############################################################################

def send_families_email(to, subject, families, args, log):
    if len(families) == 0:
        log.debug(f"Found NO matching families - no need to send an email")
        return

    columns = [('familyDUID', 'Family DUID'),
               ('firstName', 'Family First Name'),
               ('lastName', 'Family Last Name')]

    # JMS call the thingy to sort families by last, first

    bodylist = []
    bodylist.append(emailhead)
    bodylist.append('<p>We have identified the following families in ParishSoft that have no members:</p>')
    bodylist.append('<p><table border=0>\n<tr>')
    bodylist.append('<tr>')
    for tuple in columns:
        bodylist.append(f'<th>{tuple[1]}</th>')
    bodylist.append('</tr>')
    for family in families:
        bodylist.append('<tr>')
        for tuple in columns:
            key = tuple[0]
            value = 'None'
            if key in family:
                value = family[key]
            bodylist.append(f"<td>{value}</td>")
        bodylist.append('</tr>')
    bodylist.append('</table></p>')
    bodylist.append('</body>')
    bodylist.append('</html>')

    body = "\n".join(bodylist)
    ECCEmailer.send_email(body, 'html', None,
                          args.smtp_auth_file,
                          to, subject, args.smtp_client,
                          log)

##############################################################################

def check_for_families_without_members(families, log, args):
    key = 'py members'
    results = list()
    for duid, family in families.items():
        if key not in family or len(family[key]) == 0:
            results.append(family)

    send_families_email(to=args.famnomemrecip,
                        subject="Families without members",
                        families=results,
                        args=args,
                        log=log)

##############################################################################

def check_for_active_families_with_inactive_members(families, log, args):
    key = 'py members'
    results = []
    for duid, family in families.items():
        if key not in family:
            continue
        if _family_in_inactive_group(family):
            continue

        all_inactive = True
        for member in family[key]:
            if ParishSoft.member_is_active(member):
                all_inactive = False
                break

        if all_inactive:
            results.append(family)

    # JMS The "to" is wrong
    send_families_email(to=args.famnomemrecip,
                        subject="Families without active members",
                        families=results,
                        args=args,
                        log=log)

##############################################################################

def check_for_inactive_families_with_active_members(families, log, args):
    key = 'py members'
    inactive_families_with_active_members = []
    for duid, family in families.items():
        if key not in family:
            continue
        if not _family_in_inactive_group(family):
            continue

        any_active = False
        for member in family[key]:
            if ParishSoft.member_is_active(member):
                any_active = True
                break

        if any_active:
            inactive_families_with_active_members.append(f'<tr><td>{family["DUID"]}</td><td>{family["lastName"]}</td><td>Make Active in ParishSoft</td></tr>')
            log.error(f'Inactive Family with Active Members: {family["firstName"]} {family["lastName"]} (DUID: {duid})')

    #HJCTODO: Sort list alphabetically by last name, first name

    if len(inactive_families_with_active_members) != 0:
        bodylist = []
        bodylist.append(emailhead)
        bodylist.append('<p>We have identified the following inactive families in ParishSoft that have active members:</p>')

        bodylist.append('<p><table border=0>\n<tr>')
        bodylist.append('<th>Family DUID</th><th>Last Name</th><th>Action</th></tr>')
        for family in inactive_families_with_active_members:
            bodylist.append(family)
        bodylist.append('/table></p>')

        body = "\n".join(bodylist)
        ECCEmailer.send_email(body, 'html', None, args.smtp_auth_file, args.ifamamemrecip, 'ParishSoft Inactive Families with Active Members', args.smtp_client, log)

##############################################################################

def check_for_whitespace_data(members, families, log, args):
    whitespace_data = []
    def _check(name, item):
        for key, value in family.items():
            if type(value) is not str:
                continue

            svalue = value.strip()
            if len(svalue) != len(value):
                description = None
                if value[0] == ' ' and value[-1] == ' ':
                    description = 'both prefix and suffix'
                elif value[0] == ' ':
                    description = 'prefix'
                else:
                    description = 'suffix'

                log.error(f'{name}: field {key} has {description} whitespace')
                whitespace_data.append(f'<tr><td>{name}</td><td>{key}</td><td>{description} whitespace</td><td>Remove Whitespace</td></tr>')

    key = 'py members'
    for duid, family in families.items():
        name = f'Family {family["firstName"]} {family["lastName"]} (DUID: {duid})'
        _check(name, family)

        if key in family:
            for member in family[key]:
                duid = member['memberDUID']
                name = f'Member {member["py friendly name FL"]} (DUID: {duid})'
                _check(name, member)

    if len(whitespace_data) != 0:
        bodylist = []
        bodylist.append(emailhead)
        bodylist.append('<p>We have identified the following DUIDs in ParishSoft that have whitespace in thier fields:</p>')

        bodylist.append('<p><table border=0>\n<tr>')
        bodylist.append('<th>Name</th><th>Key</th><th>Description</th><th>Action</th></tr>')
        for duid in whitespace_data:
            bodylist.append(duid)
        bodylist.append('/table></p>')

        body = "\n".join(bodylist)
        ECCEmailer.send_email(body, 'html', None, args.smtp_auth_file, args.whitespace, 'ParishSoft Families and Members with Whitespace', args.smtp_client, log)

##############################################################################

def check_for_ministries_with_inactive_members(families, members, log, args):
    #HJCTODO: Fill this out
    inactive_members_in_ministries: []

    for duid, member in members.itemms():
        if ParishSoft.member_is_active(member):
            continue
        ministries = []
        for ministry in member['ministries']:
            inactive_members_in_ministries.append(f"<tr><td>{member['py friendly name FL']}</td><td>{ministry}</td><td>Remove from Ministry</td></tr>")

    if len(inactive_members_in_ministries) != 0:
        bodylist = []
        bodylist.append(emailhead)
        bodylist.append('<p>We have identified the following Inactive Members in ParishSoft Minstries:</p>')

        bodylist.append('<p><table border=0>\n<tr>')
        bodylist.append('<th>Name</th><th>Ministry</th><th>Action</th></tr>')
        for line in inactive_members_in_ministries:
            bodylist.append(line)
        bodylist.append('/table></p>')

        body = "\n".join(bodylist)
        ECCEmailer.send_email(body, 'html', None, args.smtp_auth_file, args.whitespace, 'ParishSoft Families and Members with Whitespace', args.smtp_client, log)

    # Sort results by Ministry
    # Have 1 HTML table per ministry
    # Sort the rows in the ministry by Member lastname, firstname
    # Also show the member DUID

##############################################################################

def check_for_member_workgroups_with_inactive_members(member_workgroups, log, args):
    #HJCTODO: Fill this out

    for wg in member_workgroups.items():
        pprint(wg)
        exit(0)

    # Sort results by workgroups
    # Have 1 HTML table per workgroup
    # Sort the rows in the workgroup by Member lastname, firstname
    # Also show the member DUID

##############################################################################

def check_for_family_workgroups_with_inactive_families(family_workgroups, log, args):
    #HJCTODO: Fill this out
    key = "py members"

    for wg in family_workgroups.items():
        pprint(wg)
        exit(0)

    # Sort results by workgroups
    # Have 1 HTML table per workgroup
    # Sort the rows in the workgroup by Family lastname, firstname
    # Also show the family DUID

##############################################################################

def check_for_ministries_with_no_staff_or_chair(ministries, log, args):

    for ministry in ministries.items():
        no_chair = True
        no_staff = True
        for member in ministry:
            pass

    #HJCTODO: Fill this out

    # Sort results by ministry
    # This could be as simple as an <ol>, not necessarily a <table>

##############################################################################

def setup_cli():
    default_client = 'no-reply@epiphanycatholicchurch.org'
    default_email = "harrison@cabral.org"
    parser = argparse.ArgumentParser(description='Do some ParishSoft data consistency checks')

    parser.add_argument('--smtp-auth-file',
                        required=True,
                        help='File containing SMTP AUTH username:password')
    parser.add_argument('--slack-token-filename',
                        help='File containing the Slack bot authorization token')
    parser.add_argument('--ps-api-keyfile',
                        required=True,
                        help='File containing the ParishSoft API key')
    parser.add_argument('--ps-cache-dir',
                        default='.',
                        help='Directory to cache the ParishSoft data')
    parser.add_argument('--debug',
                        action='store_true',
                        default=False,
                        help='If enabled, emit even more extra status messages during run')

    parser.add_argument('--smtp-client',
                        default= default_client,
                        help= 'Email address to be used as sender client')

    # JMS Let's make these CLI options a bit nicer
    parser.add_argument('--famnomemrecip',
                        default= default_email,
                        help= 'Recipient for the Families with No Members email')
    parser.add_argument('--afamimemrecip',
                        default= default_email,
                        help= 'Recipient for the Active Families with Inactive Members email')
    parser.add_argument('--ifamamemrecip',
                        default= default_email,
                        help= 'Recipient for the Inactive Families with Active Members email')
    parser.add_argument('--whitespace',
                        default= default_email,
                        help= 'Recipient for the Whitespace Data email')
    parser.add_argument('--familyworkgrouprecip',
                        default= default_email)
    parser.add_argument('--memberworkgrouprecip',
                        default= default_email)

    args = parser.parse_args()

    # Read the PS API key
    if not os.path.exists(args.ps_api_keyfile):
        print(f"ERROR: ParishSoft API keyfile does not exist: {args.ps_api_keyfile}")
        exit(1)
    with open(args.ps_api_keyfile) as fp:
        args.api_key = fp.read().strip()

    return args

##############################################################################

def main():
    args = setup_cli()
    log = ECC.setup_logging(debug=args.debug)

    log.info("Loading ParishSoft data...")
    families, members, family_workgroups, member_worksgroups, ministries = \
        ParishSoft.load_families_and_members(api_key=args.api_key,
                                             cache_dir=args.ps_cache_dir,
                                             active_only=False,
                                             parishioners_only=False,
                                             log=log)

    check_for_families_without_members(families, log, args)

    check_for_active_families_with_inactive_members(families, log, args)

    # JMS Exit early
    exit(1)

    check_for_inactive_families_with_active_members(families, log, args)

    check_for_whitespace_data(members, families, log, args)

    check_for_ministries_with_inactive_members(families, members, log, args)

    check_for_member_workgroups_with_inactive_members(member_workgroups, log, args)

    check_for_family_workgroups_with_inactive_families(family_workgroups, log, args)

    check_for_ministries_with_no_staff_or_chair(ministries, log, ags)

main()
