#!/usr/bin/env python3

"""Script to iterate through ministries and Member keywords from PDS and
sync the membership of a Google Group to match.

- Use a hard-coded list of ministries+keywords and associated Google
  Groups.  NOTE: the ministries, keywords, and Google Group names must
  match EXACTLY.
- For each:

  - Determine if the Google Group is a Broadcast (only manager/owers
    can post) or Discussion group (anyone can post).
  - Find all PDS Members in a given ministry and/or have a given
    keyword.
  - Find all members of the Google Group
  - Compare the two:
    - Find which PDS members should be added to the Google Group
    - Find which email addresses should be removed from the Google Group
    - Find which email addresses in the Google Group need to change
      role (from member -> owner or owner -> member)
  - If not a dry run, do the actions found above

No locking / lockfile is used in this script because it is assumed
that simultaneous access is prevented by locking at a higher level
(i.e., ../run-all.py).

-----

This script was developed and tested with Python 3.6.4.  It has not
been tested with other versions (e.g., Python 2.7.x).

-----

This script uses Google OAuth authentication; it requires a
"client_id.json" file with the app credentials from the Google App
dashboard.  This file is not committed here in git for obvious reasons
(!).

The client_id.json file is obtained from
console.developers.google.com, project name "PDS to Google Groups".
The project is owned by itadmin@epiphanycatholicchurch.org.

This script will create/fill a "user-credentials.json" file in the
same directory with the result of getting user consent for the Google
Account being used to authenticate.

Note that this script works on Windows, Linux, and OS X.  But first,
you need to install some Python classes:

    pip install --upgrade google-api-python-client
    pip install --upgrade httplib2
    ^^ NOTE: You may need to "sudo pip3.6 ..." instead of "sudo pip ..."

"""

import sys
sys.path.insert(0, '../../../python')

import logging.handlers
import httplib2
import smtplib
import logging
import sqlite3
import json
import time
import os

import ECC
import Google
import PDSChurch
import GoogleAuth
import googleapiclient

from oauth2client import tools
from email.message import EmailMessage

from pprint import pprint
from pprint import pformat

# Globals

args = None
log = None

# Default for CLI arguments
smtp = ["smtp-relay.gmail.com",
        "no-reply@epiphanycatholicchurch.org"]
gapp_id='client_id.json'
guser_cred_file = 'user-credentials.json'
verbose = True
debug = False
logfile = "log.txt"

# JMS Change me to itadmin
fatal_notify_to = 'jsquyres@gmail.com'

# Google Group permissions
BROADCAST  = 1
DISCUSSION = 2

#-------------------------------------------------------------------

def send_mail(to, subject, message_body, html=False, log=None):
    if not args.smtp:
        if log:
            log.debug('Not sending email "{0}" because SMTP not setup'.format(subject))
        return

    smtp_server   = args.smtp[0]
    smtp_from     = args.smtp[1]

    if log:
        log.info('Sending email to {to}, subject "{subject}"'
                 .format(to=to, subject=subject))
    with smtplib.SMTP_SSL(host=smtp_server) as smtp:
        if args.debug:
            smtp.set_debuglevel(2)

        # This assumes that the file has a single line in the format of username:password.
        with open(args.smtp_auth_file) as f:
            line = f.read()
            smtp_username, smtp_password = line.split(':')

        # Login; we can't rely on being IP whitelisted.
        try:
            smtp.login(smtp_username, smtp_password)
        except Exception as e:
            log.error(f'Error: failed to SMTP login: {e}')
            exit(1)

        msg = EmailMessage()
        msg.set_content(message_body)
        msg['Subject'] = subject
        msg['From'] = smtp_from
        msg['To'] = to
        if html:
            msg.replace_header('Content-Type', 'text/html')
        else:
            msg.replace_header('Content-Type', 'text/plain')

        smtp.send_message(msg)

#-------------------------------------------------------------------

def email_and_die(msg):
    sys.stderr.write(msg)
    sys.stderr.write("Aborting")

    send_mail(fatal_notify_to,
              'Fatal error from PDS<-->Google Group sync', msg)

    exit(1)


####################################################################
#
# Sync functions
#
####################################################################

