#!/usr/bin/env python3

#
# See https://openpyxl.readthedocs.io/en/stable/index.html
#
# pip3.6 install openpyxl
#

import sys
import os

import logging.handlers
import logging

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
import PDSChurch
import GoogleAuth
import googleapiclient
from google.api_core import retry

from datetime import datetime
from datetime import timedelta

from oauth2client import tools
from apiclient.http import MediaFileUpload

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment

from pprint import pprint
from pprint import pformat

# Globals

gapp_id         = 'client_id.json'
guser_cred_file = 'user-credentials.json'

ministries = [
    {
        "ministry"  : '100-Parish Pastoral Council',
        "gsheet_id" : '1aIoStpSOsup8XL5eNd8nhpJwM-IqN2gTkwVf_Qvlylc',
        "birthday"  : False,
    },
    {
        "ministry"  : '102-Finance Advisory Council',
        "gsheet_id" : '1oGkjyLDexQyb-z53n2luFpE9vU7Gxv0rX6XirtxSjA0',
        "birthday"  : False,
    },
    {
        "ministry"  : '103-Worship Committee',
        "gsheet_id" : '1h_ZvhkYlnebIu0Tk7h1ldJo-VKnJsJGe1jEzY34mcd0',
        "birthday"  : False,
    },
    {
        "ministry"  : '106-Community Life Committee',
        "gsheet_id" : '1k_hH1tEWBGuERCmFvhZxKOfAsBkqy0uZ16LAd0_jMDg',
        "birthday"  : False,
    },
    {
        "ministry"  : '107-Social Resp Steering Comm',
        "gsheet_id" : '1Am3v0Pv4D9zubkGYgFbUd8e92PZnBPrbcwKrMrs8AnI',
        "birthday"  : False,
    },
    {
        "ministry"  : '110-Ten Percent Committee',
        "gsheet_id" : '18BIrnBWf_4LS9XeC9tordSD1SBgJz67a0I9Ouj6ZcEc',
        "birthday"  : False,
    },

    {
        "ministry"  : '207-Technology Committee',
        "gsheet_id" : '1Gn2m2VMabPkWJWg_NTs6XeGPf_Qi7qPELLxyOx9Q0vU',
        "birthday"  : False,
    },

    {
        "ministry"  : '301-Audio/Visual/Light Minstry',
        "gsheet_id" : '1LtsNJc-9KYZkQqy2BITQ4Xgd_ns4Uo7z3YSQdnQrzN8',
        "birthday"  : False,
    },

    {
        "ministry"  : [ '309-Acolytes INTERESTED ONLY',
                        '309A-Acolyte Ministry 5:30P',
                        '309B-Acolyte Ministry  9:00A',
                        '309C-Acolyte Ministry 11:30A' ],
        "name"      : '309-Acolytes (all masses)',
        "gsheet_id" : '1zXfAxnuQCATWQ7nU7QYn2Mvy1Ql1Huy7Ve1DW60nPKA',
        "birthday"  : False,
    },
    {
        "ministry"  : '309A-Acolyte Ministry 5:30P',
        "gsheet_id" : '17knwBLjpOgV7tSURrVXsyhWhIe0WO0h7AQZ3HIYse6g',
        "birthday"  : False,
    },
    {
        "ministry"  : '309B-Acolyte Ministry  9:00A',
        "gsheet_id" : '1mQOGaT8jKjwfLhuL7afA4zMjoHfSU0zTfqkw9t1CVoI',
        "birthday"  : False,
    },
    {
        "ministry"  : '309C-Acolyte Ministry 11:30A',
        "gsheet_id" : '1GPk3IzlCTMvGYNFR_Q_haK02NqCuaTNd7Z1CdTZGD8w',
        "birthday"  : False,
    },
    {
        "ministry"  : '310-Adult Choir',
        "gsheet_id" : '1ku8Aq9dXm_mrOq421MWVk7hAqV2Am5FFSgUACOYs2WU',
        "birthday"  : False,
    },
    {
        "ministry"  : '311-Bell Choir',
        "gsheet_id" : '1UTzXgO9ZLBHB0w-zAW8-u57cgWLbkWWGanJgPC9gboE',
        "birthday"  : True,
    },
    {
        "ministry"  : [ '313-Communion Ministers',
                        '313A-Communion Ministers: Weekday',
                        '313B-Communion Ministers: 5:30',
                        '313C-Communion Ministers: 9:00'
                        '313D-Communion Ministers:11:30' ],
        "name"      : "313-Communion Ministers (all masses)",
        "gsheet_id" : '10Aq9XtZHL3v0m0Erm71f8BSUYr7CiEDMwzDWTSgKPJ4',
        "birthday"  : False,
    },
    {
        "ministry"  : '313A-Communion: Weekday',
        "gsheet_id" : '1ep1HrUf1jWB43e-wnHiayq6gcDImo8Y26OQ2e5b8gdw',
        "birthday"  : False,
    },
    {
        "ministry"  : '313B-Communion Ministers: 5:30',
        "gsheet_id" : '1S-mZyZwIunBJ1hZYJ942Bd1p--SMeUjEMBw3XU9y404',
        "birthday"  : False,
    },
    {
        "ministry"  : '313C-Communion Ministers: 9:00',
        "gsheet_id" : '1JHcG1krbBqlegL9NU45aAKl0zw0rSrMwmPwhKfXfIXI',
        "birthday"  : False,
    },
    {
        "ministry"  : '313D-Communion Ministers:11:30',
        "gsheet_id" : '1aqgGKqbIUyo0xHFufBPQveFMWJUQ0hVkShx_M4NTflg',
        "birthday"  : False,
    },

    {
        "ministry"  : [ '316-Greeters INTERESTED ONLY',
                        '316A-Greeters 5:30P',
                        '316B-Greeters 9:00A',
                        '316C-Greeters 11:30A' ],
        "name"      : "316-Greeters (all masses)",
        "gsheet_id" : '1vd7sltcU8MVwIBad__PyXXMN_cUEFvdXpL5RkYiBWJ0',
        "birthday"  : False,
    },
    {
        "ministry"  : '316A-Greeters 5:30P',
        "gsheet_id" : '1sWu0OAL03N7zeg3aB6_1sZQYQbn4uhw7MtCRa0VHy1s',
        "birthday"  : False,
    },
    {
        "ministry"  : '316B-Greeters 9:00A',
        "gsheet_id" : '11O1G4E9cVoDYKsG4ymVn68E77PgFWJnyK_FaU28F0vk',
        "birthday"  : False,
    },
    {
        "ministry"  : '316C-Greeters 11:30A',
        "gsheet_id" : '1JbBRo3DXs1bK3D_TkjRCJUVL_SF660V9YcsudDzm8cs',
        "birthday"  : False,
    },

    {
        "ministry"  : '317-Instrumentalists & Cantors',
        "gsheet_id" : '1YP3sC4dcOWH9Li1rJV8D5FI9mef50xvxqOf6K1K54_U',
        "birthday"  : True,
    },

    {
        "ministry"  : [ '318-Lectors  MASTER LIST',
                        '318A-Lector Ministry  5:30P',
                        '318B-Lector  Ministry 9:00A',
                        '318C-Lector Ministry 11:30A',
                        '318D-Lector Ministry  Spanish' ],
        "name"      : "318-Lectors Ministry (all masses)",
        "gsheet_id" : '1X796X7_wFZmYoKMzGnj2BFFCOeoncIEILv1cmq_CJB8',
        "birthday"  : False,
    },
    {
        "ministry"  : '318A-Lector Ministry  5:30P',
        "gsheet_id" : '1_it-a1Zl2zyWBXSwu_IfGbwbZgd0OUCJdhGtBJzNBXY',
        "birthday"  : False,
    },
    {
        "ministry"  : '318B-Lector  Ministry 9:00A',
        "gsheet_id" : '16OmohVR9zSPF68PyNgY8VV1oTzSeFyXGY7cK4dSuNnE',
        "birthday"  : False,
    },
    {
        "ministry"  : '318C-Lector Ministry 11:30A',
        "gsheet_id" : '1nKE13crOa20BaDjbmgWWRq3oklY_lkNvuHS-3X1-Rro',
        "birthday"  : False,
    },
    {
        "ministry"  : '318D-Lector Ministry  Spanish',
        "gsheet_id" : '1FZDzEquDfhTHUY2_YGR15a05gYkgIzuNR4NaDY1zyB4',
        "birthday"  : False,
    },

    {
        "ministry"  : '451-Livestream Team Ministry',
        "gsheet_id" : '1Yku0IFuIKZCeUNGB5c_Ser_geYkylC2o1tiVfaNwkx8',
        "birthday"  : False,
    },

    {
        "ministry"  : '600-Men of Epiphany',
        "gsheet_id" : '11LCDr-Vc3jyeKh5nrd49irscdvTv3TDXhpOoFWlohgs',
        "birthday"  : False,
    },
    {
        "ministry"  : '601-Sages (for 50 yrs. +)',
        "gsheet_id" : '1-uvQO5RRf0K6NJlR_4Mijygn4XGk0zhvowdflKLoEUc',
        "birthday"  : False,
    },

    {
        "ministry"  : '700-Advocates for Common Good',
        "gsheet_id" : '1Iz8hz7NAhh9-dVMiC7mL8yYFi_qmM_ayB5IXhJU0uPw',
        "birthday"  : False,
    },
    {
        "ministry"  : '710-Environmental Concerns',
        "gsheet_id" : '1jsoRxugVwXi_T2IDq9J-mEVdzS8xaOk9kuXGAef-YaQ',
        "birthday"  : False,
    },
    {
        "ministry"  : '711-Hispanic Ministry Team',
        "gsheet_id" : '1zUJLVRkzS79uVQYgMkA9YaUfSFrY4Wax0ys5jSfpkEg',
        "birthday"  : False,
    },
    {
        "ministry"  : '803-Youth Ministry AdultMentor',
        "gsheet_id" : '1jzg9jRNUrjb9CeMRC23d4pkr2CQOUQNaOgL-EMDXOW4',
        "birthday"  : False,
    },
]

