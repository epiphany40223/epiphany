#!/usr/bin/env python3

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
import ParishSoftv2 as ParishSoft
import GoogleAuth
import googleapiclient
from google.api_core import retry

from datetime import datetime
from datetime import timedelta

from oauth2client import tools
from googleapiclient.http import MediaFileUpload

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment

from pprint import pprint
from pprint import pformat

# Globals

gapp_id         = 'client_id.json'
guser_cred_file = 'user-credentials.json'

ministry_sheets = [
    {
        'ministry' : '100-Parish Pastoral Council',
        'gsheet_id' : '1uVeY_Asdm2LwI4sepDU7foYjuRnkK6v9c0TA1Dovp70',
        'birthday' : False,
    },
    {
        'ministry' : '102-Finance Advisory Council',
        'gsheet_id' : '1PXn7O9C1drTARng7OCppSXOMpmtucb0QDbAZHcWiNvk',
        'birthday' : False,
    },
    {
        'ministry' : '103-Worship Committee',
        'gsheet_id' : '1ZKLcIpaSiHHGjIczBnV_wjmEwMKvQXbef49KLkuRo5U',
        'birthday' : False,
    },
    {
        'ministry' : '104-Stewardship & E Committee',
        'gsheet_id' : '1MQJwX5-EP26NVzSozE8vsYL7Mu4kjUjuezGoXHDCCfs',
        'birthday' : False,
    },
    {
        'ministry' : '107-Social Resp Steering Comm',
        'gsheet_id' : '1oAtEySITBYZz0QSGzzWCk7y0XW8lHCrHgQgs7kaH5es',
        'birthday' : False,
    },
    {
        'ministry' : '108-Faith Formation Team',
        'gsheet_id' : '1Xw-U8IO7GxaE2vEJARVJSxAW3ip7keqXFfGvQ1BhWL8',
        'birthday' : False,
    },
    {
        'ministry' : '110-Ten Percent Committee',
        'gsheet_id' : '1ONQvhqV8n8o7CAeS_FpyYr4pRcXqHSv7DveKYm8GSoU',
        'birthday' : False,
    },
    {
        'ministry' : '111-Hispanic Ministry Team',
        'gsheet_id' : '16QuGaW2rOhgH4J2I0bkywpozYeTTmJk7PuzynzTMmqs',
        'birthday' : False,
    },
    {
        'ministry' : '113-Media Comms Planning Comm.',
        'gsheet_id' : '1ABFn_BSgbMssfMckGH9Ox5w9b0hVq6HClEq9Ga4fw-0',
        'birthday' : False,
    },
    {
        'ministry' : '114-Marriage Mentor Couples',
        'gsheet_id' : '17lK3pGXZn9JsljiUV61MJiZZNhBjpsK3k_K8AWHOxwE',
        'birthday' : False,
    },
    {
        'ministry' : '115-Parish Life Committee',
        'gsheet_id' : '148kNe7rTFzc0wooqZSuZw1ET82swm9v3iVKOkp--miA',
        'birthday' : False,
    },
    {
        'ministry' : '116-Youth Council',
        'gsheet_id' : '1CfTwWfK8CJSqJir_YX7jIIoR5yDrIQizB-ND6ak3pfo',
        'birthday' : False,
    },
    {
        'ministry' : '200-Audit Committee',
        'gsheet_id' : '1xCcPCh4DTyv4A-c2W8ZjOCeGDeg5qlIQ1LIPZzx2vCA',
        'birthday' : False,
    },
    {
        'ministry' : '201-Collection Counter',
        'gsheet_id' : '1QeoCYoqcd1K-NhuhdFZGPuACG6rOijRv983wnl2t1_s',
        'birthday' : False,
    },
    {
        'ministry' : '202-Facility Mgmt & Planning',
        'gsheet_id' : '1IYikt6MPnUbN0pe-pd9PMHjL0b2UR3y-de2f3qYzYSA',
        'birthday' : False,
    },
    {
        'ministry' : '203-Garden & Grounds',
        'gsheet_id' : '1zUShTo6fkxMNhfwMeegEyGYsdyPYa7EGBZzozE0LHOY',
        'birthday' : False,
    },
    {
        'ministry' : '204-Parish Office Volunteers',
        'gsheet_id' : '1jkSDHIHJkEYJ6LSLpYNB0krjid2p4NmEbQkmakAP_cA',
        'birthday' : False,
    },
    {
        'ministry' : '205-Participation Sheet Vol',
        'gsheet_id' : '105mQLE1l-XcgtzWuYZ9dCriZ3w39S6R08syOOqQhA_c',
        'birthday' : False,
    },
    {
        'ministry' : '206-Space Arrangers',
        'gsheet_id' : '1WKwSi-WoR-TuVs_V8_j7JXrXA6DHIzYYDPyXEk5bWFg',
        'birthday' : False,
    },
    {
        'ministry' : '207-Technology Committee',
        'gsheet_id' : '1YmVnRVu6t2vq8dfCJiIFwL6BVaEA7It3tOThDxzRvC0',
        'birthday' : False,
    },
    {
        'ministry' : '208-Weekend Closer',
        'gsheet_id' : '1R0UdA4rztyAYM27xrQC4Bm91X-uJ-S4j933g5j_ZRWY',
        'birthday' : False,
    },
    {
        'ministry' : '300-Art & Environment',
        'gsheet_id' : '1InZDOu7hIECcSKLwKNXBD_wC4osolhQbpTTj5Lqtfx8',
        'birthday' : False,
    },
    {
        'ministry' : '301-Audio/Visual/Light Minstry',
        'gsheet_id' : '1tcyyRQsyTMpgg1pPf1ELFkz-0fp3fg0a1dCnSrHAdGI',
        'birthday' : False,
    },
    {
        'ministry' : '303-Linens/Vestments Ministry',
        'gsheet_id' : '1YpHvnxutYveKzuT582KYrwjQTcZe9D7EczzINMUtak4',
        'birthday' : False,
    },
    {
        'ministry' : '304-LiturgicalPlanningDscrnmnt',
        'gsheet_id' : '1aQ4t65JW9sBB7c8IPsUWABXfCZG0igh6rT0Fe7g3Gd0',
        'birthday' : False,
    },
    {
        'ministry' : '305-Movers Ministry',
        'gsheet_id' : '1YrnUTfbrRYBix6XxiJlE47GCKdTC09I2EWQfSIzsHdo',
        'birthday' : False,
    },
    {
        'ministry' : '306-Music Support for Children',
        'gsheet_id' : '1KB4hrlDB5YJsLWf1tYwCO6EMmATHm2PwhzMKTz6gCkI',
        'birthday' : False,
    },
    {
        'ministry' : '307-Wedding Assistant',
        'gsheet_id' : '1k3RlmLRBlBUS5ecjRoVuS8lPDJBYR3ldvVgH_HpxZRQ',
        'birthday' : False,
    },
    {
        'ministry' : '308-Worship&Music Support Team',
        'gsheet_id' : '1Uj-gPnunVIdJmpd1REmBy9Ub4M_7qUHnqBtBct_MLNo',
        'birthday' : False,
    },
    {
        'ministry' : '309-Acolytes',
        'gsheet_id' : '1EBJzK3mCfa5Tjg0TYaSDlqujYQ1Sw6Z90UvCVc4lNGg',
        'birthday' : False,
    },
    {
        'ministry' : '310-Adult Choir',
        'gsheet_id' : '1QvieUBxB3EEcaHhNJmg1WvieI4WWztg4iiG4FEspj9c',
        'birthday' : False,
    },
    {
        'ministry' : '311-Bell Choir',
        'gsheet_id' : '1HCD6ACnhizGF2EbvubYKdZ4ARYLz0a1zYFksVaTfklY',
        'birthday' : True,
    },
    {
        'ministry' : '312-Children\'s Music Ministry',
        'gsheet_id' : '1wJ5LjV79zs_NTSt6Ise35XeobmN9Ei5SUwsHOLCLSTU',
        'birthday' : False,
    },
    {
        'ministry' : '313-Eucharistic Ministers',
        'gsheet_id' : '1M1kxLtHMdXCfmqPcFWrb5lhs_5FGXcXZKXk46L6MSsA',
        'birthday' : False,
    },
    {
        'ministry' : '315-Funeral Mass Ministry',
        'gsheet_id' : '1GHRXVEckGsqFTXt4HXI4nopQALCKLx0DMZsQlC5jxco',
        'birthday' : False,
    },
    {
        'ministry' : '316-Greeters',
        'gsheet_id' : '1WWyDVvWxAIhVPJVO2apagjxtCghXPU3bpfv0uWUBdhk',
        'birthday' : False,
    },
    {
        'ministry' : '317-Instrumentalists & Cantors',
        'gsheet_id' : '17VQx7Sk1ZuHHkAy-HsDNgCvXgm9A4GKKdD-0BLtjlUI',
        'birthday' : True,
    },
    {
        'ministry' : '318-Lectors',
        'gsheet_id' : '1BJ0UJRxvWovZIwJq3u8FLdqKc-LGPzQpSM5T6RrLbh0',
        'birthday' : False,
    },
    {
        'ministry' : '319-Liturgical Dance Ministry',
        'gsheet_id' : '1wWilGCTMUpzvI1Duzh-W31l7PEQU819DK9hYRYfourA',
        'birthday' : False,
    },
    {
        'ministry' : '321-Prayer Chain Ministry',
        'gsheet_id' : '1rV1XIA18cxAXDwLMo6G5Tqr2MCn2YRY5ky9PPqAPHVg',
        'birthday' : False,
    },
    {
        'ministry' : '401-Epiphany Companions',
        'gsheet_id' : '1GvzGjcbJGTtflWa7NAKemStBG8MXbqxF7Jh3mH9S6WQ',
        'birthday' : False,
    },
    {
        'ministry' : '402-New Members Coffee',
        'gsheet_id' : '1RaRyh5ARCFoRtMNPQPCHzxdqMdO_E2A3fWsBgEW3rXQ',
        'birthday' : False,
    },
    {
        'ministry' : '404-Welcome Desk',
        'gsheet_id' : '1c2P_vqJh-9THfsvMAh8uZv6snB0OWIB0kyKd9YqSNI8',
        'birthday' : False,
    },
    {
        'ministry' : '406-Evangelization Team',
        'gsheet_id' : '1sRQLwbbyHHQmcjFHOXj-aIRIZGkAXjEAiExULBaB_44',
        'birthday' : False,
    },
    {
        'ministry' : '407-Stewardship Team',
        'gsheet_id' : '1pvAGVM16nJDOY9dYs67FdtLbNpEE3qFUOoUvQoeKJFU',
        'birthday' : False,
    },
    {
        'ministry' : '408-Engagement Team',
        'gsheet_id' : '1do0tUAeaAIYJYCi7Sfd12LPXay-oadoGcn_SmnoEzlQ',
        'birthday' : False,
    },
    {
        'ministry' : '409-Sunday Morning Coffee',
        'gsheet_id' : '1JLMC5uqQlJ6RgwDZX6MsCWaqYY70fMbFle8sBWkaTVk',
        'birthday' : False,
    },
    {
        'ministry' : '452-Media Communications',
        'gsheet_id' : '1W7dWzuoZjtqLp7N0QXCh61EOm3UxMIxwio-m8QYzM8I',
        'birthday' : False,
    },
    {
        'ministry' : '501-Eucharist to Sick&Homebnd',
        'gsheet_id' : '1XP5AShlYUEzR7uE4GfdW9HaPdZZ7dTLsjx8AsrMADrs',
        'birthday' : False,
    },
    {
        'ministry' : '505-Healing Blanket Ministry',
        'gsheet_id' : '1hLxjlI28UKHYFA21hHVD4hNUW9rCEB-ihSEaCr7ENuI',
        'birthday' : False,
    },
    {
        'ministry' : '508-Messages of Hope Ministry',
        'gsheet_id' : '1h-OkqDak6IdxbZVlbqyG-UkZEvVMybbZCsSWr_HAD7w',
        'birthday' : False,
    },
    {
        'ministry' : '509-HOPE Support Groups',
        'gsheet_id' : '1MBATMw1dfb81zvhsQ7W6WEFjMHlhYz-AaFpbROCwGWc',
        'birthday' : False,
    },
    {
        'ministry' : '510-Flower Delivery to SHB',
        'gsheet_id' : '19cIpyHHktTrGExMASUFS_bmjMju7R-_Y6ofImX9jOjo',
        'birthday' : False,
    },
    {
        'ministry' : '600-Men of Epiphany',
        'gsheet_id' : '1J2Gu7t8VkPsFsDxnbqMvhC5xljbVydK1zOPYZc7ZYVw',
        'birthday' : False,
    },
    {
        'ministry' : '601-Sages (for 50 yrs. +)',
        'gsheet_id' : '1xslfW3kqisx8kzJSA1QgQtljzJ7ENl9iOuC_-CoNaaM',
        'birthday' : False,
    },
    {
        'ministry' : '602-Singles Explore Life (SEL)',
        'gsheet_id' : '1dKn0XiT-bpJ-stZ103ET_kPKfEM88RJOGOPjGwVhF94',
        'birthday' : False,
    },
    {
        'ministry' : '604-Wednesdays for Women',
        'gsheet_id' : '1Dw-u0PBvPT6zwawiGvOWX6pMNKezNS2KPqqfdw4S4bw',
        'birthday' : False,
    },
    {
        'ministry' : '609-Octoberfest Plan Team 2022',
        'gsheet_id' : '1Xtvss0vpiaRzjE9cEuoecTz7h3JWh-xmQFTI-AvEgdM',
        'birthday' : False,
    },
    {
        'ministry' : '611-Bereavement Receptions',
        'gsheet_id' : '1tFYlhbBcWFEAeIdI_isF9Z2zsi1gY2jUEKiP9FM_yno',
        'birthday' : False,
    },
    {
        'ministry' : '612-Community Life Committee',
        'gsheet_id' : '1R7dk_qSHAU_emnLANgF4bj8srXi2_18ATaxVHmwpz0Y',
        'birthday' : False,
    },
    {
        'ministry' : '700-Advocates for Common Good',
        'gsheet_id' : '1VdQrtZrCRK2ZS00QaqODgXH4UP7GPOG8SePCAbMqbak',
        'birthday' : False,
    },
    {
        'ministry' : '701-CLOUT',
        'gsheet_id' : '1cnw_4N8TgxdpiAdfcRSa17mbveqe6dAYY5IG0JewNkY',
        'birthday' : False,
    },
    {
        'ministry' : '703-Eyeglass Ministry',
        'gsheet_id' : '1TxDTGmBalrMq0_9nYNHCO5tIPxqm4ZGpOMlzrJE0PHU',
        'birthday' : False,
    },
    {
        'ministry' : '704-Habitat for Humanity',
        'gsheet_id' : '1wb4ksX7Nu059-rDa8n12y3LpYxWIqQt9-Gbv7tuxqV4',
        'birthday' : False,
    },
    {
        'ministry' : '705-Hunger & Poverty Ministry',
        'gsheet_id' : '1gu60W6eFLDo5pNDwbPdp60Q3-mW5oZ5oi0tdKETcWY4',
        'birthday' : False,
    },
    {
        'ministry' : '706-Prison Ministry',
        'gsheet_id' : '1g-Z41e_lXAigSESBg9RTb_25zzidkM5u9yDX-pD1lqQ',
        'birthday' : False,
    },
    {
        'ministry' : '707-St. Vincent De Paul',
        'gsheet_id' : '1ICq-Jn7N7JKRYotxaa0C2LgIbRaRHRCoxfOgzCJekpU',
        'birthday' : False,
    },
    {
        'ministry' : '709-Twinning Committee:Chiapas',
        'gsheet_id' : '16NcSJKzqkE28wuTfcRfItVmVHpDhWOensAqh-0U5d5c',
        'birthday' : False,
    },
    {
        'ministry' : '710-Environmental Concerns',
        'gsheet_id' : '1j5BVyVnqTLjjNAxUlAE5B-AXMECcx3tmDk9dQzegqTE',
        'birthday' : False,
    },
    {
        'ministry' : '712-Legislative Network',
        'gsheet_id' : '1-PToZJtO8Jft_LTDJKYygXVXRSnxpReI9f8yxSrc1tQ',
        'birthday' : False,
    },
    {
        'ministry' : '800-Catechists for Children',
        'gsheet_id' : '1e4Pz9-jgh77CjpniEYYqrQELon4QseVCbgxt_gyRrzI',
        'birthday' : False,
    },
    {
        'ministry' : '802-Gather the Children',
        'gsheet_id' : '1t3v4zmJcdVjmu_Qtj9oDnglDSDDUQ79O2UXZv4FJifc',
        'birthday' : False,
    },
    {
        'ministry' : '805-Monday Adult Bible Study',
        'gsheet_id' : '1RUGMm2LzFgp66q40fFxBcLyXk11yeBSQozMpx2h8y_Q',
        'birthday' : False,
    },
    {
        'ministry' : '807-Catechumenate/InitiationTm',
        'gsheet_id' : '1flQzaj-c4zfotrSSqWIOz2J451-C9i-hPE3jf947wOE',
        'birthday' : False,
    },
    {
        'ministry' : '808-BibleTimes Core Team',
        'gsheet_id' : '1m3s6OWZ3ykqJ4LG0vhFCW0XaPyTVLJBWJ4MK4Ia8QI4',
        'birthday' : False,
    },

    {
        'ministry' : '901-Youth Ministry Adult Vols',
        'gsheet_id' : '1gL5ekFiBL4il_Aym1Sb8QUIZv5EFw-TfKoeMBC0rZVU',
        'birthday' : False,
    },
    {
        'ministry' : '902-Adult Advisory Council',
        'gsheet_id' : '1yW9tUxef7slTboXYXlVoWrAH80vhP-IAZ53MBjXYUPA',
        'birthday' : False,
    },
    {
        'ministry' : '903-Confirmation Core Team',
        'gsheet_id' : '1Ay9Zp3HnHmINygZWIilVWMvlbD4IfKygyOoa9wU4FK8',
        'birthday' : False,
    },
]

