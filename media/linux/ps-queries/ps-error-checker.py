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

def send_families_email(to, subject, description, families, args, log):

    if len(families) == 0:
        log.debug(f"Found NO matching families - no need to send an email")
        return

    columns = [('familyDUID', 'Family DUID'),
               ('firstName', 'Family First Name'),
               ('lastName', 'Family Last Name')]

    families = sorted(families, key=lambda family: (family["lastName"], family["firstName"]))

    bodylist = []
    bodylist.append(emailhead)
    bodylist.append(f'<p>{description}</p>')
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

def send_groups_email(to, subject, columns, description, items, args, log, group_column = None):

    bodylist = []
    bodylist.append(emailhead)
    bodylist.append(f'<p>{description}</p>')
    bodylist.append('<p><table border=0>\n<tr>')
    bodylist.append('<tr>')
    for tuple in columns:
        bodylist.append(f'<th>{tuple[1]}</th>')
    bodylist.append('</tr>')

    #HJCTODO: Add newlines between groups
    prev_value = None
    for item in items:
        bodylist.append('<tr>')
        for tuple in columns:
            key = tuple[0]
            value = 'None'
            if key in item:
                value = item[key]
            if key == group_column:
                if prev_value != None and value != prev_value:
                    bodylist.append('<td><br /> </td></tr><tr>')
                    prev_value = value
                else:
                    prev_value = value
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
    log.debug('Checking for Families without Members')
    key = 'py members'
    results = list()
    for duid, family in families.items():
        if key not in family or len(family[key]) == 0:
            results.append(family)

    log.debug(f'Found {len(results)} results')

    send_families_email(to=args.famnomemrecip,
                        subject="Families without members",
                        description="We have identified the following families in ParishSoft that have no members:",
                        families=results,
                        args=args,
                        log=log)

##############################################################################

def check_for_active_families_with_inactive_members(families, log, args):
    log.debug('Checking for Active Families with Inactive Members')
    key = 'py members'
    results = []
    for duid, family in families.items():
        if key not in family:
            continue
        if not ParishSoft.family_is_active(family):
            continue

        all_inactive = True
        for member in family[key]:
            if ParishSoft.member_is_active(member):
                all_inactive = False
                break

        if all_inactive:
            results.append(family)

    log.debug(f'Found {len(results)} results')

    send_families_email(to=args.afamimemrecip,
                        subject="Families without active members",
                        description="We have identified the following families in ParishSoft that have no active members:",
                        families=results,
                        args=args,
                        log=log)

##############################################################################

def check_for_inactive_families_with_active_members(families, log, args):
    log.debug('Checking for Inactive Families with Active Members')
    key = 'py members'
    results = []
    for duid, family in families.items():
        if key not in family:
            continue
        if ParishSoft.family_is_active(family):
            continue

        any_active = False
        for member in family[key]:
            if ParishSoft.member_is_active(member):
                any_active = True
                break

        if any_active:
            results.append(family)

    log.debug(f'Found {len(results)} results')

    send_families_email(to=args.ifamamemrecip,
                        subject="Inactive families with active members",
                        description="We have identified the following inactive families in ParishSoft that have active members:",
                        families=results,
                        args=args,
                        log=log)

##############################################################################

def check_for_whitespace_data(members, families, log, args):
    log.debug('Checking for Members or Families with Whitespace in their field names')
    whitespace_data = []
    def _check(category, name, item):
        for key, value in item.items():
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
                whitespace_data.append(f'<tr><td>{category}</td><td>{name}</td><td>{key}</td><td>{description} whitespace</td><td>Remove Whitespace</td></tr>')

    key = 'py members'
    for duid, family in families.items():
        name = f'{family["firstName"]} {family["lastName"]} (DUID: {duid})'
        _check("Family", name, family)

        if key in family:
            for member in family[key]:
                duid = member['memberDUID']
                name = f'{member["py friendly name FL"]} (DUID: {duid})'
                _check("Member", name, member)

    log.debug(f'Found {len(whitespace_data)} results')

    if len(whitespace_data) != 0:
        bodylist = []
        bodylist.append(emailhead)
        bodylist.append('<p>We have identified the following DUIDs in ParishSoft that have whitespace in thier fields:</p>')

        bodylist.append('<p><table border=0>\n<tr>')
        bodylist.append('<th>Type</th><th>Name</th><th>Key</th><th>Description</th><th>Action</th></tr>')
        for duid in whitespace_data:
            bodylist.append(duid)
        bodylist.append('</table></p>')
        bodylist.append('</body></html>')

        body = "\n".join(bodylist)
        ECCEmailer.send_email(body, 'html', None, args.smtp_auth_file, args.whitespace, 'ParishSoft Families and Members with Whitespace', args.smtp_client, log)
    else:
        log.debug('Found NO matching members or families - no need to send an email')