####################################################################

def write_xlsx(members, ministry, name, want_birthday, log):
    # Make the microseconds be 0, just for simplicity
    now = datetime.now()
    us = timedelta(microseconds=now.microsecond)
    now = now - us

    timestamp = ('{year:04}-{mon:02}-{day:02} {hour:02}:{min:02}'
                .format(year=now.year, mon=now.month, day=now.day,
                        hour=now.hour, min=now.minute))
    filename_base = name
    if filename_base is None:
        filename_base = ministry
    filename_base = filename_base.replace("/", "-")
    filename = (f'{filename_base} members as of {timestamp}.xlsx')

    # Put the members in a sortable form (they're currently sorted by MID)
    sorted_members = dict()
    for m in members:
        # 'Name' will be "Last,First..."
        sorted_members[m['Name']] = m

    wb = Workbook()
    ws = wb.active

    # Title rows + set column widths
    title_font = Font(color='FFFF00')
    title_fill = PatternFill(fgColor='0000FF', fill_type='solid')
    title_align = Alignment(horizontal='center')

    last_col = 'C'
    if want_birthday:
        last_col = 'D'

    row = 1
    ws.merge_cells(f'A{row}:{last_col}{row}')
    cell = f'A{row}'
    ws[cell] = f'Ministry: {name}'
    ws[cell].fill = title_fill
    ws[cell].font = title_font

    row = row + 1
    ws.merge_cells(f'A{row}:{last_col}{row}')
    cell = f'A{row}'
    ws[cell] = f'Last updated: {now}'
    ws[cell].fill = title_fill
    ws[cell].font = title_font

    row = row + 1
    ws.merge_cells(f'A{row}:{last_col}{row}')
    cell = f'A{row}'
    ws[cell] = ''
    ws[cell].fill = title_fill
    ws[cell].font = title_font

    row = row + 1
    columns = [(f'A{row}', 'Member name', 30),
               (f'B{row}', 'Address', 30),
               (f'C{row}', 'Phone / email', 50)]
    if want_birthday:
        columns.append((f'D{row}', 'Birthday', 30))

    for cell,value,width in columns:
        ws[cell] = value
        ws[cell].fill = title_fill
        ws[cell].font = title_font
        ws[cell].alignment = title_align
        ws.column_dimensions[cell[0]].width = width

    # Freeze the title row
    row = row + 1
    ws.freeze_panes = ws[f'A{row}']

    #---------------------------------------------------------------------

    def _append(row, col, value):
        if value is None or len(value.strip()) == 0:
            return row

        _ = ws.cell(row=row, column=col, value=value)
        return row + 1

    # Data rows
    for name in sorted(sorted_members):
        m = sorted_members[name]
        # The name will take 1 row
        _ = ws.cell(row=row, column=1, value=m['email_name'])

        # The address will take multiple rows
        col = 2
        last_row = row
        f = m['family']
        last_row = _append(col=col, row=last_row, value=f['StreetAddress1'])
        last_row = _append(col=col, row=last_row, value=f['StreetAddress2'])
        val = '{cs}, {zip}'.format(cs=f['city_state'], zip=f['StreetZip'])
        last_row = _append(col=col, row=last_row, value=val)
        addr_last_row = last_row

        # The phone / email may be more than 1 row
        col = 3
        last_row = row
        key = 'phones'
        if key in m:
            for phone in m[key]:
                # Skip unlisted phone numbers
                if phone['unlisted']:
                    log.info("SKIPPED UNLISTED NUMBER FOR {n}".format(n=m['full_name']))
                    continue

                val = '{ph} {type}'.format(ph=phone['number'], type=phone['type'])
                last_row = _append(col=col, row=last_row, value=val)

        # If we have any preferred emails, list them all
        key = 'preferred_emails'
        if key in m and len(m[key]) > 0:
            for email in m[key]:
                last_row = _append(col=col, row=last_row, value=email['EMailAddress'])
                email_last_row = last_row

        # If we have no preferred emails, list the first alphabetic
        # non-preferred email
        else:
            key = 'non_preferred_emails'
            if key in m and len(m[key]) > 0:
                emails   = sorted([x['EMailAddress'] for x in m[key]])
                last_row = _append(col=col, row=last_row,
                                   value=emails[0])
                email_last_row = last_row

        # The birthday will only be 1 row
        if want_birthday:
            col = 4
            key1 = 'MonthOfBirth'
            key2 = 'DayOfBirth'
            if key1 in m and key2 in m:
                birthday = '{m} {d}'.format(m=m[key1], d=m[key2])
                # Sometimes PDS has "None" in one of these two fields
                if 'None' not in birthday:
                    _append(col=col, row=row, value=birthday)

        # Between the address / phone+email, find the real last row
        last_row = max(email_last_row, addr_last_row)
        row = last_row + 1

    #---------------------------------------------------------------------

    wb.save(filename)
    log.info(f'Wrote {filename}')

    return filename