def compute_sync(sync, pds_members, group_members, log=None):
    actions = list()

    for pm in pds_members:
        found_in_google_group = False
        for gm in group_members:
            if pm['email'] == gm['email']:
                found_in_google_group = True
                gm['sync_found'] = True

                if pm['leader'] and gm['role'] != 'owner':
                    # In this case, the PDS Member is in the group,
                    # but they need to be changed to a Google Group
                    # OWNER.
                    actions.append({
                        'action'              : 'change role',
                        'email'               : pm['email'],
                        'role'                : 'OWNER',
                        'pds_ministry_member' : pm,
                    })

                elif not pm['leader'] and gm['role'] == 'owner':
                    # In this case, the PDS Member is in the group,
                    # but they need to be changed to a Google Group
                    # MEMBER.
                    actions.append({
                        'action'              : 'change role',
                        'email'               : pm['email'],
                        'role'                : 'MEMBER',
                        'pds_ministry_member' : pm,
                    })

        if not found_in_google_group:
            # In this case, we have an email address that needs to be
            # added to the Google Group.
            role = 'MEMBER'
            if pm['leader']:
                role = 'OWNER'

            actions.append({
                'action'              : 'add',
                'email'               : pm['email'],
                'role'                : role,
                'pds_ministry_member' : pm,
            })

    # Now go through all the group members and see who wasn't
    # 'sync_found' (above).  These are the emails we need to delete
    # from the Google Group.
    for gm in group_members:
        if 'sync_found' in gm and gm['sync_found']:
            continue

        actions.append({
            'action'              : 'delete',
            'email'               : gm['email'],
            'id'                  : gm['id'],
            'role'                : None,
            'pds_ministry_member' : None,
        })

    return actions

#-------------------------------------------------------------------

def do_sync(sync, group_permissions, service, actions, log=None):
    ministries = sync['ministries'] if 'ministries' in sync else 'None'
    keywords   = sync['keywords']   if 'keywords'   in sync else 'None'

    type_str   = 'Broadcast' if group_permissions == BROADCAST else 'Discussion'

    log.info("Synchronizing ministries: {min}, keywords: {key}, group: {ggroup}, type {type}"
             .format(min=ministries, key=keywords, ggroup=sync['ggroup'],
                     type=type_str))

    # Process each of the actions
    changes     = list()
    for action in actions:
        a = action['action']
        r = action['role']

        # Remember: the pds_ministry_member contains an array of PDS
        # members (because there may be more than one PDS Member that
        # shares the same email address).
        mem_names = None
        key = 'pds_ministry_member'
        if key in action and action[key]:
            for mem in action[key]['pds_members']:
                if mem_names is None:
                    mem_names = mem['Name']
                else:
                    mem_names += ', {name}'.format(name=mem['Name'])

        log.debug("Processing action: {action} / {email} / {role}".
                  format(action=action['action'],
                         email=action['email'],
                         role=action['role']))
        # JMS This outputs PDS Members (and their families!) -- very
        # lengthy output.
        #log.debug("Processing full action: {action}".
        #          format(action=pformat(action)))

        msg = None
        if a == 'change role':
            if r == 'OWNER':
                msg = _sync_member_to_owner(sync, group_permissions,
                                            service, action, mem_names, log)
            elif r == 'MEMBER':
                msg = _sync_owner_to_member(sync, group_permissions,
                                            service, action, mem_names, log)
            else:
                log.error("Action: change role, unknown role: {role} -- PDS Member {name} (skipped)"
                          .format(role=r, name=mem_names))
                continue

        elif a == 'add':
            msg = _sync_add(sync, group_permissions,
                            service=service, action=action,
                            name=mem_names, log=log)

        elif a == 'delete':
            msg = _sync_delete(sync, service, action, mem_names, log)

        else:
            log.error("Unknown action: {action} -- PDS Member {name} (skipped)"
                      .format(action=a, name=mem_names))

        if msg:
            email = action['email']
            i     = len(changes) + 1
            changes.append("<tr>\n<td>{i}.</td>\n<td>{name}</td>\n<td>{email}</td>\n<td>{msg}</td>\n</tr>"
                           .format(i=i,
                                   name=mem_names,
                                   email=action['email'],
                                   msg=msg))

    # If we have changes to report, email them
    if len(changes) > 0:
        subject = 'Update to Google Group for '

        subject_add = list()
        rationale   = list()
        if 'ministries' in sync:
            for m in sync['ministries']:
                rationale.append('<li> Members in the "{m}" ministry</li>'
                                 .format(m=m))
                subject_add.append(m)

        if 'keywords' in sync:
            for k in sync['keywords']:
                rationale.append('<li> Members with the "{k}" keyword</li>'
                                .format(k=k))
                subject_add.append(k)

        # Assemble the final subject line
        subject = subject + ', '.join(subject_add)

        # Assemble the final email body
        style = r'''table { border-collapse: collapse; }
th, td {
    text-align: left;
    padding: 8px;
    border-bottom: 1px solid #ddd;
}
tr:nth-child(even) { background-color: #f2f2f2; }'''

        body = ("""<html>
<head>
<style>
{style}
</style>
</head>
<body>
<p>The following changes were made to the {type} Google Group {email}:</p>

<p><table border=0>
<tr>
<th>&nbsp;</th>
<th>Name</th>
<th>Email address</th>
<th>Action</th>
</tr>
{changes}
</table></p>

<p>These email addresses were obtained from PDS:</p>

<p><ol>
{rationale}
</ol></p>
</body>
</html>
"""
                .format(type=type_str,
                        style=style,
                        email=sync['ggroup'],
                        changes='\n'.join(changes),
                        rationale='\n'.join(rationale)))

        # Send the email
        send_mail(to=sync['notify'], subject=subject, message_body=body,
                  html=True, log=log)

