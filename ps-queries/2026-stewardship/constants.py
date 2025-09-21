import os
import urllib
import datetime

import helpers

# Overall title
stewardship_year = 2026
title = f'Stewardship {stewardship_year}'

# Start and end dates for the stewardship year

stewardship_begin_date = datetime.date(year=stewardship_year, month=1,  day=1)
stewardship_end_date   = datetime.date(year=stewardship_year, month=12, day=31)

#--------------------------------------------------------------------------

# SMTP / email basics

smtp_server  = 'smtp-relay.gmail.com'
smtp_from    = f'"Epiphany Catholic Church" <stewardship-{stewardship_year}@epiphanycatholicchurch.org>'

#--------------------------------------------------------------------------

# Submitted eStewardship in prior year

stewardship_fam_cur_year_wg = f'Active: Stewardship {stewardship_year}'
stewardship_fam_prev_year_wg = f'Active: Stewardship {stewardship_year-1}'

# ParishSoft Member Workgroup names

business_logisitics_wg_name = 'Business Logistics Email'

#--------------------------------------------------------------------------

# For Stewardship 2020, redirect.ecc.org is a Digital Ocean droplet running
# Ubuntu and Apache and the PHP in the php subfolder (with free LetEncrypt SSL
# certificates to make everything encrypted).

email_image_url = f'https://api.epiphanycatholicchurch.org/stewardship-{stewardship_year}/stewardship-logo.png'
api_base_url    = f'https://api.epiphanycatholicchurch.org/stewardship-{stewardship_year}/?key='

#--------------------------------------------------------------------------

# Google local metadata files
gapp_id         = 'client_id.json'
guser_cred_file = 'user-credentials.json'

# The public URL we use to access the Jotform form
jotform_form_url = 'https://form.jotform.com/252365065387160'

# Copied from the Google Spreadsheet where Jotform is writing its
# results
jotform_gsheet_gfile_id = '1Zy8MZddnxRrc_4W0OeEcvUhPyKaA9S-xZBGMHeUoPzU'

# Last year's Jotform Gsheet results
#
# Only load this if we're actually "constants.py" (as opposed to being
# named -- via sym link -- "constants_prev_year.py")
if os.path.basename(__file__) == "constants.py":
    from constants_prev_year import jotform_gsheet_gfile_id as \
        jotform_gsheet_prev_year_gfile_id
    from constants_prev_year import jotform_gsheet_columns as \
        jotform_gsheet_prev_year_columns

# Google Shared Drive folder where to upload the CSV/spreadsheet comparison
# output files
upload_team_drive_folder_id = '1B0ce_ZfjL9jQmyC5v6fGvBiZGAdTiatr'

# Top level folder of the Google Shared Drive
google_shared_drive_id = '0AHQEqKijqXcFUk9PVA'

gsheet_editors = f'stewardship-{stewardship_year}@epiphanycatholicchurch.org'

#--------------------------------------------------------------------------

# For members who change their ministry data, start / end dates to use

ministry_start_date = '11/01/2025'
ministry_end_date   = ministry_start_date

#--------------------------------------------------------------------------

# In the 2D ministry grids in Jotform, we need to know the column numbers
# (starting with 0) for two cases:
# 1. For when the Member is involved in this ministry
# 2. For when the Member is not involved in this ministry
COL_AM_INVOLVED  = 0
COL_NOT_INVOLVED = 2

MAX_PS_FAMILY_MEMBER_NUM = 7

#############################################################################

class ministry_2d_grid:
    def __init__(self, name, field_prefix, q_prefixes,
                 field_max=MAX_PS_FAMILY_MEMBER_NUM):
        self.name          = name
        self.rows          = list()
        self.member_fields = list()
        self.field_prefix  = field_prefix
        self.field_max     = field_max
        self.q_prefixes    = q_prefixes

        for i in range(1, field_max + 1):
            q_prefix = f'q{q_prefixes[i-1]}_'
            self.member_fields.append(f'{q_prefix}{field_prefix}{i}')

    def add_row(self, ps_ministry, row_heading=None, new=False):
        # If no row_heading is provided, it is the same as the PS ministry name
        if row_heading is None:
            row_heading = ps_ministry

        if new:
            row_heading = f'NEW {row_heading}'

        self.rows.append({
            'ps_ministry'     : ps_ministry,
            'row_heading'     : row_heading,
            'new'             : new,

            # This value is filled in much later.
            # It will be the name of the column in the Jotform gsheet of
            # results: there will be one unique column name for each Member.
            'jotform_columns' : list(),
        })