#-------------------------------------------------------------------

@retry.Retry(predicate=Google.retry_errors)
def upload_overwrite(filename, google, file_id, log):
    # Strip the trailing ".xlsx" off the Google Sheet name
    gsheet_name = filename
    if gsheet_name.endswith('.xlsx'):
        gsheet_name = gsheet_name[:-5]

    try:
        log.info('Uploading file update to Google file ID "{id}"'
              .format(id=file_id))
        metadata = {
            'name'     : gsheet_name,
            'mimeType' : Google.mime_types['sheet'],
            'supportsAllDrives' : True,
            }
        media = MediaFileUpload(filename,
                                mimetype=Google.mime_types['sheet'],
                                resumable=True)
        file = google.files().update(body=metadata,
                                     fileId=file_id,
                                     media_body=media,
                                     supportsAllDrives=True,
                                     fields='id').execute()
        log.debug('Successfully updated file: "{filename}" (ID: {id})'
              .format(filename=filename, id=file['id']))

    except Exception as e:
        # When errors occur, we do want to log them.  But we'll re-raise them to
        # let an upper-level error handler handle them (e.g., retry.Retry() may
        # actually re-invoke this function if it was a retry-able Google API
        # error).
        log.error('Google file update failed for some reason:')
        log.error(e)
        raise e