##############################################################################

def check_for_ministries_with_inactive_members(families, members, log, args):
    log.debug('Checking for Ministries with Inactive Members')
    results = []

    for duid, member in members.items():
        if ParishSoft.member_is_active(member):
            continue
        for name, ministry in member['py ministries'].items():
            results.append({'ministryName': ministry['name'], 
                           'memberDUID': member['memberDUID'],
                           'lastName': member['lastName'],
                           'firstName': member['firstName']}),

    columns = [('ministryName', 'Ministry Name'),
               ('memberDUID', 'Member DUID'),
               ('lastName', 'Member Last Name'),
               ('firstName', 'Member First Name')]

    log.debug(f'Found {len(results)} results')

    if len(results) == 0:
        log.debug(f"Found NO matching groups - no need to send an email")
    else:
        results = sorted(results, key=lambda item: (item["ministryName"], item["lastName"], item["firstName"]))
        send_groups_email(to=args.ministryrecip,
                          subject="Ministries with Inactive Members",
                          columns = columns,
                          description="We have identified the following ministries in ParishSoft that have inactive members:",
                          items=results,
                          args=args,
                          log=log,
                          group_column='ministryName',)

##############################################################################

def check_for_member_workgroups_with_inactive_members(members, log, args):
    #HJCTODO: Consolidate this, family_workgroups, and the two email checks into one abstract function that these call instead.
    log.debug('Checking for Member Workgroups with Inactive Members')
    results = []

    for member in members.values():
        if ParishSoft.member_is_active(member):
            continue
        for name, workgroup in member['py workgroups'].items():
            results.append({'workgroupName': workgroup['name'], 
                           'memberDUID': member['memberDUID'],
                           'lastName': member['lastName'],
                           'firstName': member['firstName']}),

    columns = [('workgroupName', 'Workgroup Name'),
               ('memberDUID', 'Member DUID'),
               ('lastName', 'Member Last Name'),
               ('firstName', 'Member First Name')]

    log.debug(f"Found {len(results)} results")

    if len(results) == 0:
        log.debug(f"Found NO matching groups - no need to send an email")
    else:
        results = sorted(results, key=lambda item: (item["workgroupName"], item["lastName"], item["firstName"]))
        send_groups_email(to=args.memberworkgrouprecip,
                          subject="Workgroups with Inactive Members",
                          columns = columns,
                          description="We have identified the following Member Workgroups in ParishSoft that have inactive members:",
                          items=results,
                          args=args,
                          log=log,
                          group_column='workgroupName')

##############################################################################

def check_for_family_workgroups_with_inactive_families(families, log, args):
    log.debug('Checking for Family Workgroups with Inactive Families')
    results = []

    for family in families.values():
        if ParishSoft.family_is_active(family):
            continue
        for name, workgroup in family['py workgroups'].items():
            results.append({'workgroupName': workgroup['name'], 
                           'familyDUID': family['familyDUID'],
                           'lastName': family['lastName'],
                           'firstName': family['firstName']}),

    columns = [('workgroupName', 'Workgroup Name'),
               ('familyDUID', 'Family DUID'),
               ('lastName', 'Member Last Name'),
               ('firstName', 'Member First Name')]

    log.debug(f"Found {len(results)} results")

    if len(results) == 0:
        log.debug(f"Found NO matching groups - no need to send an email")
    else:
        results = sorted(results, key=lambda item: (item["workgroupName"], item["lastName"], item["firstName"]))
        send_groups_email(to=args.memberworkgrouprecip,
                          subject="Family Workgroups with Inactive Families",
                          columns = columns,
                          description="We have identified the following Family Workgroups in ParishSoft that have inactive families:",
                          items=results,
                          args=args,
                          log=log,
                          group_column='workgroupName')

