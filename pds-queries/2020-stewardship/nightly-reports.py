#!/usr/bin/env python3

# These are needed for the PDF graph that is created for the
# statistics report.
#
# NOTE: This comment is left over from using matplotlib for Mercy
# scripts, which used animation.  The pip3-installed version of
# matplotlib didn't handle animation properly.  But we're not using
# animation here in the Epiphany reports, so pip3 installing
# matplotlib may be sufficient...?  Certainly don't need ffmpeg.
#
# MacOS:
# brew install libpng freetype pkg-config ffmpeg
# *** PER ABOVE: probably don't need ffmpeg?
#
# Centos 7:
# sudo yum install -y freetype freetype-devel
#
# Do not install matplotlib from pip3 -- it won't have the Right Things for
# animation (which may not matter for this script, but this is left over from
# the Mercy scripts where animation matplotlib features were used).  Instead,
# build it manually:
#
# git clone git@github.com:matplotlib/matplotlib.git
# cd matplotlib
# python3.6 -mpip install .
#
# *** PER ABOVE: Probably sufficient to pip3 install matplotlib...?

import sys
sys.path.insert(0, '../../python')

import collections
import traceback
import datetime
import argparse
import smtplib
import csv
import os
import re

import ECC
import Google
import PDSChurch
import GoogleAuth

import helpers

from pprint import pprint
from pprint import pformat
from datetime import datetime
from datetime import timedelta

from oauth2client import tools
from googleapiclient.http import MediaFileUpload
from email.message import EmailMessage

import matplotlib
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

#------------------------------------------------------------------------------

from constants import jotform_member_ministries
from constants import jotform_ministry_groups
from constants import jotform_member_fields
from constants import jotform_family_fields
from constants import already_submitted_fam_status

from constants import gapp_id
from constants import guser_cred_file
from constants import jotform_member_gfile_id
from constants import jotform_family_gfile_id
from constants import upload_team_drive_folder_id
from constants import gsheet_editors

from constants import ministry_start_date
from constants import ministry_end_date

from constants import title
from constants import stewardship_begin_date
from constants import stewardship_end_date

from constants import smtp_server
from constants import smtp_from

from constants import email_image_url
from constants import api_base_url

##############################################################################

ecc = '@epiphanycatholicchurch.org'

# Comments report email
comments_email_to = 'erin{ecc},mary{ecc},jeff@squyres.com'.format(ecc=ecc)
comments_email_subject = 'Comments report'

# Statistics report email
statistics_email_to = 'erin{ecc},mary{ecc},jeff@squyres.com'.format(ecc=ecc)
statistics_email_subject = 'Statistics report'

# Pledge results email
# JMS: Lynne, ?Mary?
pledge_email_to = 'jsquyres@gmail.com'
pledge_email_subject = 'Pledge results'

# Ministry results email
# JMS: Maria, ?Mary?
ministry_email_to = 'jsquyres@gmail.com'
ministry_email_subject = 'Ministry results'

# FID participation email
fid_participation_email_to = 'jsquyres@gmail.com'
fid_participation_subject = 'Family Overall Participation results'

# JMS for debugging/testing
#statistics_email_to = 'jsquyres@gmail.com'
#comments_email_to = 'jsquyres@gmail.com'


##############################################################################

def upload_to_gsheet(google, folder_id, filename, fieldnames, csv_rows, remove_csv, log):
    if csv_rows is None or len(csv_rows) == 0:
        return None, None

    # First, write out a CSV file
    csv_filename = filename
    try:
        os.remove(csv_filename)
    except:
        pass

    csvfile = open(csv_filename, 'w')
    writer  = csv.DictWriter(csvfile, fieldnames=fieldnames,
                            quoting=csv.QUOTE_ALL)
    writer.writeheader()
    for row in csv_rows:
        writer.writerow(row)
    csvfile.close()

    # Now upload that file to Google Drive
    try:
        log.info('Uploading file to google "{file}"'
              .format(file=filename))
        metadata = {
            'name'     : filename,
            'mimeType' : Google.mime_types['sheet'],
            'parents'  : [ folder_id ],
            'supportsTeamDrives' : True,
            }
        media = MediaFileUpload(csv_filename,
                                mimetype=Google.mime_types['sheet'],
                                resumable=True)
        file = google.files().create(body=metadata,
                                     media_body=media,
                                     supportsTeamDrives=True,
                                     fields='id').execute()
        log.debug('Successfully uploaded file: "{filename}" (ID: {id})'
              .format(filename=filename, id=file['id']))

    except:
        log.error('Google upload failed for some reason:')
        log.error(traceback.format_exc())
        exit(1)

    # Set permissions on the GSheet to allow the stewardship 2020
    # workers group to edit the file (if you are view-only, you
    # can't even adjust the column widths, which will be
    # problematic for the comments report!).
    try:
        perm = {
            'type': 'group',
            'role': 'writer',
            'emailAddress': gsheet_editors,
        }
        out = google.permissions().create(fileId=file['id'],
                                          supportsTeamDrives=True,
                                          sendNotificationEmail=False,
                                          body=perm,
                                          fields='id').execute()
        log.debug("Set Google permission for file: {id}"
                 .format(id=out['id']))
    except:
        log.error('Google set permission failed for some reason:')
        log.error(traceback.format_exc())
        exit(1)

    # Remove the temp file when we're done
    if remove_csv:
        try:
            os.remove(csv_filename)
            csv_filename = None
        except:
            pass

    return file['id'], csv_filename

##############################################################################

def _change(label, old_value, new_value, message):
    return {
        'label'     : label,
        'old_value' : old_value,
        'new_value' : new_value,
        'message'   : message,
    }

def _compare(changes, label, jot_value, pds_value):
    if jot_value is None:
        jot_value = ''
    if pds_value is None:
        pds_value = ''

    if jot_value.strip() == pds_value.strip():
        return

    message = ('{label}: {new_value}'
               .format(label=label, new_value=jot_value))
    changes.append(_change(label=label,
                           old_value=pds_value,
                           new_value=jot_value,
                           message=message))