#----------------------------------------------------------------------------

_all_ministry_grids = list()

#----------------------------------------------------------------------------

grid = ministry_2d_grid('Parish Leadership', 'pl',
                        [65, 108, 135, 162, 189, 216, 243 ])

grid.add_row('100-Parish Pastoral Council')
grid.add_row('102-Finance Advisory Council')
grid.add_row('103-Worship Committee')
grid.add_row('104-Stewardship Team',
                '104-Stewardship & Engagement Committee')
grid.add_row('107-Social Resp Steering Comm',
                '107-Social Responsibility Steering Committee')
grid.add_row('108-Faith Formation Team')
grid.add_row('110-Ten Percent Committee')
grid.add_row('111-Hispanic Ministry Team')
grid.add_row('113-Media Comms Planning Comm.',
             '113-Media Communications Planning Committee')
grid.add_row('115-Community Care Committee')
grid.add_row('116-Youth Council')

_all_ministry_grids.append(grid)

#----------------------------------------------------------------------------

grid = ministry_2d_grid('Administration', 'aa',
                        [67, 110, 137, 164, 191, 218, 245 ])

grid.add_row('200-Audit Committee')
grid.add_row('201-Collection Counter')
grid.add_row('203-Garden & Grounds',
             '203-Gardens & Grounds')
grid.add_row('204-Parish Office Volunteers')
grid.add_row('206-Space Arrangers')
grid.add_row('207-Technology Committee')
grid.add_row('208-Weekend Closer',
             '208-Weekend Closers')

_all_ministry_grids.append(grid)

#----------------------------------------------------------------------------

grid = ministry_2d_grid('Liturgical Prepatory', 'lp',
                        [68, 112, 139, 166, 193, 220, 247 ])

grid.add_row('300-Art & Environment')
grid.add_row('301-Audio/Visual/Light Minstry',
                '301-Audio/Visual/Lighting Ministry')
grid.add_row('303-Linens/Vestments Ministry')
grid.add_row('304-LiturgicalPlanningDscrnmnt',
             '304-Liturgy Planning Discernment Committee')
grid.add_row('306-Music Support for Children',
             '306-Music Support for Children\'s Formation')
grid.add_row('307-Wedding Assistant',
             '307-Wedding Assistants')
grid.add_row('308-Worship&Music Support Team',
                '308-Worship & Music Support Team')

_all_ministry_grids.append(grid)

#----------------------------------------------------------------------------

grid = ministry_2d_grid('Liturgical Celebratory', 'lc',
                        [69, 114, 141, 168, 195, 222, 249 ])

grid.add_row('309-Acolytes')
grid.add_row('310-Adult Choir')
grid.add_row('311-Bell Choir')
grid.add_row('312-Children\'s Music Ministry')
grid.add_row('313-Eucharistic Ministers')
grid.add_row('315-Funeral Mass Ministry')
grid.add_row('316-Greeters')
grid.add_row('317-Instrumentalists & Cantors')
grid.add_row('318-Lectors')
grid.add_row('319-Liturgical Dance Ministry',
             '319-Liturgical Dance')

_all_ministry_grids.append(grid)

#----------------------------------------------------------------------------

# Used to be "Stewardship and Engagement, hence the "se" prefix.
grid = ministry_2d_grid('Community Life', 'se',
                        [70, 116, 143, 170, 197, 224, 251 ])

grid.add_row('401-Epiphany Companions')
grid.add_row('404-Welcome Desk')
grid.add_row('409-Sunday Morning Coffee',
             '409-Sunday Morning Coffee Workers')