#-------------------------------------------------------------------

def _sync_member_to_owner(sync, group_permissions,
                          service, action, name, log=None):
    email = action['email']
    if log:
        log.info("Changing PDS Member {name} ({email}) from Google Group Member to Owner"
                 .format(name=name, email=email))

    # Per
    # https://stackoverflow.com/questions/31552146/group-as-owner-or-manager-fails-with-400-error,
    # we can't set a Group as an OWNER or MANAGER of another Group
    # (e.g., director-worship@ecc.org can't be the owner of one of the
    # ministry groups).  As of Aug 2018, you can still do it in the
    # Google Web dashboard (i.e., remove the Group, then re-add the
    # Group as an OWNER), but you can't do it via the API.  Apparently
    # this is Google's intended behavior -- the fact that it works on
    # the Google Web dashboard is a fluke.  :-( So we just have to
    # plan on not being able to set Groups to be OWNER or MANAGER of
    # another Group.  Sigh.

    group_entry = {
        'email' : email,
        'role'  : 'OWNER',
    }
    service.members().update(groupKey=sync['ggroup'],
                             memberKey=email,
                             body=group_entry).execute()

    if group_permissions == BROADCAST:
        msg = "Change to: owner (can post to this group)"
    else:
        msg = "Change to: owner"

    return msg

def _sync_owner_to_member(sync, group_permissions,
                          service, action, name, log=None):
    email = action['email']
    if log:
        log.info("Changing PDS Member {name} ({email}) from Google Group Owner to Member"
                 .format(name=name, email=email))

    group_entry = {
        'email' : email,
        'role'  : 'MEMBER',
    }
    service.members().update(groupKey=sync['ggroup'],
                             memberKey=email,
                             body=group_entry).execute()

    if group_permissions == BROADCAST:
        msg = "Change to: member (can <strong><em>not</em></strong> post to this group)"
    else:
        msg = "Change to: member"

    return msg

def _sync_add(sync, group_permissions,
              service, action, name, log=None):
    email = action['email']
    role  = action['role']
    if log:
        log.info("Adding PDS Member {name} ({email}) as Google Group {role}"
                 .format(name=name, email=email, role=role.lower()))

    group_entry = {
        'email' : email,
        'role'  : role,
    }
    try:
        service.members().insert(groupKey=sync['ggroup'],
                                 body=group_entry).execute()

        if group_permissions == BROADCAST:
            if role == 'OWNER':
                msg = "Added to group (can post to this group)"
            else:
                msg = "Added to group (can <strong><em>not</em></strong> post to this group)"
        else:
            msg = "Added to group"

    except googleapiclient.errors.HttpError as e:
        # NOTE: If we failed because this is a duplicate, then don't
        # worry about it.
        msg = "FAILED to add this member -- Google error:"

        j = json.loads(e.content)
        for err in j['error']['errors']:
            if err['reason'] == 'duplicate':
                if log:
                    log.error("Google says a duplicate of {email} "
                              "already in the group -- ignoring"
                              .format(email=email))
                return None

            elif err['reason'] == 'backendError':
                if log:
                    log.error("Google had an internal error while processing"
                              "{email} -- ignoring"
                              .format(email=email))
                return None

            msg += " {msg} ({reason})".format(msg=err['message'],
                                              reason=err['reason'])
    except:
        all = sys.exc_info()
        msg = ("FAILED to add this member -- unknown Google error! "
               "({a} / {b} / {c})"
               .format(a=all[0], b=all[1], c=all[2]))

    return msg

