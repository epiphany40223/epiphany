#!/usr/bin/env python3

# Basic script to create a list of all PDS trainings of a given type.

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

from datetime import date
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

trainings   = [
    {
        "title"     : 'Cup and Plate',
        "gsheet_id" : '1zWsmd5wnyVLwGRjBRX-wEe6xxJL2Bt0NLQAJBdDk4a0',
        'pds_type'  : 'Cup and Plate training',
    },
]

def pretty_member(member):
    phones = list()
    key = 'phones'
    if key in member:
        for phone in member[key]:
            if phone['unlisted']:
                continue

            val = '{ph} {type}'.format(ph=phone['number'], type=phone['type'])
            phones.append(val)

    email = PDSChurch.find_any_email(member)[0]

    m = {
        'mid'       :   member['MemRecNum'],
        'name'      :   member['first']+' '+member['last'],
        'phones'    :   phones,
        'email'     :   email,}
    
    return m

def find_training(pds_members, training_to_find):
    def _dt_to_int(datetime):
        return 1000000*datetime.month + 10000*datetime.day + datetime.year
    
    out = dict()
    reqcount = 0

    for m in pds_members.values():
        key = 'requirements'
        if key not in m:
            continue

        for req in m[key]:
            if(req['description'] != training_to_find):
                continue
            reqcount += 1
            mem = pretty_member(m)
            sd = req['start_date']
            ed = req['end_date']
            mid = mem['mid']
            if sd not in out:
                out[sd] = dict()
            if ed not in out[sd]:
                out[sd][ed] = dict()
            if mid not in out[sd][ed]:
                out[sd][ed][mid] = list()
            out[sd][ed][mid].append({
                'mid'           :   mid,
                'name'          :   mem['name'],
                'phone'         :   mem['phones'][0],
                'email'         :   mem['email'],
                'description'   :   req['description'],
                'start_date'    :   sd,
                'end_date'      :   ed,
                'result'        :   req['result'],
                'note'          :   req['note'],
            })
            #print(m['first']+' '+m['last']+": "+str(recent['end_date']))
    
    print(f"Found {reqcount} training records")
    return out

def write_xlsx(members, title):
    now = datetime.now()
    us = timedelta(microseconds=now.microsecond)
    now = now - us

    timestamp = ('{year:04}-{mon:02}-{day:02} {hour:02}:{min:02}'
                .format(year=now.year, mon=now.month, day=now.day,
                        hour=now.hour, min=now.minute))
    filename = (f'{title} trainings as of {timestamp}.xlsx')

    wb = Workbook()
    ws = wb.active

    # Title rows + set column widths
    title_font = Font(color='FFFF00')
    title_fill = PatternFill(fgColor='0000FF', fill_type='solid')
    title_align = Alignment(horizontal='center')

    last_col = 'F'
    
    row = 1
    ws.merge_cells(f'A{row}:{last_col}{row}')
    cell = f'A{row}'
    ws[cell] = f'Training: {title}'
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
    columns = [(f'A{row}', 'Member Name', 30),
               (f'B{row}', 'Phone Number', 50),
               (f'C{row}', 'Email Address', 50),
               (f'D{row}', 'Result', 50),
               (f'E{row}', 'Notes', 50)]
    
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
        if value is None or len(value) == 0:
            return

        _ = ws.cell(row=row, column=col, value=value)

    # Data rows
    for sd in sorted(members, reverse=True):
        for ed in sorted(members[sd]):
            _ = ws.cell(row=row, column=1, value=f'Start Date: {sd}')
            ws.cell(row, 1).fill = PatternFill(fgColor='FFFF00', fill_type='solid')
            _ = ws.cell(row=row, column=2, value=f'End Date: {ed}')
            ws.cell(row, 2).fill = PatternFill(fgColor='FFFF00', fill_type='solid')

            row += 1

            
            for mid in sorted(members[sd][ed]):
                for entry in members[sd][ed][mid]:

                    col = 1
                    _append(col=col, row=row, value=entry['name'])

                    col += 1
                    _append(col=col, row=row, value=entry['phone'])
                
                    col += 1
                    _append(col=col, row=row, value=entry['email'])

                    col +=1
                    _append(col=col, row=row, value=entry['result'])
                
                    col += 1
                    _append(col=col, row=row, value=entry['note'])
                
                    row += 1
    
    #--------------------------------------------------------------------------

    wb.save(filename)
    print(f'Wrote {filename}')

    return filename


#---------------------------------------------------------------------------

def create_roster(pds_members, training, google, log):
    # Find training logs
    members = find_training(pds_members=pds_members,
                      training_to_find=training['pds_type'])
    if members is None or len(members) == 0:
        print("No trainings of type: {train}".format(train=training['title']))
    
    # Create xlsx file
    filename = write_xlsx(members=members, title=training['title'])
    print("Wrote temp XLSX file: {f}".format(f=filename))

    # Upload xlsx to Google
    upload_overwrite(filename=filename, google=google, file_id=training['gsheet_id'],
                     log=log)
    log.debug("Uploaded XLSX file to Google")

    # Remove temp local xlsx file
    try:
        os.unlink(filename)
        log.debug("Unlinked temp XLSX file")
    except:
        log.info("Failed to unlink temp XLSX file!")
        log.error(traceback.format_exc())

#---------------------------------------------------------------------------

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

    except:
        log.error('Google file update failed for some reason:')
        log.error(traceback.format_exc())
        exit(1)

#------------------------------------------------------------------
        
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

#-------------------------------------------------------------------

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

    for training in trainings:
        create_roster(pds_members=pds_members,
                      training=training,
                      google=google,
                      log=log)

    # All done
    pds.connection.close()

main()