##############################################################################

def comments_to_csv(google, jotform_data, id_field, name_field, env_field, type, output, log):
    field = "Comments"

    for row in jotform_data:
        if field not in row:
            continue

        # Skip the title row
        value = row[field].strip()
        if value == field:
            continue

        # Skip if the comments are empty
        if value == '':
            continue

        output.append({
            'Date'            : row['SubmitDate'],
            'PDS internal ID' : row[id_field],
            'Envelope'        : "'" + row[env_field],
            'Type'            : type,
            'Name'            : row[name_field],
            'Comments'        : row[field],
        })

def comments_report(google, start, end, time_period, jotform_ministry, jotform_pledge, log):
    log.info("Composing comments report...")

    # Examine both jotforms and see if there are any comments that
    # need to be reported
    data = list()
    comments_to_csv(google, jotform_data=jotform_ministry,
                    id_field='mid', name_field='Name',
                    env_field='EnvId',
                    type='Member', output=data, log=log)

    # If there were member comments, make a blank line to separate
    # them from any possible pledge comments.
    blank_line = 0
    if len(data) > 0:
        blank_line = 1
        fieldnames = data[0].keys()
        dummy = dict()
        for field in fieldnames:
            dummy[field] = ''
        data.append(dummy)

    comments_to_csv(google, jotform_data=jotform_pledge,
                    id_field='fid', name_field='Names',
                    env_field='EnvId',
                    type='Family', output=data, log=log)

    # If we have any comments, upload them to a Gsheet
    gsheet_id = None
    if len(data) > 0:
        # The field names are in data[0].keys(), but we want a
        #specific, deterministic ordering of the fields.  So hard-code
        #them here.
        fieldnames = [
            'Date',
            'PDS internal ID',
            'Type',
            'Envelope',
            'Name',
            'Comments',
        ]
        filename = 'Comments {t}.csv'.format(t=time_period)
        gsheet_id, _ = upload_to_gsheet(google,
                                        folder_id=upload_team_drive_folder_id,
                                        filename=filename,
                                        fieldnames=fieldnames,
                                        csv_rows=data,
                                        remove_csv=True,
                                        log=log)

    # Send the comments report email
    body = list()
    body.append("""<html>
<body>
<h2>{title} comments report</h2>

<h3>Time period: {time_period}</h3>"""
               .format(title=title, time_period=time_period))

    if len(data) == 0:
        body.append("<p>No comments submitted during this time period.</p>")
    else:
        url = 'https://docs.google.com/spreadsheets/d/{id}'.format(id=gsheet_id)
        body.append("""<p><a href="{url}">Link to Google sheet containing comments for this timeframe</a>.</p>
<p>There are {num} comments in this report.</p>"""
                     .format(url=url, num=len(data) - blank_line))

    body.append("""
</body>
</html>""")

    to = comments_email_to
    subject = '{subj} ({t})'.format(subj=comments_email_subject, t=time_period)
    try:
        log.info('Sending "{subject}" email to {to}'
                 .format(subject=subject, to=to))
        with smtplib.SMTP_SSL(host=smtp_server) as smtp:
            msg = EmailMessage()
            msg['Subject'] = subject
            msg['From'] = smtp_from
            msg['To'] = to
            msg.set_content('\n'.join(body))
            msg.replace_header('Content-Type', 'text/html')

            smtp.send_message(msg)
    except:
        print("==== Error with {email}".format(email=to))
        print(traceback.format_exc())

##############################################################################

def statistics_compute(pds_families, jotform_ministry, jotform_pledge, log):
    ret = dict()

    # Total number of active Families in the parish
    ret['num_active'] = len(pds_families)

    #---------------------------------------------------------------

    # Number of active Families who are eligible for electronic stewardship
    # (i.e., we have an email address for the spouse and/or HoH)

    eligible = dict()
    for fid, f in pds_families.items():
        for m in f['members']:
            if helpers.member_is_hoh_or_spouse(m):
                em = PDSChurch.find_any_email(m)
                if len(em) == 0:
                    continue
                eligible[fid] = True
                continue

    ret['num_eligible'] = len(eligible)

    #-----------------------------------------------------------

    # Make quick lookup dictionaries for which MIDs and FIDs have
    # submitted for use below.
    ministry_submitted = dict()
    for row in jotform_ministry:
        if row['mid'] == 'mid':
            continue # Skip title row

        mid = int(row['mid'])
        ministry_submitted[mid] = True

    pledge_submitted = dict()
    for row in jotform_pledge:
        if row['fid'] == 'fid':
            continue # Skip title row

        fid = int(row['fid'])
        pledge_submitted[fid] = True

    #-----------------------------------------------------------

    # Compute number of a) at least partial household submissions
    # and b) completed household submissions.  While here, also
    # count families that have either started *or* have the
    # "already done" PDS Family status (i.e., the union count of
    # these two).
    ret['num_started'] = 0
    ret['num_completed'] = 0
    ret['num_started_or_asfs'] = 0
    ret['num_completed_or_asfs'] = 0

    for fid, f in pds_families.items():
        member_ministries_done = True
        for m in f['members']:
            mid = m['MemRecNum']
            if mid not in ministry_submitted:
                member_ministries_done = False
                break

        family_pledge_done = True
        if fid not in pledge_submitted:
            family_pledge_done = False

        if member_ministries_done or family_pledge_done:
            ret['num_started'] += 1
        if member_ministries_done and family_pledge_done:
            ret['num_completed'] += 1

        done_status = False
        if 'status' in f and f['status'] == already_submitted_fam_status:
            done_status = True

        if member_ministries_done or family_pledge_done or done_status:
            ret['num_started_or_asfs'] += 1
        if (member_ministries_done and family_pledge_done) or done_status:
            ret['num_completed_or_asfs'] += 1

    #-----------------------------------------------------------

    # Number of Families with the "completed" PDS Family status
    ret['num_asfs'] = 0
    for f in pds_families.values():
        if 'status' in f and f['status'] == already_submitted_fam_status:
            ret['num_asfs'] += 1

    #-----------------------------------------------------------

    return ret