#-------------------------------------------------------------------

def create_roster(pds_members, ministry_entry, google, log):
    ministry      = ministry_entry['ministry']
    gsheet_id     = ministry_entry['gsheet_id']
    birthday      = ministry_entry['birthday']

    if type(ministry) is list:
        ministries = ministry
    else:
        ministries = [ ministry ]

    name = None
    key = 'name'
    if key in ministry_entry:
        name = ministry_entry[key]

    # Find the members
    members = PDSChurch.filter_members_on_ministries(pds_members, ministries)
    if members is None or len(members) == 0:
        log.info("No members in ministry: {min}".format(min=ministry))
        return

    # PDSChurch.filter_members() returns a dict.  Turn this into a simple
    # list of Members.
    members = [ x for x in members.values() ]

    # Make an xlsx
    filename = write_xlsx(members=members, ministry=ministry, name=name,
                          want_birthday=birthday, log=log)
    log.debug("Wrote temp XLSX file: {f}".format(f=filename))

    # Upload the xlsx to Google
    upload_overwrite(filename=filename, google=google, file_id=gsheet_id,
                     log=log)
    log.debug("Uploaded XLSX file to Google")

    # Remove the temp local XLSX file
    try:
        os.unlink(filename)
        log.debug("Unlinked temp XLSX file")
    except Exception as e:
        log.info("Failed to unlink temp XLSX file!")
        log.error(e)