workgroups = [
    {
        'workgroup' : 'Livestream Team',
        'gsheet_id' : '1VDydiBCfI007b7u2ji0fyjlV-8MaxFndiWdF6Ny-KVQ',
        'birthday'  : False,
    },
    {
        'workgroup' : 'YouthMin parent: Jr high',
        'gsheet_id' : '11XfI_8qPGk-dwhsl6RDNNrIIs7wKKP8Da8tstLaokyQ',
        'birthday'  : False,
    },
    {
        'workgroup' : 'YouthMin parent: Sr high',
        'gsheet_id' : '1IoSn1P-68voRhOQKHra1bk7YqAGIswm2F4PPRy4Btsw',
        'birthday'  : False,
    },
]

####################################################################

def write_xlsx(members, ministry_name, name, want_birthday, log):
    # Make the microseconds be 0, just for simplicity
    now = datetime.now()
    us = timedelta(microseconds=now.microsecond)
    now = now - us

    timestamp = ('{year:04}-{mon:02}-{day:02} {hour:02}:{min:02}'
                .format(year=now.year, mon=now.month, day=now.day,
                        hour=now.hour, min=now.minute))
    filename_base = name
    if filename_base is None:
        filename_base = ministry_name
    filename_base = filename_base.replace("/", "-")
    filename = (f'{filename_base} members as of {timestamp}.xlsx')

    # Put the members in a sortable form (they're currently sorted by MID)
    sorted_members = dict()
    for m in members:
        # 'Name' will be "Last,First..."
        sorted_members[m['display_FullName']] = m

    wb = Workbook()
    ws = wb.active

    # Title rows + set column widths
    title_font = Font(color='FFFF00')
    title_fill = PatternFill(fgColor='0000FF', fill_type='solid')
    title_align = Alignment(horizontal='center')

    last_col = 'D'
    if want_birthday:
        last_col = 'E'

    row = 1
    ws.merge_cells(f'A{row}:{last_col}{row}')
    cell = f'A{row}'
    ws[cell] = f'Ministry: {ministry_name}'
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

    role = 'D'
    if want_birthday:
        columns.append((f'D{row}', 'Birthday', 30))
        role = 'E'
    columns.append((f'{role}{row}', 'Role', 20))

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
        _ = ws.cell(row=row, column=1, value=m['py friendly name LF'])

        # The address will take multiple rows
        col = 2
        last_row = row
        f = m['py family']
        last_row = _append(col=col, row=last_row, value=f['primaryAddress1'])
        last_row = _append(col=col, row=last_row, value=f['primaryAddress2'])
        val = '{cs}, {state} {zip}'.format(cs=f['primaryCity'],
                                           state=f['primaryState'],
                                           zip=f['primaryPostalCode'])
        last_row = _append(col=col, row=last_row, value=val)
        addr_last_row = last_row
        email_last_row = last_row

        # The phone / email may be more than 1 row
        col = 3
        last_row = row
        phones = ParishSoft.get_member_public_phones(m)
        for phone in phones:
            val = '{ph} {type}'.format(ph=phone['number'], type=phone['type'])
            last_row = _append(col=col, row=last_row, value=val)

        # If we have any preferred emails, list them all
        email = ParishSoft.get_member_public_email(m)
        if email is not None:
            last_row = _append(col=col, row=last_row, value=email)
            email_last_row = last_row

        # The birthday will only be 1 row
        if want_birthday:
            col = 4
            key = 'birthdate'
            if key in m and m[key] is not None:
                birthday = f'{m[key].strftime("%B")} {m[key].day}'
                _append(col=col, row=row, value=birthday)

        # Role
        col += 1
        _append(col=col, row=row, value=m['py ministry role'])

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
    mime_type = Google.mime_types['sheet']
    #mime_type = Google.mime_types['xlsx']

    try:
        log.info(f'Uploading file update to Google file ID "{file_id}"')
        metadata = {
            'name'     : gsheet_name,
            'mimeType' : Google.mime_types['sheet'],
            'supportsAllDrives' : True,
            }
        media = MediaFileUpload(filename,
                                mimetype=Google.mime_types['xlsx'],
                                resumable=True)
        file = google.files().update(body=metadata,
                                     fileId=file_id,
                                     media_body=media,
                                     supportsAllDrives=True,
                                     fields='id').execute()
        log.debug(f'Successfully updated file: "{filename}" (ID: {file["id"]})')

    except Exception as e:
        # When errors occur, we do want to log them.  But we'll re-raise them to
        # let an upper-level error handler handle them (e.g., retry.Retry() may
        # actually re-invoke this function if it was a retry-able Google API
        # error).
        log.error('Google file update failed for some reason:')
        log.error(e)
        raise e