##############################################################################

def check_for_ministries_with_no_staff_or_chair(ministries, log, args):
    log.debug('Checking for Ministries without a Staff Member and/or Chairperson')
    results = []

    for ministry_id, ministry in ministries.items():
        #log.debug(ministry['name'])
        #exit(0)
        log.debug(f'Checking ministry: {ministry['name']}')
        found_chair = False
        found_staff = False
        reasons = []

        for member in ministry['membership']:
            if member["ministryRoleName"] == "Chairperson":
                found_chair = True
                log.debug(f'({ministry['name']}) Found Chairperson: {member['firstName']} {member['lastName']}')
            if member["ministryRoleName"] == "Staff":
                found_staff = True
                log.debug(f'({ministry['name']}) Found Staff member: {member['firstName']} {member['lastName']}')

        if not found_chair:
            log.debug(f'({ministry['name']}) No Chairperson found')
            reasons.append('No chairperson found')
        if not found_staff:
            log.debug(f'({ministry['name']}) No Staff Member found')
            reasons.append('No staff member found')

        if len(reasons) > 0:
            results.append({
                'ministryName': ministry['name'],
                'reasons': ', '.join(reasons),
                })

    columns = [('ministryName', 'Ministry Name'),
               ('reasons', 'Reasons'),]

    log.debug(f"Found {len(results)} results")

    if len(results) == 0:
        log.debug(f"Found NO matching groups - no need to send an email")
    else:
        results = sorted(results, key=lambda item: (item['ministryName']))
        send_groups_email(to=args.nochairrecip,
                          subject="Ministries without a Staff Member and/or Chairperson",
                          columns = columns,
                          description ='We have identified the following ministries in ParishSoft that are missing a Staff Member or Chairperson:',
                          items = results,
                          args=args,
                          log=log)

##############################################################################

def check_for_workgroups_with_members_without_emails(member_workgroups, members, families, log, args):
    #We assume we care about having emails for any given workgroup unless specifically told otherwise
    log.debug('Checking for Workgroups with Members without Emails')
    results = []

    dont_care_workgroups_list = [
        'LVG VET US AIR FORCE',
        'LVG VET US ARMY',
        'LVG VET US MARINES',
        'LVG VET US NAVY',
        'LIVING VETERAN',
        '2018 Photo Waiver',
        '2018 Text Alerts',
        '2018 July-Parish Upd Response',
        'Linda Retirement Planning',
        '2021 parents',
        'DO NOT CONTACT',
        'Homebound',
        'Homebound & 90 yrs',
        'Default',
        ]
                                
    for wg in member_workgroups.values():
        if wg['name'] in dont_care_workgroups_list:
            log.debug(f'Workgroup {wg['name']} was skipped due to dont_care_workgroups_list')
            continue

        log.debug(f'Checking workgroup: {wg['name']}')

        for entry in wg['membership']:
            reasons = []

            member_duid = entry['py member duid']
            member = members[member_duid]
            if not ParishSoft.member_is_active(member):
                #We already handle inactive or deceased members in check_for_member_workgroups_with_inactive_members()
                continue

            if entry['emailAddress'] == None:
                reasons.append("Member has no email address")

            family_duid = entry['py family duid']
            family = families[family_duid]
            if family['sendNoMail'] == True:
                reasons.append('Family "Send Mail" is not checked')

            if len(reasons) > 0:
                results.append({'workgroupName': wg['name'], 
                       'memberDUID': entry['py member duid'],
                       'lastName': entry['lastName'],
                       'firstName': entry['firstName'],
                       'reasons': ', '.join(reasons),
                       })

    columns = [('workgroupName', 'Workgroup Name'),
               ('memberDUID', 'Member DUID'),
               ('lastName', 'Member Last Name'),
               ('firstName', 'Member First Name'),
               ('reasons', 'Reasons'),]

    log.debug(f"Found {len(results)} results")

    if len(results) == 0:
        log.debug(f"Found NO matching groups - no need to send an email")
    else:
        results = sorted(results, key=lambda item: (item["workgroupName"], item["lastName"], item["firstName"]))
        send_groups_email(to=args.workgroupnoemailrecip,
                          subject="Workgroups with Members that Have No Email Addresses",
                          columns = columns,
                          description="We have identified the following Member Workgroups in ParishSoft that have members without email addresses:",
                          items=results,
                          args=args,
                          log=log,
                          group_column='workgroupName')