def _sync_delete(sync, service, action, name, log=None):
    email = action['email']

    # We delete by ID (instead of by email address) because of a weird
    # corner case:
    #
    # - foo@example.com (a non-gmail address) is in a google group,
    #   but has no Google account
    # - later, foo@example.com visits
    #   https://accounts.google.com/SignupWithoutGmail and gets a
    #   Google account associated with that email address
    #
    # In this case, Google seems to be somewhat confused:
    # foo@example.com is still associated with the Group, but it's the
    # non-Google-account foo@example.com.  But if we attempt to move
    # that email address, it'll try to remove the Google-account
    # foo@example.com (and therefore fail).
    #
    # So we remove by ID, and that unambiguously removes the correct
    # member from the Group.
    id    = action['id']
    if log:
        log.info("Deleting PDS Member {name} ({email}) from group {group}"
                 .format(name=name, email=email, group=sync['ggroup']))

    service.members().delete(groupKey=sync['ggroup'],
                             memberKey=id).execute()

    msg = "Removed from the group"
    return msg

####################################################################
#
# Google queries
#
####################################################################

def google_group_get_permissions(service, group_email, log=None):
    response = (service
                .groups()
                .get(groupUniqueId=group_email,
                     fields='whoCanPostMessage')
                .execute())

    who = response.get('whoCanPostMessage')
    if log:
        log.info("Group permissions for {email}: {who}"
                 .format(email=group_email, who=who))

    if (who == 'ANYONE_CAN_POST' or who == 'ALL_MEMBERS_CAN_POST' or
        who == 'ALL_IN_DOMAIN_CAN_POST'):
        return DISCUSSION
    else:
        return BROADCAST

#-------------------------------------------------------------------

def google_group_find_members(service, sync, log=None):
    group_members = list()

    # Iterate over all (pages of) group members
    page_token = None
    while True:
        response = (service
                    .members()
                    .list(pageToken=page_token,
                          groupKey=sync['ggroup'],
                          fields='members(email,role,id)').execute())
        for group in response.get('members', []):
            group_members.append({
                'email' : group['email'].lower(),
                'role'  : group['role'].lower(),
                'id'    : group['id'].lower(),
            })

        page_token = response.get('nextPageToken', None)
        if page_token is None:
            break

    if log:
        log.debug("Google Group membership for {group}"
                  .format(group=sync['ggroup']))
        log.debug(group_members)

    return group_members

####################################################################
#
# PDS queries
#
####################################################################

# Returns two values:
# Boolean: if the Member is in any of the ministry names provided
#          --> I.e., if the Member is in the ministry
# Boolean: if the Member is Chairperson in any of the ministry names provided
#          --> I.e., if the Member should be able to post to the Google Group
def _member_in_any_ministry(member, ministries):
    if 'active_ministries' not in member:
        return False, False

    found = False
    chair_of_any = False
    for member_ministry in member['active_ministries']:
        member_ministry_name = member_ministry['Description']
        if member_ministry_name in ministries:
            found = True
            if 'Chair' in member_ministry['status']:
                chair_of_any = True
    if found:
        return found, chair_of_any

    # Didn't find the Member in any of the ministries
    return False, False

# Returns two values:
# Boolean: if the member has any KEYWORD or "KEYWORD Ldr"  from those provided
#          --> I.e., if the Member has the base keyword
# Boolean: if the member has "KEYWORD Ldr" from those provided
#          --> I.e., if the Member should be able to post to the Google Group
def _member_has_any_keyword(member, keywords):
    if 'keywords' not in member:
        return False, False

    found_any  = False
    poster_of_any = False
    for k in keywords:
        if k in member['keywords']:
            found_any     = True
        if '{key} Ldr'.format(key=k) in member['keywords']:
            found_any     = True
            poster_of_any = True

    return found_any, poster_of_any

def pds_find_ministry_members(members, sync, log=None):
    ministry_members = list()
    ministries       = list()
    keywords         = list()
    found_emails     = dict()

    # Make the sync ministries be an array
    if 'ministries' in sync:
        if type(sync['ministries']) is list:
            ministries = sync['ministries']
        else:
            ministries = [ sync['ministries'] ]

    # Make the sync keywords be a group
    if 'keywords' in sync:
        if type(sync['keywords']) is list:
            keywords = sync['keywords']
        else:
            keywords = [ sync['keywords'] ]

    # Walk all members looking for those in any of the ministries or
    # those that have any of the keywords.
    for mid, member in members.items():
        min_any, chair_of_any  = _member_in_any_ministry(member, ministries)
        key_any, poster_of_any = _member_has_any_keyword(member, keywords)

        if not min_any and not key_any:
            continue

        leader = False
        if chair_of_any or poster_of_any:
            leader = True

        emails = PDSChurch.find_any_email(member)
        for email in emails:
            e = email.lower()
            new_entry = {
                'pds_members' : [ member ],
                'email'       : e,
                'leader'      : leader,
            }

            # Here's a kicker: some PDS Members share an email
            # address.  This means we might find multiple Members with
            # the same email address who are in the same ministry.
            # ...and they might have different permissions (one may be
            # a poster and one may not)!  Since Google Groups will
            # treat these multiple Members as a single email address,
            # we just have to take the most permissive Member's
            # permission for the shared email address.

            if e in found_emails:
                index = found_emails[e]
                leader = leader or ministry_members[index]['leader']
                ministry_members[index]['leader'] = leader
                ministry_members[index]['pds_members'].append(member)
            else:
                ministry_members.append(new_entry)
                found_emails[e] = len(ministry_members) - 1

    if log:
        log.debug("PDS members for ministries {m} and keywords {k}:"
                  .format(m=ministries, k=keywords))
        for m in ministry_members:
            name_str = ''
            for pm in m['pds_members']:
                if len(name_str) > 0:
                    name_str = name_str + ' or '
                name_str = name_str + pm['Name']

            log.debug('  {name} <{email}> leader: {leader}'
                      .format(name=name_str,
                              email=m['email'],
                              leader=m['leader']))

    return ministry_members