#-------------------------------------------------------------------

def _create_roster(ps_members, ministry_name, sheet_name,
                   birthday, gsheet_id, google, log):
    # PDSChurch.filter_members() returns a dict.  Turn this into a simple
    # list of Members.
    members = [ x for x in ps_members.values() ]

    # Make an xlsx
    filename = write_xlsx(members=members,
                          ministry_name=sheet_name,
                          name=ministry_name,
                          want_birthday=birthday, log=log)
    log.debug(f"Wrote temp XLSX file: {filename}")

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

#-------------------------------------------------------------------

def create_ministry_roster(ps_members, ps_ministries, ministry_sheet, google, log):
    log.info(f"Making ministry roster for: {ministry_sheet}")
    gsheet_id = ministry_sheet['gsheet_id']
    birthday  = ministry_sheet['birthday']

    key1 = 'ministry'
    key2 = 'ministries'
    if key1 in ministry_sheet:
        sheet_name = ministry_sheet[key1]
        ministries = [ sheet_name ]
    elif key2 in ministry_sheet:
        sheet_name = ', '.join(ministry_sheet[key2])
        ministries = ministry_sheet[key2]
    else:
        print(f"ERROR: Cannot find {key1} or {key2} in ministry_sheet!")
        print(ministry_sheet)
        exit(1)

    name = None
    key = 'name'
    if key in ministry_sheet:
        name = ministry_sheet[key]

    # Find the PS Ministry Membershp with the same name
    ministry = None
    for entry in ps_ministries.values():
        if entry['name'] == ministry_sheet['ministry']:
            ministry = entry
    if ministry is None:
        log.error(f"Could not find PS ministry named '{ministry_sheet['ministry']}'")
        exit(1)
    log.debug(f"Found ministry: {ministry['name']}")

    # Make a list of PS Members (objects) that are in this ministry
    members = dict()
    for entry in ministry['membership']:
        mem_duid = entry['memberId']
        if mem_duid not in ps_members:
            log.error(f"Cannot find PS Member with DUID {mem_duid} -- inactive member?")
            exit(1)

        members[mem_duid] = ps_members[mem_duid]
        # We stash this on the member so that it's easy to find later,
        # when making the roster.  This will continually be
        # overwritten on the member with the role for the current
        # ministry.
        members[mem_duid]['py ministry role'] = entry['ministryRoleName']

    if members is None or len(members) == 0:
        log.info(f"No members in ministry: {sheet_name} -- writing empty sheet")

    _create_roster(members, name, sheet_name,
                   birthday, gsheet_id, google, log)