##############################################################################

def check_for_associated_nonparishionar_families_with_do_not_communicate(families, log, args):
    #HCJTODO: Look at removing "columns" in favor of just having good results names
    #ANP is specifically for families that want to receive communications, so if "do not commuicate" is set, that's a contradiction
    log.debug('Checking for Associated Non-Parishioner Families with Do Not Communicate')
    results = []

    for family in families.values():
        if family['py family group'] == 'Associated Non-Parishioner':
            reasons = []

            if family['sendNoMail'] == True:
                reasons.append('Family "Send Mail" is not checked')

            foundEmail = False
            for member in family['py members']:
                if member['emailAddress'] is not None and len(member['emailAddress']) != 0 :
                    foundEmail = True
                    break
            if not foundEmail:
                reasons.append('No members in the family have an email address.')

            if len(reasons) > 0:
                results.append({
                   'familyDUID': family['familyDUID'],
                   'lastName': family['lastName'],
                   'firstName': family['firstName'],
                   'reason': ', '.join(reasons),
                   })

    columns = [('familyDUID', 'Family DUID'),
                ('lastName', 'Family Last Name'),
                ('firstName', 'Family First Name'),
                ('reason', 'Reason'),]

    log.debug(f"Found {len(results)} results")

    if len(results) == 0:
        log.debug(f"Found NO matching groups - no need to send an email")
    else:
        results = sorted(results, key=lambda item: (item["lastName"], item["firstName"]))
        send_groups_email(to=args.nonparishionerrecip,
                          subject="Associated Non-Parishioner Families without Email",
                          columns = columns,
                          description='We have identified the following associated non-parishioner families in ParishSoft that either do not have "Send Email" checked or have no members with email addresses:',
                          items=results,
                          args=args,
                          log=log)


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
    parser.add_argument('--ministryrecip',
                        default= default_email,
                        help= 'Recipient for the Ministries with Inactive Members email')
    parser.add_argument('--familyworkgrouprecip',
                        default= default_email,
                        help= 'Recipient for the Family Workgroups with Inactive Families email')
    parser.add_argument('--memberworkgrouprecip',
                        default= default_email,
                        help= 'Recipient for the Member Workgroups with Inactive Members email')
    parser.add_argument('--nochairrecip',
                        default= default_email,
                        help= 'Recipient for the Ministries without a Staff Member or Chairperson email')
    parser.add_argument('--workgroupnoemailrecip',
                        default= default_email,
                        help= 'Recipient for the Workgroups with Members without Email email')
    parser.add_argument('--nonparishionerrecip',
                        default= default_email,
                        help= 'Recipient for the Associated Non-Parishioner Families without Email email')

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
    families, members, family_workgroups, member_workgroups, ministries = \
        ParishSoft.load_families_and_members(api_key=args.api_key,
                                             cache_dir=args.ps_cache_dir,
                                             active_only=False,
                                             parishioners_only=False,
                                             log=log)

    check_for_families_without_members(families, log, args)

    check_for_active_families_with_inactive_members(families, log, args)

    check_for_inactive_families_with_active_members(families, log, args)

    check_for_whitespace_data(members, families, log, args)

    check_for_ministries_with_inactive_members(families, members, log, args)

    check_for_member_workgroups_with_inactive_members(members, log, args)

    check_for_family_workgroups_with_inactive_families(families, log, args)

    check_for_ministries_with_no_staff_or_chair(ministries, log, args)

    check_for_workgroups_with_members_without_emails(member_workgroups, members, families, log, args)

    check_for_associated_nonparishionar_families_with_do_not_communicate(families, log, args)

main()