grid.add_row('410-Epiphany Flower Guild')
grid.add_row('412-Sages (for 50 yrs. +)')
grid.add_row('413-Singles Explore Life (SEL)')
grid.add_row('414-Hospitality Linen Ministry', new=True)

_all_ministry_grids.append(grid)

#----------------------------------------------------------------------------

grid = ministry_2d_grid('Community Care', 'hh',
                        [71, 118, 145, 172, 199, 226, 253 ])

grid.add_row('500-Bereavement Receptions')
grid.add_row('501-Eucharist to Sick&Homebnd',
                '501-Eucharist to the Sick and Homebound')
grid.add_row('505-Healing Blanket Ministry')
grid.add_row('507-Flower Angels', new=True)
grid.add_row('508-Grief Support Group')
grid.add_row('509-HOPE for the Widowed Support Groups')
grid.add_row('510-Flower Delivery to SHB',
             '510-Flower Delivery - Homebound, & Bereaved')
grid.add_row('511-Prayer Chain Ministry')
grid.add_row('512-Health & Wellness Ministry', new=True)
grid.add_row('513-Blessing Card Ministry', new=True)

_all_ministry_grids.append(grid)

#----------------------------------------------------------------------------

grid = ministry_2d_grid('Social Responsibility', 'sr',
                        [73, 122, 149, 176, 203, 230, 257 ])

grid.add_row('700-Advocates for Common Good',
             '700-Advocates for the Common Good')
grid.add_row('701-CLOUT')
grid.add_row('703-Eyeglass Ministry')
grid.add_row('704-Habitat for Humanity',
             '704-Habitat for Humanity - Epiphany Build Team')
grid.add_row('705-Hunger & Poverty Ministry')
grid.add_row('706-Prison Ministry')
grid.add_row('707-St. Vincent De Paul',
             '707-St. Vincent De Paul - Epiphany Conference')
grid.add_row('708-Social Concerns Forum', new=True)
grid.add_row('709-Twinning Committee:Chiapas',
             '709-Twinning Committee: Chiapas')
grid.add_row('710-Creation Care Team')
grid.add_row('711-Women\'s Concerns Committee')

_all_ministry_grids.append(grid)

#----------------------------------------------------------------------------

grid = ministry_2d_grid('Faith Formation', 'ff',
                        [74, 124, 151, 178, 205, 232, 259 ])

grid.add_row('800-Catechists for Children',
             '800-Children\'s Formation Catechists (PreK-6th)')
grid.add_row('802-Gather the Children Prayer Leaders')
grid.add_row('805-Monday Adult Bible Study Catechists')
grid.add_row('807-Catechumenate / Initiation Team Members')
grid.add_row('808-BibleTimes Volunteers')
grid.add_row('809-Marriage Mentor Couples')
grid.add_row('810-Wednesdays for Women')

_all_ministry_grids.append(grid)

#----------------------------------------------------------------------------

grid = ministry_2d_grid('Youth Ministires', 'ym',
                        [380, 432, 433, 434, 438, 439, 437 ])

grid.add_row('901-Youth Ministry Adult Vols',
             '901-Youth Ministry Adult Volunteers')
grid.add_row('902-Adult Advisory Council')
grid.add_row('903-Confirmation Core Team')

_all_ministry_grids.append(grid)

#############################################################################

class jotform_class:
    def __init__(self, url, ministry_grids):
        self.url            = url
        self.pre_fill_data  = {
            'family'     : list(),
            'per_member' : list(),
        }
        self.ministry_grids = ministry_grids

    def _add_pre_fill_data(self, type, name, func, fields):
        self.pre_fill_data[type].append({
            'name'       : name,
            'fields'     : fields,
            'value_func' : func,
        })

    def add_family_pre_fill_data(self, name, func, fields):
        # NOTE: the "fields" will be a single field for Family data
        self._add_pre_fill_data('family', name, func, fields)

    def add_member_pre_fill_data(self, name, func, fields):
        # NOTE: the "fields" will be a list for Member data
        self._add_pre_fill_data('per_member', name, func, fields)

#----------------------------------------------------------------------------

last_updated = datetime.datetime.now().strftime('%A %B %d, %Y at %I:%M%p')