####################################################################

def setup_cli_args():
    tools.argparser.add_argument('--logfile',
                                 help='Also save to a logfile')
    tools.argparser.add_argument('--debug',
                                 action='store_true',
                                 default=False,
                                 help='Be extra verbose')

    tools.argparser.add_argument('--sqlite3-db',
                                 required=True,
                                 help='Location of PDS sqlite3 database')

    global gapp_id
    tools.argparser.add_argument('--app-id',
                                 default=gapp_id,
                                 help='Filename containing Google application credentials')
    global guser_cred_file
    tools.argparser.add_argument('--user-credentials',
                                 default=guser_cred_file,
                                 help='Filename containing Google user credentials')

    args = tools.argparser.parse_args()

    return args

####################################################################
#
# Main
#
####################################################################

def main():
    args = setup_cli_args()

    log = ECC.setup_logging(info=True,
                            debug=args.debug,
                            logfile=args.logfile)

    log.info("Reading PDS data...")
    (pds, pds_families,
     pds_members) = PDSChurch.load_families_and_members(filename=args.sqlite3_db,
                                                        parishioners_only=False,
                                                        log=log)

    apis = {
        'drive' : { 'scope'       : Google.scopes['drive'],
                    'api_name'    : 'drive',
                    'api_version' : 'v3', },
    }
    services = GoogleAuth.service_oauth_login(apis,
                                              app_json=args.app_id,
                                              user_json=args.user_credentials,
                                              log=log)
    google = services['drive']

    for ministry in ministries:
        create_roster(pds_members=pds_members,
                      ministry_entry=ministry,
                      google=google,
                      log=log)

    # All done
    pds.connection.close()

if __name__ == '__main__':
    main()