#------------------------------------------------------------------------

def statistics_graph(pds_members, pds_families, jotform_ministry, jotform_pledge, log):
    def _find_range(data, earliest, latest):
        for row in data:
            submitted = row['SubmitDate']
            submitted_dt = helpers.jotform_date_to_datetime(submitted)
            if submitted_dt < earliest:
                earliest = submitted_dt
            if submitted_dt > latest:
                latest = submitted_dt

        return earliest, latest

    #------------------------------------------------------------------------

    def _compute(start, end, pds_members, pds_families,
                 jotform_ministry, jotform_pledge, log):
        ret = dict()

        # Compute these values just in the date range:
        # - How many ministry submissions?
        # - How many pledge submissions?
        # - How many families started?
        # - How many families completed?

        family_submitted = dict()
        ministry_submitted = dict()
        for row in jotform_ministry:
            if row['mid'] == 'mid':
                continue # Skip title row

            # Is this row in our date range?
            dt = helpers.jotform_date_to_datetime(row['SubmitDate'])
            if dt < start or dt > end:
                continue

            mid = int(row['mid'])

            # Make sure the member hasn't been deleted
            if mid not in pds_members:
                continue

            ministry_submitted[mid] = True

            fid = pds_members[mid]['family']['FamRecNum']
            family_submitted[fid] = True

        pledge_submitted = dict()
        for row in jotform_pledge:
            if row['fid'] == 'fid':
                continue # Skip title row

            # Is this row in our date range?
            dt = helpers.jotform_date_to_datetime(row['SubmitDate'])
            if dt < start or dt > end:
                continue

            fid = int(row['fid'])

            # Make sure the family hasn't been deleted
            if fid not in pds_families:
                continue

            pledge_submitted[fid] = True
            family_submitted[fid] = True

        ret['num_ministry_submissions'] = len(ministry_submitted)
        ret['num_pledge_submissions'] = len(pledge_submitted)
        ret['num_families_started'] = len(family_submitted)

        #...........................

        ret['num_families_completed'] = 0
        for fid, f in pds_families.items():
            member_ministries_done = True
            for m in f['members']:
                mid = m['MemRecNum']
                if mid not in ministry_submitted:
                    member_ministries_done = False
                    break

            family_pledge_done = True
            if fid not in pledge_submitted:
                family_pledge_done = False

            if member_ministries_done and family_pledge_done:
                ret['num_families_completed'] += 1

        return ret

    #------------------------------------------------------------------------

    earliest = datetime(year=9999, month=12, day=31)
    latest   = datetime(year=1971, month=1,  day=1)
    earliest, latest = _find_range(jotform_ministry, earliest, latest)
    earliest, latest = _find_range(jotform_pledge, earliest, latest)

    log.info("Earliest: {dt}".format(dt=earliest))
    log.info("Latest:   {dt}".format(dt=latest))

    one_day = timedelta(days=1)

    day = earliest

    dates = list()
    data_ministry = list()
    data_pledge = list()
    data_family_starts = list()
    data_family_completions = list()
    data_family_completions_per_day = list()

    # Make lists that we can give to matplotlib for plotting
    while day <= latest:
        data_one_day = _compute(day, day + one_day,
                                pds_members, pds_families,
                                jotform_ministry, jotform_pledge, log)
        data_cumulative = _compute(earliest, day + one_day,
                                   pds_members, pds_families,
                                   jotform_ministry, jotform_pledge, log)

        dates.append(day.date())
        data_ministry.append(data_one_day['num_ministry_submissions'])
        data_pledge.append(data_one_day['num_pledge_submissions'])
        data_family_starts.append(data_cumulative['num_families_started'])
        data_family_completions.append(data_cumulative['num_families_completed'])
        data_family_completions_per_day.append(data_one_day['num_families_completed'])

        day += one_day


    # JMS
    print("==== CSV data")
    for i, date in enumerate(dates):
        print(f"{i},{date},{data_family_completions_per_day[i]},{data_family_completions[i]}")
    print("==== CSV data")
    exit(1)


    # Make the plot
    fig, ax = plt.subplots()

    # The X label of "days" is obvious, there's no good Y label since we have
    # multiple lines
    n = datetime.now()
    hour = n.hour if n.hour > 0 else 12
    ampm = 'am' if n.hour < 12 else 'pm'
    plt.title("As of {month} {day}, {year} at {hour}:{min:02}{ampm}"
            .format(month=n.strftime("%B"), day=n.day, year=n.year,
                    hour=hour, min=n.minute, ampm=ampm))
    plt.suptitle(title + " submissions statistics")

    ax.plot(dates, data_ministry, label='Ministry submissions per day')
    ax.plot(dates, data_pledge, label='Pledge submissions per day')
    ax.plot(dates, data_family_starts, label='Cumulative family starts')
    ax.plot(dates, data_family_completions, label='Cumulative family completions')

    ax.get_xaxis().set_major_locator(mdates.DayLocator(interval=1))
    ax.get_xaxis().set_major_formatter(mdates.DateFormatter("%a %b %d"))
    plt.setp(ax.get_xticklabels(), rotation=20, ha="right",
             rotation_mode="anchor")
    ax.grid()

    plt.legend(loc="upper left")

    # Make a filename based on the time that this was run
    filename = ('statistics-as-of-{year:04}-{month:02}-{day:02}-{hour:02}{min:02}{sec:02}.pdf'
                .format(year=n.year, month=n.month, day=n.day,
                        hour=n.hour, min=n.minute, sec=n.second))
    fig.savefig(filename)

    plt.close(fig)

    return filename