jotform = jotform_class(jotform_form_url, _all_ministry_grids)

# These Jotform fields are for the overall Family
jotform.add_family_pre_fill_data('fduid',
                    lambda fam: fam['familyDUID'],
                    'fduid')
jotform.add_family_pre_fill_data('Emails for Jotform to send response to',
                    lambda fam: ','.join(fam['stewardship']['to_addresses']),
                    'email')

# If the value is an integer, just return "%24{val}" (i.e., "${val}").
# If it's a floating point value, make sure to show 2 decimal places.
def jf_money_str(val):
    if isinstance(val, int):
        return f'%24{val}'
    else:
        return f'%24{val:.2f}'

jotform.add_family_pre_fill_data('Family annual pledge for stewardship_year-1',
                    lambda fam: jf_money_str(fam['calculated']['pledged']) if 'calculated' in fam else "%240",
                    'previousPledge')
jotform.add_family_pre_fill_data('Family contributed so far in stewardship_year-1',
                    lambda fam: jf_money_str(fam['calculated']['gifts']) if 'calculated' in fam else "%240",
                    'giftsThisYear_fmt')

jotform.add_family_pre_fill_data('Family name',
                    lambda fam: helpers.url_escape(f'{fam["firstName"]} {fam["lastName"]}'),
                    'householdName')

# These Jotform fields are specific to a Member
jotform.add_member_pre_fill_data('mduid',
                    lambda mem: mem['memberDUID'],
                    [ f'mduid{i}' for i in range(1, MAX_PS_FAMILY_MEMBER_NUM+1) ])
jotform.add_member_pre_fill_data('name',
                    lambda mem: helpers.url_escape(mem['py friendly name FL']),
                    [ f'name{i}' for i in range(1, MAX_PS_FAMILY_MEMBER_NUM+1) ])

###########################################################################

# These are the fields in the Jotform ministry results spreadsheet
# The ordering of these fields is critical, although the names are not.
jotform_gsheet_columns = dict()

#--------------------------------------------------------------------------

# Add Jotform fields and family-general data
jotform_gsheet_columns['prelude'] = [
    # This is put here by Jotform automatically
    'SubmitDate',
    # This is where our fields start
    'fduid',
    'Emails to reply to',
    'Spiritual participation',
]

#--------------------------------------------------------------------------

max_number = MAX_PS_FAMILY_MEMBER_NUM

jotform_gsheet_columns['per-member epilog'] = [
    # These fields were present in the 2026 Jotform, but they were hidden.
    # Hence, there is no data collected for these fields, but the columns
    # still show up in the Google results spreadsheet.
    'member group prayer events',
    'member small prayer group',
    'member protect',
]

jotform_gsheet_columns['members'] = list()
for member_num in range(1, max_number+1):
    member_columns = list()
    # Add the per-member columns (E.g., MDUID, name)
    for data in jotform.pre_fill_data['per_member']:
        member_columns.append(data['fields'][member_num - 1])

    # Add the per-member ministry grid columns
    for grid in jotform.ministry_grids:
        for row in grid.rows:
            col_heading = row['row_heading']
            column_name = col_heading + f" {member_num}"
            member_columns.append(column_name)

            row['jotform_columns'].append(column_name)

    # Add the per-member ministry epilog columns
    for col in jotform_gsheet_columns['per-member epilog']:
        member_columns.append(f'{col} {member_num}')

    jotform_gsheet_columns['members'].append(member_columns)

#--------------------------------------------------------------------------

jotform_gsheet_columns['family'] = [
    'Family names',
    f'CY{stewardship_year-1} pledge',
    f'CY{stewardship_year-1} gifts',
    f'CY{stewardship_year} whole year pledge',
    f'CY{stewardship_year} how fullfill',
    f'CY{stewardship_year} weekly',
    f'CY{stewardship_year} monthly',
    f'CY{stewardship_year} quarterly',
    f'CY{stewardship_year} how',
    'Comments',
]

#--------------------------------------------------------------------------

jotform_gsheet_columns['epilog'] = [
    'Submission IP',
    'Submission URL',
    'Edit URL',
    'Last update',
    'Submissions ID',
]