#-------------------------------------------------------------------

def create_workgroup_roster(ps_members, ps_mem_workgroups, workgroup_sheet, google, log):
    log.info(f"Making roster for Member Workgroup: {workgroup_sheet}")
    gsheet_id = workgroup_sheet['gsheet_id']
    birthday  = workgroup_sheet['birthday']

    key = 'workgroup'
    if key not in workgroup_sheet:
        print(f"ERROR: Cannot find {key} in workgroup_sheet!")
        print(ministry_entry)
        exit(1)

    # The "Leader" workgroups end in " Ldr"
    leader_suffix = ' Ldr'
    wg_name = workgroup_sheet[key]
    # IMPORTANT: Have the "leader suffix" group come last!  We want to
    # overwrite the "py member role" on the Member of leaders (below).
    wg_names = [ wg_name,
                 f'{wg_name}{leader_suffix}' ]

    # Find the PS Member Workgroup with the same name or ldr_name.
    # Fill the members dictionary will all of its members (the
    # dictionary will de-duplicate based on DUID).
    members = dict()
    for wg in ps_mem_workgroups.values():
        if wg['name'] not in wg_names:
            continue

        # Make a list of PS Members (objects) that are in this
        # member workgroup
        for member in wg['membership']:
            mem_duid = member['memberId']
            if mem_duid not in ps_members:
                log.error(f"Cannot find PS Member with DUID {mem_duid} -- inactive member?")
                exit(1)

            members[mem_duid] = ps_members[mem_duid]
            # We stash this on the member so that it's easy to find
            # later, when making the roster.  This will continually be
            # overwritten on the member with the role for the current
            # ministry.
            if wg['name'].endswith(leader_suffix):
                members[mem_duid]['py ministry role'] = 'Leader'
            else:
                members[mem_duid]['py ministry role'] = 'Member'

    if members is None or len(members) == 0:
        log.info(f"No members in ministry: {sheet_name} -- writing empty sheet")

    _create_roster(members, wg_name, wg_name,
                   birthday, gsheet_id, google, log)

