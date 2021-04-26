#!/usr/bin/env python3

# Basic script to create a list of all PDS trainings of a given type.

import sys
sys.path.insert(0, '../../../python')

import os

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

import training_sheets
from training_sheets import EverythingSheet, ActiveSheet, ExpiredSheet

# Globals

gapp_id         = 'client_id.json'
guser_cred_file = 'user-credentials.json'

now = datetime.now()
us = timedelta(microseconds=now.microsecond)
now = now - us
timestamp = ('{year:04}-{mon:02}-{day:02} {hour:02}:{min:02}'
                .format(year=now.year, mon=now.month, day=now.day,
                        hour=now.hour, min=now.minute))

trainings   = [
    {
        "title"     : 'Communion Minister',
        "gsheet_id" : '1J_16q43O1sFWKuXm0uwkMtkBl9wliqplU0vnXY7fjUU',
        'pds_type'  : 'Communion Minister training',
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

    ministries = {'weekday'     :   'No',
                  'weekend'     :   'No',
                  'homebound'   :   'No',}
    key = 'active_ministries'
    if key in member:
        for ministry in member[key]:
            if ministry['Description'] == 'Weekend Communion':
                ministries['weekend'] = 'Yes'
            if ministry['Description'] == 'Weekday Communion':
                ministries['weekday'] = 'Yes'
            if ministry['Description'] == 'Homebound Communion':
                ministries['homebound'] = 'Yes'

    email = PDSChurch.find_any_email(member)[0]

    if PDSChurch.is_parishioner(member['family']):
        active = "No"
    else:
        active = "Yes"

    m = {
        'mid'       :   member['MemRecNum'],
        'name'      :   member['first']+' '+member['last'],
        'email'     :   email,
        'phones'    :   phones,
        'active'    :   active,
        'weekend'   :   ministries['weekend'],
        'weekday'   :   ministries['weekday'],
        'homebound' :   ministries['homebound']
    }
    
    return m

def pds_find_training(pds_members, training_to_find, log):
    
    out = dict()
    reqcount = 0

    for m in pds_members.values():
        key = 'requirements'
        if key not in m:
            continue

        for req in m[key]:
            if(req['description'] != training_to_find['pds_type']):
                continue
            reqcount += 1
            mem = pretty_member(m)
            sd = req['start_date']
            mid = mem['mid']
            if mid not in out:
                out[mid] = dict()
            if sd not in out[mid]:
                out[mid][sd] = list()
            out[mid][sd].append({
                'mid'           :   mid,
                'name'          :   mem['name'],
                'email'         :   mem['email'],
                'phone'         :   mem['phones'][0],
                'start_date'    :   sd,
                'end_date'      :   req['end_date'],
                'stage'         :   req['result'],
                'active'        :   mem['active'],
                'weekend'       :   mem['weekend'],
                'weekday'       :   mem['weekday'],
                'homebound'     :   mem['homebound'],
                'note'          :   req['note'],
            })
    
    if len(out) == 0:
        log.info(f"No trainings of type: {training_to_find['title']} found")
        return None
    else:    
        log.info(f"Found {reqcount} training records")
        return out

def write_xlsx(title, trainingdata, log):

    filename = (f'{title} trainings as of {timestamp}.xlsx')

    wb = Workbook()

    every = EverythingSheet(wb, trainingdata)
    every.create_roster(title)

    active = ActiveSheet(wb, trainingdata)
    active.create_roster(title)

    expired = ExpiredSheet(wb, trainingdata)
    expired.create_roster(title)

    wb.save(filename)
    log.debug(f'Wrote {filename}')

    return filename


#---------------------------------------------------------------------------

def create_roster(trainingdata, training, google, log, dry_run):
    
    # Create xlsx file
    filename = write_xlsx(training['title'], trainingdata, log)
    log.info("Wrote temp XLSX file: {f}".format(f=filename))

    # Upload xlsx to Google
    if not dry_run:
        upload_overwrite(filename=filename, google=google, file_id=training['gsheet_id'],
                        log=log)
        log.debug("Uploaded XLSX file to Google")

        # Remove temp local xlsx file
        try:
            os.unlink(filename)
            log.debug("Unlinked temp XLSX file")
        except:
            log.info("Failed to unlink temp XLSX file!")

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

    tools.argparser.add_argument('--dry-run',
                                 action='store_true',
                                 default=False,
                                 help='Do not upload to Google')

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
    google = None
    if not args.dry_run:
        services = GoogleAuth.service_oauth_login(apis,
                                                app_json=args.app_id,
                                                user_json=args.user_credentials,
                                                log=log)
        google = services['drive']

    for training in trainings:
        training_data = pds_find_training(pds_members, training, log)
        create_roster(training_data, training, google, log, args.dry_run)


    # All done
    pds.connection.close()

main()