####################################################################
#
# Setup functions
#
####################################################################

def setup_cli_args():
    # Be sure to check the Google SMTP relay documentation for
    # non-authenticated relaying instructions:
    # https://support.google.com/a/answer/2956491
    # We are using the following settings:
    # - Allowed senders: only addresses in my domains
    # - Only accept mail from the specified IP addresses: No
    # - Require SMTP Authentication: yes
    #   |--> This means that you have to specify an ECC Google Account email
    #        address as an argument to --smtp, and you must also specify
    #        a 2FA app-specific password as the password.  Do NOT use
    #        "allow less-secure apps", because Google is deprecating that
    #        functionality and it will disappear someday.  Use 2FA
    #        app-specific passwords.
    # - Require TLS encryption: yes
    global smtp
    tools.argparser.add_argument('--smtp',
                                 nargs=2,
                                 default=smtp,
                                 help='SMTP server hostname, from addresses')
    tools.argparser.add_argument('--smtp-auth-file',
                                 required=True,
                                 help='File containing SMTP AUTH username:password')

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

    tools.argparser.add_argument('--sqlite3-db',
                                 required=True,
                                 help='SQLite3 database containing PDS data')

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

    # Sanity check args
    l = 0
    if args.smtp:
        l = len(args.smtp)
    if l > 0 and l != 2:
        log.error("Need exactly 2 arguments to --smtp: server from_addr")
        exit(1)

    return args

####################################################################
#
# Main
#
####################################################################