#-----------------------------------------------------------------------------

def statistics_report(end, pds_members, pds_families, jotform_ministry, jotform_pledge, log):
    log.info("Composing statistics report...")

    #---------------------------------------------------------------

    graph_filename = statistics_graph(pds_members, pds_families,
                                    jotform_ministry, jotform_pledge, log)
    data = statistics_compute(pds_families,
                              jotform_ministry, jotform_pledge, log)

    #---------------------------------------------------------------------

    # Send the statistics report email
    body = list()
    body.append("""<html>
<body>
<h2>{title} statistics update</h2>

<h3>Time period: through {end}</h3>
<ul>
<li> Total number of active PDS Families in the parish: {num_active:,d}</li>
<br>
<li> Number of active PDS Families eligible for electronic stewardship: {num_eligible:,d}
    <ul>
    <li>This means that we have an email address in PDS for the Head of Household and/or the Spouse of a given Family</li>
    </ul></li>
<br>
<li> Number of electronic-stewardship-eligible Families who have electronically submitted anything: {started:,d} (out of {num_eligible:,d}, or {started_percentage:.1f}%)</li>
<li> Number of electronic-stewardship-eligible Families who have electronically completed their submissions: {completed:,d} (out of {num_eligible:,d}, or {completed_percentage:.1f}%)</li>
<br>
<li> Number of active PDS Families with "{label}" status: {num_asfs:,d}</li>
<br>
<li> Number of active PDS Families who have either electronically submitted anything or have "{label}" status: {num_started_or_asfs:,d} (out of {num_active:,d}, or {num_started_or_asfs_percentage:.1f}%)
<li> Number of active PDS Families who have either electronically completed their submission or have "{label}" status: {num_completed_or_asfs:,d} (out of {num_active:,d}, or {num_completed_or_asfs_percentage:.1f}%)
</ul>
</body>
</html>"""
                       .format(title=title, end=end,
                                num_active=data['num_active'],
                                num_eligible=data['num_eligible'],
                                started=data['num_started'],
                                started_percentage=(data['num_started']/data['num_eligible']*100),
                                completed=data['num_completed'],
                                completed_percentage=(data['num_completed']/data['num_eligible']*100),
                                label=already_submitted_fam_status,
                                num_asfs=data['num_asfs'],
                                num_started_or_asfs=data['num_started_or_asfs'],
                                num_started_or_asfs_percentage=(data['num_started_or_asfs']/data['num_active']*100),
                                num_completed_or_asfs=data['num_completed_or_asfs'],
                                num_completed_or_asfs_percentage=(data['num_completed_or_asfs']/data['num_active']*100)))

    to = statistics_email_to
    time_period = "through {end}".format(end=end)
    subject = '{subj} ({t})'.format(subj=statistics_email_subject, t=time_period)
    try:
        log.info('Sending "{subject}" email to {to}'
                 .format(subject=subject, to=to))
        with smtplib.SMTP_SSL(host=smtp_server) as smtp:
            msg = EmailMessage()
            msg['Subject'] = subject
            msg['From'] = smtp_from
            msg['To'] = to
            msg.set_content('\n'.join(body))
            msg.replace_header('Content-Type', 'text/html')

            with open(graph_filename, "rb") as f:
                csv_data = f.read()
            msg.add_attachment(csv_data, maintype='application', subtype='pdf',
                            filename=graph_filename)
            os.unlink(graph_filename)

            smtp.send_message(msg)
    except:
        print("==== Error with {email}".format(email=to))
        print(traceback.format_exc())

##############################################################################

# Columns that I need
# - fid
# - Recurring Charge Name:
# - Terms / Frequency: Weekly, Biweekly, Monthly, Bimonthly, Semimonthly, Quarterly, Semiannually, Annually
# - Begin Date: 01/01/2020
# - End Date: 12/31/2020
# - Rate
# - Total pledge
def convert_pledges_to_pds_import(pds_families, jotform_pledge, log):
    def _map_to_freqrate(pledge):
        freq = pledge['2020 frequency']
        amount = float(pledge['2020 pledge'])

        if freq == 'Weekly donations':
            return 'Weekly', amount / 52
        elif freq == 'Monthly donations':
            return 'Monthly', amount / 12
        elif freq == 'Quarterly donations':
            return 'Quarterly', amount / 4
        elif freq == 'One annual donation':
            return 'Annually', amount
        else:
            return None, None

    #-------------------------------------------------------------------------

    out = list()

    for pledge in jotform_pledge:
        # Skip the title row
        if 'fid' in pledge['fid']:
            continue

        # Here's something that can happen: A family may be deleted from PDS
        # even though they submitted.  In this case, skip them.
        if int(pledge['fid']) not in pds_families:
            log.warn("WARNING: Family FID {fid} / {names} submitted a pledge, but is no longer in PDS"
                .format(fid=pledge['fid'], names=pledge['Names']))
            continue

        # If there is a $0 pledge, Per Lynne's comment, we'll
        # transform this into a $1 annual pledge -- just so that this
        # person is on the books, so to speak.
        if int(pledge['2020 pledge']) == 0:
            pledge['2020 pledge'] = 1
            pledge['2020 frequency'] = 'One annual donation'

        frequency, rate = _map_to_freqrate(pledge)

        # Round pledge value and rate to 2 decimal points, max
        rate = float(int(rate * 100)) / 100.0
        total = float(int(pledge['2020 pledge']) * 100) / 100.0

        # Use an OrderedDict to keep the fields in order
        row = collections.OrderedDict()
        row['fid'] = pledge['fid']
        row['RecChargeName'] = 'Due/Contributions'
        row['Frequency'] = frequency
        row['BeginDate'] = '{0:%m}/{0:%d}/{0:%Y}'.format(stewardship_begin_date)
        row['EndDate'] = '{0:%m}/{0:%d}/{0:%Y}'.format(stewardship_end_date)
        row['PledgeRate'] = rate
        row['TotalPledge'] = total
        row['SubmitDate'] = pledge['SubmitDate']
        row['Names'] = pledge['Names']
        row['Envelope'] = "'" + pledge['EnvId']

        out.append(row)

    return out