####################################################################

def setup_cli_args():
    tools.argparser.add_argument('--logfile',
                                 help='Also save to a logfile')
    tools.argparser.add_argument('--debug',
                                 action='store_true',
                                 default=False,
                                 help='Be extra verbose')

    tools.argparser.add_argument('--ps-api-keyfile',
                                 required=True,
                                 help='File containing the ParishSoft API key')
    tools.argparser.add_argument('--ps-cache-dir',
                                 default='.',
                                 help='Directory to cache the ParishSoft data')

    global gapp_id
    tools.argparser.add_argument('--app-id',
                                 default=gapp_id,
                                 help='Filename containing Google application credentials')
    global guser_cred_file
    tools.argparser.add_argument('--user-credentials',
                                 default=guser_cred_file,
                                 help='Filename containing Google user credentials')

    args = tools.argparser.parse_args()

    # Read the PS API key
    if not os.path.exists(args.ps_api_keyfile):
        print(f"ERROR: ParishSoft API keyfile does not exist: {args.ps_api_keyfile}")
        exit(1)
    with open(args.ps_api_keyfile) as fp:
        args.api_key = fp.read().strip()

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

    log.info("Reading PS data...")
    families, members, family_workgroups, member_workgroups, ministries = \
        ParishSoft.load_families_and_members(api_key=args.api_key,
                                             cache_dir=args.ps_cache_dir,
                                             active_only=True,
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

    for sheet in ministry_sheets:
        create_ministry_roster(ps_members=members,
                               ps_ministries=ministries,
                               ministry_sheet=sheet,
                               google=google,
                               log=log)

    for sheet in workgroups:
        create_workgroup_roster(ps_members=members,
                                ps_mem_workgroups=member_workgroups,
                                workgroup_sheet=sheet,
                                google=google,
                                log=log)

if __name__ == '__main__':
    main()