def main():
    args = setup_cli_args()

    log = ECC.setup_logging(info=args.verbose,
                            debug=args.debug,
                            logfile=args.logfile)

    (pds, pds_families,
     pds_members) = PDSChurch.load_families_and_members(filename=args.sqlite3_db,
                                                        parishioners_only=False,
                                                        log=log)

    apis = {
        'admin' : { 'scope'       : Google.scopes['admin'],
                    'api_name'    : 'admin',
                    'api_version' : 'directory_v1', },
        'group' : { 'scope'       : Google.scopes['group'],
                    'api_name'    : 'groupssettings',
                    'api_version' : 'v1', },
    }
    services = GoogleAuth.service_oauth_login(apis,
                                              app_json=args.app_id,
                                              user_json=args.user_credentials,
                                              log=log)
    service_admin = services['admin']
    service_group = services['group']

    ecc = '@epiphanycatholicchurch.org'
    synchronizations = [
        {
            'ministries' : [ '102-Finance Advisory Council' ],
            'ggroup'     : 'administration-committee{ecc}'.format(ecc=ecc),
            'notify'     : 'business-manager{ecc},pds-google-sync{ecc}'.format(ecc=ecc),
        },
        {
            'ministries' : [ '203-Garden & Grounds' ],
            'ggroup'     : 'garden-and-grounds{ecc}'.format(ecc=ecc),
            'notify'     : 'mary{ecc},emswine2@gmail.com,pds-google-sync{ecc}'.format(ecc=ecc),
        },
        {
            'ministries' : [ '207-Technology Committee' ],
            'ggroup'     : 'tech-committee{ecc}'.format(ecc=ecc),
            'notify'     : 'business-manager{ecc},pds-google-sync{ecc}'.format(ecc=ecc),
        },

        {
            'keywords'   : [ 'Liturgy Transcriptions' ],
            'ggroup'     : 'liturgy-transcriptions{ecc}'.format(ecc=ecc),
            'notify'     : 'mary{ecc},pds-google-sync{ecc}'.format(ecc=ecc),
        },

        #############################

        {
            'ministries' : [ '100-Parish Pastoral Council' ],
            'ggroup'     : 'ppc{ecc}'.format(ecc=ecc),
            'notify'     : 'bookkeeper{ecc},pds-google-sync{ecc}'.format(ecc=ecc),
        },
        {
            'keywords'   : [ 'PPC Executive Committee' ],
            'ggroup'     : 'ppc-exec{ecc}'.format(ecc=ecc),
            'notify'     : 'bookkeeper{ecc},pds-google-sync{ecc}'.format(ecc=ecc),
        },

        #############################

        {
            'ministries' : [ '602-Singles Explore Life (SEL)' ],
            'ggroup'     : 'sel{ecc}'.format(ecc=ecc),
            'notify'     : 'lynne{ecc},pds-google-sync{ecc}'.format(ecc=ecc),
        },

        #############################

        {
            'ministries' : [ '302-Bread Baking Ministry' ],
            'ggroup'     : 'breadmakers{ecc}'.format(ecc=ecc),
            'notify'     : 'linda{ecc},pds-google-sync{ecc}'.format(ecc=ecc),
        },
        {
            'ministries' : [ '103-Worship Committee' ],
            'ggroup'     : 'worship-committee{ecc}'.format(ecc=ecc),
            'notify'     : 'linda{ecc},pds-google-sync{ecc}'.format(ecc=ecc),
        },
        {
            'ministries' : [ '304-Liturgical Planning' ],
            'ggroup'     : 'liturgy-planning{ecc}'.format(ecc=ecc),
            'notify'     : 'linda{ecc},pds-google-sync{ecc}'.format(ecc=ecc),
        },
        {
            'ministries' : [ '305-Movers Ministry' ],
            'ggroup'     : 'movers{ecc}'.format(ecc=ecc),
            'notify'     : 'linda{ecc},awsimpson57@gmail.com,pds-google-sync{ecc}'.format(ecc=ecc),
        },
        {
            'ministries' : [ '309A-Acolyte Ministry 5:30P',
                             '309B-Acolyte Ministry  9:00A',
                             '309C-Acolyte Ministry 11:30A' ],
            'ggroup'     : 'acolytes{ecc}'.format(ecc=ecc),
            'notify'     : 'linda{ecc},pds-google-sync{ecc}'.format(ecc=ecc),
        },
        {
            'ministries' : [ '310-Adult Choir' ],
            'ggroup'     : 'choir{ecc}'.format(ecc=ecc),
            'notify'     : 'linda{ecc},faith@feetwashers.org,pds-google-sync{ecc}'.format(ecc=ecc),
        },
        {
            'ministries' : [ '311-Bell Choir' ],
            'keywords'   : [ 'Bell choir email list' ],
            'ggroup'     : 'bell-ringers{ecc}'.format(ecc=ecc),
            'notify'     : 'linda{ecc},pds-google-sync{ecc}'.format(ecc=ecc),
        },
        {
            'ministries' : [ '313-Communion Ministers' ],
            'ggroup'     : 'communion-ministers{ecc}'.format(ecc=ecc),
            'notify'     : 'linda{ecc},stephen@feetwashers.org,pds-google-sync{ecc}'.format(ecc=ecc),
        },
        {
            'ministries' : [ '314-Communion Min. Coordinator'],
            'ggroup'     : 'communion-ministers-coordinators{ecc}'.format(ecc=ecc),
            'notify'     : 'linda{ecc},stephen@feetwashers.org,pds-google-sync{ecc}'.format(ecc=ecc),
        },
        {
            'ministries' : [ '315-Funeral Mass Ministry' ],
            'ggroup'     : 'funeral-mass-ministry{ecc}'.format(ecc=ecc),
            'notify'     : 'linda{ecc},pds-google-sync{ecc}'.format(ecc=ecc),
        },
        {
            'ministries' : [ '317-Instrumentalists & Cantors' ],
            'keywords'   : [ 'Musicians email list' ],
            'ggroup'     : 'musicians{ecc}'.format(ecc=ecc),
            'notify'     : 'linda{ecc},pds-google-sync{ecc}'.format(ecc=ecc),
        },
        {
            'ministries' : [ '318-Lectors  MASTER LIST' ],
            'ggroup'     : 'lectors{ecc}'.format(ecc=ecc),
            'notify'     : 'linda{ecc},pds-google-sync{ecc}'.format(ecc=ecc),
        },
        {
            'ministries' : [ '321-Prayer Chain Ministry' ],
            'ggroup'     : 'prayer-chain-ministry{ecc}'.format(ecc=ecc),
            'notify'     : 'linda{ecc},pds-google-sync{ecc}'.format(ecc=ecc),
        },
        {
            'ministries' : [ 'E-Taize Prayer' ],
            'ggroup'     : 'taizeprayer{ecc}'.format(ecc=ecc),
            'notify'     : 'linda{ecc},pds-google-sync{ecc}'.format(ecc=ecc),
        },
        {
            'ministries' : [ 'E-Soul Life' ],
            'ggroup'     : 'soullife{ecc}'.format(ecc=ecc),
            'notify'     : 'linda{ecc},pds-google-sync{ecc}'.format(ecc=ecc),
        },

        {
            'keywords'   : [ 'Wedding Ministries email list' ],
            'ggroup'     : 'wedding-ministries{ecc}'.format(ecc=ecc),
            'notify'     : 'linda{ecc},pds-google-sync{ecc}'.format(ecc=ecc),
        },
        {
            'keywords'   : [ 'Homebound MP3 Recordings' ],
            'ggroup'     : 'mp3-uploads-group{ecc}'.format(ecc=ecc),
            'notify'     : 'linda{ecc},business-manager{ecc},pds-google-sync{ecc}'.format(ecc=ecc),
        },
        {
            'keywords'   : [ 'Homebound recipients email lst', 'Homebound MP3 Recordings' ],
            'ggroup'     : 'ministry-homebound-liturgy-recipients{ecc}'.format(ecc=ecc),
            'notify'     : 'linda{ecc},pds-google-sync{ecc}'.format(ecc=ecc),
        },
        {
            'keywords'   : [ 'Recordings access' ],
            'ggroup'     : 'recordings-viewer{ecc}'.format(ecc=ecc),
            'notify'     : 'linda{ecc},pds-google-sync{ecc}'.format(ecc=ecc),
        },
        {
            # JMS To be deleted after 30 May 2020
            'keywords'   : [ 'ECC Sheet Music access' ],
            'ggroup'     : 'music-ministry-sheet-music-access{ecc}'.format(ecc=ecc),
            'notify'     : 'linda{ecc},pds-google-sync{ecc}'.format(ecc=ecc),
        },
        {
            'keywords'   : [ 'ECC Musicians Info editor' ],
            'ggroup'     : 'music-ministry-musicians-information-editor{ecc}'.format(ecc=ecc),
            'notify'     : 'linda{ecc},pds-google-sync{ecc}'.format(ecc=ecc),
        },
        {
            'keywords'   : [ 'ECC Liturgy Plans editor' ],
            'ggroup'     : 'worship-liturgy-planning{ecc}'.format(ecc=ecc),
            'notify'     : 'linda{ecc},pds-google-sync{ecc}'.format(ecc=ecc),
        },
        {
            'keywords'   : [ 'ECC Liturgy Plans reader' ],
            'ggroup'     : 'worship-liturgy-planning-guest{ecc}'.format(ecc=ecc),
            'notify'     : 'linda{ecc},pds-google-sync{ecc}'.format(ecc=ecc),
        },

        #############################

        {
            'ministries' : [ '451-Livestream Team Ministry' ],
            'ggroup'     : 'livestream-team{ecc}'.format(ecc=ecc),
            'notify'     : 'director-communications{ecc},TomHayesMP@gmail.com,pds-google-sync{ecc}'.format(ecc=ecc),
        },

        #############################

        {
            'ministries' : [ '800-ChildrenFormationCatechist' ],
            'ggroup'     : 'childrens-formation-catechists{ecc}'.format(ecc=ecc),
            'notify'     : 'lisa{ecc},pds-google-sync{ecc}'.format(ecc=ecc),
        },

        {
            'ministries' : [ '807-RCIA Team' ],
            'ggroup'     : 'rcia-team{ecc}'.format(ecc=ecc),
            'notify'     : 'lisa{ecc},pds-google-sync{ecc}'.format(ecc=ecc),
        },
        {
            'ministries' : [ "811-Family&Children's WorkGrp" ],
            'ggroup'     : 'family-and-childrens-working-group{ecc}'.format(ecc=ecc),
            'notify'     : 'lisa{ecc},pds-google-sync{ecc}'.format(ecc=ecc),
        },
        {
            'ministries' : [ '812-Adult Form. Working Group' ],
            'ggroup'     : 'adult-formation-working-group{ecc}'.format(ecc=ecc),
            'notify'     : 'lisa{ecc},pds-google-sync{ecc}'.format(ecc=ecc),
        },
        {
            'ministries' : [ '813-Visual Faith Group' ],
            'ggroup'     : 'visual-faith{ecc}'.format(ecc=ecc),
            'notify'     : 'lisa{ecc},pds-google-sync{ecc}'.format(ecc=ecc),
        },

        #############################

        {
            'ministries' : [ '808-Young Adult Ministry' ],
            'ggroup'     : 'young-adults{ecc}'.format(ecc=ecc),
            'notify'     : 'tasha{ecc},pds-google-sync{ecc}'.format(ecc=ecc),
        },

        {
            'keywords'   : [ 'YouthMin parent: Jr high' ],
            'ggroup'     : 'youth-ministry-parents-jr-high{ecc}'.format(ecc=ecc),
            'notify'     : 'tasha{ecc},pds-google-sync{ecc}'.format(ecc=ecc),
        },
        {
            'keywords'   : [ 'YouthMin parent: Sr high' ],
            'ggroup'     : 'youth-ministry-parents-sr-high{ecc}'.format(ecc=ecc),
            'notify'     : 'tasha{ecc},pds-google-sync{ecc}'.format(ecc=ecc),
        },

        #############################

        {
            'ministries' : [ '600-Men of Epiphany' ],
            'ggroup'     : 'moe{ecc}'.format(ecc=ecc),
            'notify'     : 'lisag{ecc},brayton@howlandgroup.com,pds-google-sync{ecc}'.format(ecc=ecc),
        },

        #############################

        {
            'ministries' : [ '110-Ten Percent Committee' ],
            'ggroup'     : 'ten-percent-committee{ecc}'.format(ecc=ecc),
            'notify'     : 'polly{ecc},pds-google-sync{ecc}'.format(ecc=ecc),
        },

        {
            'keywords'   : [ '10 Pct Emergency Assistance' ],
            'ggroup'     : '10-percent-emergency-assistance{ecc}'.format(ecc=ecc),
            'notify'     : 'polly{ecc},pds-google-sync{ecc}'.format(ecc=ecc),
        },

        #############################

        {
            'ministries' : [ '505-Healing Blanket Ministry' ],
            'ggroup'     : 'healing-blankets-ministry{ecc}'.format(ecc=ecc),
            'notify'     : 'frtony{ecc},pds-google-sync{ecc}'.format(ecc=ecc),
        },
        {
            'ministries' : [ '601-Sages (for 50 yrs. +)' ],
            'ggroup'     : 'sages{ecc}'.format(ecc=ecc),
            'notify'     : 'joanhagedorn46@gmail.com,lisag{ecc},pds-google-sync{ecc}'.format(ecc=ecc),
        },

        #############################

        {
            'ministries' : [ '104-Stewardship & E Committee' ],
            'ggroup'     : 'stewardship{ecc}'.format(ecc=ecc),
            'notify'     : 'angie{ecc},pds-google-sync{ecc}'.format(ecc=ecc),
        },
        {
            'ministries' : [ '707-St. Vincent DePaul' ],
            'ggroup'     : 'SVDPConference{ecc}'.format(ecc=ecc),
            'notify'     : 'polly{ecc},pds-google-sync{ecc}'.format(ecc=ecc),
        },

        #############################

        {
            'keywords'   : [ 'Apply@ECC email list' ],
            'ggroup'     : 'apply{ecc}'.format(ecc=ecc),
            'notify'     : 'mary{ecc},pds-google-sync{ecc}'.format(ecc=ecc),
        },

        #############################

        {
            'keywords'   : [ 'Pastoral staff email list' ],
            'ggroup'     : 'pastoral-staff{ecc}'.format(ecc=ecc),
            'notify'     : 'mary{ecc},pds-google-sync{ecc}'.format(ecc=ecc),
        },
        {
            'keywords'   : [ 'Support staff email list' ],
            'ggroup'     : 'support-staff{ecc}'.format(ecc=ecc),
            'notify'     : 'mary{ecc},pds-google-sync{ecc}'.format(ecc=ecc),
        },
        {
            'keywords'   : [ 'Maintenance staff email list' ],
            'ggroup'     : 'maintenance-staff{ecc}'.format(ecc=ecc),
            'notify'     : 'mary{ecc},pds-google-sync{ecc}'.format(ecc=ecc),
        },
    ]
    for sync in synchronizations:
        group_permissions = google_group_get_permissions(service_group,
                                                         sync['ggroup'],
                                                         log)
        pds_ministry_members = pds_find_ministry_members(pds_members,
                                                         sync, log=log)
        group_members = google_group_find_members(service_admin, sync, log=log)

        actions = compute_sync(sync,
                               pds_ministry_members,
                               group_members, log=log)
        if not args.dry_run:
            do_sync(sync, group_permissions, service_admin, actions, log=log)

    # All done
    pds.connection.close()

if __name__ == '__main__':
    main()