#-----------------------------------------------------------------------------

def family_pledge_csv_report(args, google, start, end, time_period, pds_families, jotform_pledge, log):
    pledges = convert_pledges_to_pds_import(pds_families, jotform_pledge, log)

    # If we have pledges, upload them to a Google sheet
    gsheet_id = None
    if len(pledges) > 0:
        filename = 'Family Pledge PDS import {t}.csv'.format(t=time_period)
        gsheet_id, csv_filename = upload_to_gsheet(google,
                                        folder_id=upload_team_drive_folder_id,
                                        filename=filename,
                                        fieldnames=pledges[0].keys(),
                                        csv_rows=pledges,
                                        remove_csv=False,
                                        log=log)

    # Send the statistics report email
    body = list()
    body.append("""<html>
<body>
<h2>{title} pledge update</h2>

<h3>Time period: {time_period}</h3>"""
                       .format(title=title, time_period=time_period))

    if gsheet_id:
        url = 'https://docs.google.com/spreadsheets/d/{id}'.format(id=gsheet_id)
        body.append('<p><a href="{url}">Link to Google sheet containing pledge updates for this timeframe</a>.</p>'
                     .format(url=url))
        body.append("<p>See the attachment for a CSV to import directly into PDS.</p>")
    else:
        body.append("<p>There were no pledge submissions during this timeframe.<p>")

    body.append("""</body>
</html>""")

    to = pledge_email_to
    subject = '{subj} ({t})'.format(subj=pledge_email_subject, t=time_period)
    try:
        log.info('Sending "{subject}" email to {to}'
                 .format(subject=subject, to=to))
        with smtplib.SMTP_SSL(host=smtp_server) as smtp:
            msg = EmailMessage()
            msg['Subject'] = subject
            msg['From'] = smtp_from
            msg['To'] = to
            msg.set_content('\n'.join(body))
            msg.replace_header('Content-Type', 'text/html')

            # If there were results, attach the CSV
            if gsheet_id:
                with open(filename, "rb") as f:
                    csv_data = f.read()
                msg.add_attachment(csv_data, maintype='text', subtype='csv', filename=filename)

            smtp.send_message(msg)

            if gsheet_id:
                os.unlink(filename)
    except:
        print("==== Error with {email}".format(email=to))
        print(traceback.format_exc())

##############################################################################

MINISTRY_PARTICIPATE = 1
MINISTRY_INTERESTED  = 2
MINISTRY_INACTIVE    = 3

def _convert_jotform_ministry_status(jotform_status):
    if jotform_status is None:
        return MINISTRY_INACTIVE

    if 'PARTICIPATE' in jotform_status:
        return MINISTRY_PARTICIPATE
    elif 'INTERESTED' in jotform_status:
        return MINISTRY_INTERESTED
    elif 'NO LONGER' in jotform_status:
        return MINISTRY_INACTIVE
    else:
        # Catch-all
        return MINISTRY_INACTIVE

def _status_to_str(status):
    if status == MINISTRY_PARTICIPATE:
        return 'I already participate'
    elif status == MINISTRY_INTERESTED:
        return 'I am interested'
    else:
        return 'I do not participate'

#-----------------------------------------------------------------------------

# Fields I need:
# - MID
# - Ministry
# - Status
# - Start date (from constants.py)
# - End date (from constants.py)
# Other fields requested by the staff:
# - Member nickname + last name
# - Member email addresses
# - Member phones
# - Member status on ministry
#
# Will generate several outputs:
# - Likely can be directly imported
#   - NOT PARTICIPATE -> INTERESTED
# - Likely cannot be directly imported (still need to test)
#   - PARTICPATE -> NOT PARTICIPATE
# - Needs to be examined by a human
#   - NOT PARTICIPATE -> ALREADY PARTICIPATE
#   - PARTICIPATE -> INTERESTED
def convert_ministries_to_pds_import(pds_members, jotform_ministry, log):
    def _get_pds_member_ministry_status(member, ministry_names):
        for ministry in m['active_ministries']:
            if ministry['Description'] in ministry_names:
                if ministry['active']:
                    return MINISTRY_PARTICIPATE, ministry['status']
                else:
                    return MINISTRY_INACTIVE, ministry['status']

        return MINISTRY_INACTIVE, 'Not listed in PDS'

    #-------------------------------------------------------------------------
    def _status_to_pds(status):
        if status == MINISTRY_PARTICIPATE:
            return 'Actively Involved'
        elif status == MINISTRY_INACTIVE:
            return 'No Longer Involved'
        elif status == MINISTRY_INTERESTED:
            return 'Interested'

    #-------------------------------------------------------------------------
    def _map_ministry_to_group(ministry_to_find):
        for key, group in jotform_member_ministries.items():
            for ministry in group:
                if type(ministry) is list:
                    for m in ministry:
                        if m == ministry_to_find:
                            return jotform_ministry_groups[key]
                else:
                    if ministry == ministry_to_find:
                        return jotform_ministry_groups[key]
        return None

    #-------------------------------------------------------------------------

    interested = list()
    no_longer_interested = list()
    needs_human = list()

    for row in jotform_ministry:
        # Here's something that can happen: a MID was submitted, but is no
        # longer an active member in PDS.  In that case, ignore the submission.
        mid = int(row['mid'])
        if mid not in pds_members:
            log.warn("WARNING: Member {mid} / {name} submitted ministry info, but cannot be found"
                    .format(mid=mid, name=row['Name']))
            continue

        m = pds_members[mid]
        f = m['family']

        # JMS Debug
        #if not m['Name'].startswith('Squyres,Jeff'):
        #    continue

        # For each ministry submitted, see if there was a change
        for group in jotform_member_ministries:
            for ministry_entry in jotform_member_ministries[group]:
                # Some of the ministry entries are lists because we want to treat them equivalently.
                if type(ministry_entry) is list:
                    jotform_column = ministry_entry[0]
                    ministries     = ministry_entry
                else:
                    jotform_column = ministry_entry
                    ministries     = [ ministry_entry ]

                # Get their status from Jotform
                jotform_status_str = row[jotform_column]
                jotform_status = _convert_jotform_ministry_status(jotform_status_str)

                # Get their status from PDS
                pds_status, pds_status_string = _get_pds_member_ministry_status(m, ministries)

                # If they're the same, nothing to do
                if jotform_status == pds_status:
                    continue

                ministry_group = _map_ministry_to_group(jotform_column)

                # We're going to have some form of output here, so
                # make a row.  Use an OrderedDict so that the fields
                # stay in order.
                out_row = collections.OrderedDict()
                out_row['mid'] = mid
                out_row['MinistryGroup'] = ministry_group
                out_row['Ministry'] = jotform_column
                out_row['Status'] = _status_to_pds(jotform_status)
                out_row['Name'] = row['Name']

                # If PDS INACTIVE -> INTERESTED
                if (pds_status == MINISTRY_INACTIVE and
                      jotform_status == MINISTRY_INTERESTED):
                    out_row['StartDate'] = ministry_start_date
                    interested.append(out_row)

                elif (pds_status == MINISTRY_PARTICIPATE and
                      jotform_status == MINISTRY_INACTIVE):
                    out_row['EndDate'] = ministry_end_date
                    no_longer_interested.append(out_row)

                elif (pds_status == MINISTRY_INACTIVE and
                      jotform_status == MINISTRY_PARTICIPATE):
                    out_row['Reason'] = 'PDS says inactive, but Member indicated active'
                    needs_human.append(out_row)

                elif (pds_status == MINISTRY_PARTICIPATE and
                      jotform_status == MINISTRY_INTERESTED):
                    out_row['Reason'] = 'PDS says already active, but member indicated interest'
                    needs_human.append(out_row)

                # Add additional fields as requested by the staff
                # - Whether Member's Family submitted a paper card or not
                # - Member nickname + last name
                # - Member first name
                # - Member last name
                # - Family envelope ID
                # - Member email addresses
                # - Member phones
                # - Member status on ministry
                if 'status' in f and f['status'] == already_submitted_fam_status:
                    paper = 'Submitted paper card'
                else:
                    paper = 'Electronic only'
                out_row['Submitted paper?'] = paper

                out_row['Full Name'] = m['full_name']
                out_row['First Name'] = m['first']
                out_row['Last Name'] = m['last']
                out_row['Family Envelope ID'] = "'" + f['ParKey'].strip()

                emails = list()
                key = 'preferred_emails'
                if key in m:
                    for e in m[key]:
                        emails.append(e['EMailAddress'])
                out_row['Email'] = ', '.join(emails)

                phones = list()
                text = ''
                key = 'phones'
                key2 = 'unlisted'
                if key in m:
                    # Is this the old member format?  Seems to be a dict of phone_id / phone_data, and no "Unlisted".  :-(
                    for p in m[key].values():
                        text = ('{num} {type}'
                                .format(num=p['number'], type=p['type']))
                        if key2 in p:
                            if p[key2]:
                                text += ' UNLISTED'
                        phones.append(text)
                out_row['Phone'] = text

                out_row['PDSMinistryStatus'] = pds_status_string

    return interested, no_longer_interested, needs_human

#-----------------------------------------------------------------------------

def member_ministry_csv_report(args, google, start, end, time_period, pds_members, jotform_ministry_csv, log):
    interested, no_longer_interested, needs_human = convert_ministries_to_pds_import(pds_members, jotform_ministry_csv, log)

    # If we have ministry update data, upload it to a Google sheet
    def _check(data, key, title):
        group = {
            'key' : key,
            'title': title,
            'data' : data,
            'gsheet_id' : None,
            'csv_filename' : None,
        }

        if len(data) > 0:
            filename = ('Individual Member Ministry Update: {title}, {t}.csv'
                    .format(t=time_period, title=title))
            gsheet_id, csv_filename = upload_to_gsheet(google,
                                        folder_id=upload_team_drive_folder_id,
                                        filename=filename,
                                        fieldnames=data[0].keys(),
                                        csv_rows=data,
                                        remove_csv=False,
                                        log=log)
            group['gsheet_id' ] = gsheet_id
            group['csv_filename'] = csv_filename

        groups.append(group)

    #-------------------------------------------------------------------------

    groups = list()
    _check(interested, 'interested', 'PDS import for Interested')
    _check(no_longer_interested, 'no_longer_interested', 'PDS import for No longer interested')
    _check(needs_human, 'needs_human', 'Needs human checking')

    #------------------------------------------------------------------------

    body = list()
    body.append("""<html>
<body>
<h2>{title} Member Ministry Participation data update</h2>
<h3>Time period: {start} through {end}</h3>
<p>Only showing results with changes compared to the data in the PDS database.</p>

<p>
<ul>"""
                       .format(title=title, start=start, end=end))

    for group in groups:
        if group['gsheet_id']:
            url = 'https://docs.google.com/spreadsheets/d/{id}'.format(id=group['gsheet_id'])
            body.append('<li><a href="{url}">Spreadsheet with {title} results</a></li>'
                    .format(url=url, title=group['title']))
        else:
            body.append("<li>No results for {title}</li>")
    body.append("</ul>")

    body.append("""</body>
</html>""")

    to = ministry_email_to
    subject = '{title} Member Ministry Participation updates ({t})'.format(title=title, t=time_period)
    try:
        log.info('Sending "{subject}" email to {to}'
              .format(subject=subject, to=to))
        with smtplib.SMTP_SSL(host=smtp_server) as smtp:
            msg = EmailMessage()
            msg['Subject'] = subject
            msg['From'] = smtp_from
            msg['To'] = to
            msg.set_content('\n'.join(body))
            msg.replace_header('Content-Type', 'text/html')

            # If there were results, attach CSV files
            for group in groups:
                if group['csv_filename']:
                    with open(group['csv_filename'], 'rb') as f:
                        csv_data = f.read()
                    msg.add_attachment(csv_data, maintype='text', subtype='csv',
                                    filename=group['csv_filename'])

            smtp.send_message(msg)

            for group in groups:
                if group['csv_filename']:
                    os.unlink(group['csv_filename'])
    except:
        print("==== Error with {email}".format(email=to))
        print(traceback.format_exc())

##############################################################################

def family_status_csv_report(args, google, start, end, time_period, pds_families, pds_members, jotform_pledge, jotform_ministry, log):
    # Simple report: FID, Family name, and constants.already_submitted_fam_status

    # Make a list of families who have submitted anything at all
    submitted = dict()
    for row in jotform_pledge:
        fid = int(row['fid'])
        if fid in pds_families:
            submitted[fid] = True
    for row in jotform_ministry:
        mid = int(row['mid'])
        if mid in pds_members:
            fid = pds_members[mid]['FamRecNum']
            if fid in pds_families:
                submitted[fid] = True

    # Did we find anything?
    if len(submitted) == 0:
        log.info("No FID Statuses to update")
        return

    # Make a dictionary of the final CSV data
    csv_data = list()
    for fid in submitted:
        last_name = pds_families[fid]['Name'].split(',')[0]
        csv_data.append({
            'fid' : fid,
            'Family Name' : pds_families[fid]['Name'],
            'Envelope ID' : pds_families[fid]['ParKey'],
            'Last Name'   : last_name,
            'Status'      : already_submitted_fam_status,
        })

    filename = ('Family Status Update: {t}.csv'
            .format(t=time_period, title=title))
    gsheet_id, csv_filename = upload_to_gsheet(google,
                                folder_id=upload_team_drive_folder_id,
                                filename=filename,
                                fieldnames=csv_data[0].keys(),
                                csv_rows=csv_data,
                                remove_csv=False,
                                log=log)
    url = 'https://docs.google.com/spreadsheets/d/{id}'.format(id=gsheet_id)

    #------------------------------------------------------------------------

    body = list()
    body.append("""<html>
<body>
<h2>Family Status data update</h2>
<h3>Time period: {start} through {end}</h3>

<p> See attached spreadsheet of FIDs that have submitted anything at all in this time period.
The same spreadsheet <a href="{url}">is also available as a Google Sheet</a>.</p>

<p> Total of {num} families.</p>
</body>
</html>"""
                   .format(start=start, end=end, url=url,
                           num=len(submitted)))

    to = fid_participation_email_to
    subject = '{title} Family Status updates ({t})'.format(title=title, t=time_period)
    try:
        log.info('Sending "{subject}" email to {to}'
              .format(subject=subject, to=to))
        with smtplib.SMTP_SSL(host=smtp_server) as smtp:
            msg = EmailMessage()
            msg['Subject'] = subject
            msg['From'] = smtp_from
            msg['To'] = to
            msg.set_content('\n'.join(body))
            msg.replace_header('Content-Type', 'text/html')

            # If there were results, attach CSV files
            with open(csv_filename, 'rb') as f:
                csv_data = f.read()
            msg.add_attachment(csv_data, maintype='text', subtype='csv',
                            filename=csv_filename)

            smtp.send_message(msg)

            os.unlink(csv_filename)
    except:
        print("==== Error with {email}".format(email=to))
        print(traceback.format_exc())

##############################################################################

# Send "thank you" emails to everyone who completed in this timeframe
def thank_you_emails(args, google, start, end, time_period, pds_families, pds_members, jotform_pledge, jotform_ministry, log):



    # JMS THIS REPORT WAS NOT COMPLETED FOR 2020 Stewardship.



    # Make quick lookup table for looking up Members who submitted a ministry update
    member_ministry_update = dict()
    for row in jotform_ministry:
        mid = int(row['mid'])
        if mid not in pds_members:
            continue
        member_ministry_update[mid] = True

    # Find Families who are complete
    completed = dict()
    for row in jotform_pledge:
        fid = int(row['fid'])
        if fid not in pds_families:
            continue

        # If we get here, it's because the Family submitted a pledge.  Now check to see if all Members in the Family have submitted a Ministry update.
        found_all = True
        f = pds_families[fid]
        for m in f['members']:
            mid = m['MemRecNum']
            if mid not in member_ministry_update:
                # At least this Member does not have a ministry member update.  We're therefore done searching this Family.
                found_all = False
                break

        if not found_all:
            continue

        # If we got here, it means the Family submission is complete
        log.info("Family {name} has completed"
                .format(name=f['Name']))
        completed[fid] = True

    #-------------------------------------------------------------------------

    # JMS AT THIS POINT WE KNOW WHO COMPLETED OVERALL
    # JMS WE STILL NEED TO KNOW WHO COMPLETED IN THE TIMEFRAME (i.e., who "new" just completed so that we can send them an email)

    #-------------------------------------------------------------------------

    with open('email-thank-you-and-survey.html', 'r') as f:
        contents = f.read()

    # JMS override
    to = 'jsquyres@gmail.com'
    # Can't use .format() because of CSS use of {}
    body = contents.replace("{family_names}", "Squyres")

    subject = 'Thank you for participating in Epiphany\'s 2020 Stewardship Drive!'
    try:
        log.info('Sending "{subject}" email to {to}'
                 .format(subject=subject, to=to))
        with smtplib.SMTP_SSL(host=smtp_server) as smtp:
            msg = EmailMessage()
            msg['Subject'] = subject
            msg['From'] = smtp_from
            msg['To'] = to
            msg.set_content(body)
            msg.replace_header('Content-Type', 'text/html')

            smtp.send_message(msg)
    except:
        print("==== Error with {email}".format(email=to))
        print(traceback.format_exc())


##############################################################################

def _export_gsheet_to_csv(service, start, end, google_sheet_id, fieldnames):
    response = service.files().export(fileId=google_sheet_id,
                                      mimeType=Google.mime_types['csv']).execute()

    # Some of the field names will be lists.  In those cases, use the first field name in the list.
    final_fieldnames = list()
    for f in fieldnames:
        if type(f) is list:
            final_fieldnames.append(f[0])
        else:
            final_fieldnames.append(f)

    csvreader = csv.DictReader(response.decode('utf-8').splitlines(),
                               fieldnames=final_fieldnames)

    rows = list()
    for row in csvreader:
        # Skip title row
        if 'Submission' in row['SubmitDate']:
            continue

        # Is this submission between start and end?
        submit_date = helpers.jotform_date_to_datetime(row['SubmitDate'])
        if submit_date < start or submit_date > end:
            continue

        rows.append(row)

    return rows

#-----------------------------------------------------------------------------

def read_jotforms(google, start, end, member_gfile_id, family_gfile_id):
    def _deduplicate(rows, field):
        index = dict()

        # Save the last row number for any given MID/FID
        # (we only really care about the *last* entry that someone makes)
        for i, row in enumerate(rows):
            index[row[field]] = i

        # Now create a new output list that has just that last row for any given
        # MID/FID
        out = list()
        for i, row in enumerate(rows):
            if index[row[field]] == i:
                out.append(row)

        return out

    #------------------------------------------------------------------------

    member_csv = _export_gsheet_to_csv(google, start, end, member_gfile_id,
                                      jotform_member_fields)
    member_csv = _deduplicate(member_csv, 'mid')

    family_csv = _export_gsheet_to_csv(google, start, end, family_gfile_id,
                                      jotform_family_fields)
    family_csv = _deduplicate(family_csv, 'fid')

    return member_csv, family_csv

##############################################################################

def setup_args():
    tools.argparser.add_argument('--gdrive-folder-id',
                                 help='If specified, upload a Google Sheet containing the results to this Team Drive folder')

    tools.argparser.add_argument('--all',
                                 action='store_const',
                                 const=True,
                                 help='If specified, run the comparison for all time (vs. running for the previous time period')

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

##############################################################################

def main():
    global families, members

    args = setup_args()
    log = ECC.setup_logging(debug=False)

    #---------------------------------------------------------------

    # Calculate the start and end of when we are analyzing in the
    # source data
    epoch = datetime(year=1971, month=1, day=1)
    end = datetime.now()
    if args.all:
        start = epoch
    else:
        # If not supplied on the command line:
        # Sun: skip
        # Mon: everything from last 3 days (Sat+Sun)
        # Tue-Fri: everything from yesterday
        # Sat: skip
        today = end.strftime('%a')
        if today == 'Sat' or today == 'Sun':
            print("It's the weekend.  Nothing to do!")
            exit(0)
        elif today == 'Mon':
            start = end - timedelta(days=3)
        else:
            start = end - timedelta(days=1)

    # JMS
    #start = datetime(year=2019, month=9, day=30)
    #end   = datetime(year=2019, month=10, day=1)

    # No one wants to see the microseconds
    start = start - timedelta(microseconds=start.microsecond)
    end   = end   - timedelta(microseconds=end.microsecond)

    if args.all:
        time_period = 'all results to date'
    else:
        time_period = '{start} - {end}'.format(start=start, end=end)

    log.info("Comments for: {tp}".format(tp=time_period))

    #---------------------------------------------------------------

    log.info("Reading PDS data...")
    (pds, pds_families,
     pds_members) = PDSChurch.load_families_and_members(filename='pdschurch.sqlite3',
                                                        log=log)

    # Remove non-parishioner families
    pds_families = helpers.filter_parishioner_families_only(pds_families)

    #---------------------------------------------------------------

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

    #---------------------------------------------------------------

    # Load all the results
    log.info("Downloading Jotform raw data...")
    jotform_ministry_all, jotform_pledge_all = read_jotforms(google, epoch, end,
                jotform_member_gfile_id, jotform_family_gfile_id)

    # Load a range of results
    if start == epoch:
        jotform_ministry_range = jotform_ministry_all.copy()
        jotform_pledge_range = jotform_pledge_all.copy()
    else:
        jotform_ministry_range, jotform_pledge_range = read_jotforms(google, start, end,
                    jotform_member_gfile_id, jotform_family_gfile_id)

    #---------------------------------------------------------------

    # Do the individual reports

    # These two reports were run via cron at 12:07am on Mon-Fri
    # mornings.
    #comments_report(google, start, end, time_period,
    #                jotform_ministry_range, jotform_pledge_range, log)
    statistics_report(end, pds_members, pds_families,
                      jotform_ministry_all, jotform_pledge_all, log)

    # These reports were uncommented and run by hand upon demand.
    #family_pledge_csv_report(args, google, start, end, time_period,
    #                         pds_families, jotform_pledge_range, log)
    #family_status_csv_report(args, google, start, end, time_period,
    #                         pds_families, pds_members,
    #                         jotform_pledge_range, jotform_ministry_range, log)
    #member_ministry_csv_report(args, google, start, end, time_period,
    #                           pds_members, jotform_ministry_range, log)

    # This report was not finished.  See the "Ideas for 2021" section
    # in README.md.  It should probably be finished and run every
    # night.
    #thank_you_emails(args, google, start, end, time_period,
    #                 pds_families, pds_members,
    #                 jotform_pledge_all, jotform_ministry_all, log)

    # Close the databases
    pds.connection.close()

main()
