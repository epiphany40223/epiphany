import datetime

import helpers

# Overall title

stewardship_year = 2021

title = f'Stewardship {stewardship_year}'

# Start and end dates for the stewardship year

stewardship_begin_date = datetime.date(year=stewardship_year, month=1,  day=1)
stewardship_end_date   = datetime.date(year=stewardship_year, month=12, day=31)

#--------------------------------------------------------------------------

# SMTP / email basics

smtp_server  = 'smtp-relay.gmail.com'
smtp_from    = f'"Epiphany Catholic Church" <stewardship{stewardship_year}@epiphanycatholicchurch.org>'

#--------------------------------------------------------------------------

# Already submitted PDS Family Status

already_submitted_fam_status = f'{stewardship_year} Stewardship'

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

# Copied from the Google Spreadsheet where Jotform is writing its
# results
jotform_gsheet_gfile_id = '1NWSW8SRXGBLJXtjbGrkPE7kCPzxosVYo9z-VsvkOgU4'

# Team Drive folder where to upload the CSV/spreadsheet comparison
# output files
upload_team_drive_folder_id = '1fo8in3EBgidsAxtvm6p88b3uz8mjh7_2'

gsheet_editors = f'stewardship{stewardship_year}-workers@epiphanycatholicchurch.org'

#--------------------------------------------------------------------------

# For members who change their ministry data, start / end dates to use

ministry_start_date = '11/01/2020'
ministry_end_date   = ministry_start_date

#--------------------------------------------------------------------------

# In the cookies SQL database, we store two types of redirects:
# 1. Redirects for the ministry jotform
# 2. Redirects for the pledge jotform
MINISTRY_SQL_TYPE = 1
PLEDGE_SQL_TYPE   = 2

# In the 2D ministry grids in Jotform, we need to know the column numbers
# (starting with 0) for two cases:
# 1. For when the Member is involved in this ministry
# 2. For when the Member is not involved in this ministry
COL_AM_INVOLVED  = 0
COL_NOT_INVOLVED = 2

MAX_PDS_FAMILY_MEMBER_NUM = 6

#############################################################################

class ministry_2d_grid:
    def __init__(self, name, field_prefix, field_max=MAX_PDS_FAMILY_MEMBER_NUM):
        self.name          = name
        self.rows          = list()
        self.member_fields = list()
        self.field_prefix  = field_prefix
        self.field_max     = field_max

        for i in range(1, field_max+1):
            self.member_fields.append(f'{field_prefix}{i}')

    def add_row(self, pds_ministry, row_heading=None, new=False):
        # If no row_heading is provided, it is the same as the PDS ministry name
        if row_heading is None:
            row_heading = pds_ministry

        if new:
            row_heading = f'NEW {row_heading}'

        self.rows.append({
            'pds_ministry' : pds_ministry,
            'row_heading'  : row_heading,
            'new'          : new,
        })

#----------------------------------------------------------------------------

_all_ministry_grids = list()

#----------------------------------------------------------------------------

grid = ministry_2d_grid('Parish Leadership', 'pl')

grid.add_row('100-Parish Pastoral Council')
grid.add_row('102-Finance Advisory Council')
grid.add_row('103-Worship Committee')
grid.add_row('104-Stewardship & E Committee',
                            '104-Stewardship & Evangelization Committee')
grid.add_row('106-Community Life Committee')
grid.add_row('107-Social Resp Steering Comm',
                            '107-Social Responsibility Steering Committee')
grid.add_row('108-Formation Team')
grid.add_row('109-Prayer Ministry Leadership')
grid.add_row('110-Ten Percent Committee')

_all_ministry_grids.append(grid)

#----------------------------------------------------------------------------

grid = ministry_2d_grid('administration', 'aa')

grid.add_row('200-Audit Committee')
grid.add_row('201-Collection Counter')
grid.add_row('202-Facility Mgmt & Planning',
                '202-Facility Management & Planning')
grid.add_row('203-Garden & Grounds')
grid.add_row('204-Parish Office Volunteers')
grid.add_row('205-Participation Sheet Vol',
                '205-Participation Sheet Volunteer')
grid.add_row('206-Space Arrangers')
grid.add_row('207-Technology Committee')
grid.add_row('208-Weekend Closer')

_all_ministry_grids.append(grid)

#----------------------------------------------------------------------------

grid = ministry_2d_grid('Liturgical Prepatory', 'lp')

grid.add_row('300-Art & Environment')
grid.add_row('301-Audio/Visual/Light Minstry',
                    '301-Audio/Visual/Lighting Ministry')
grid.add_row('302-Bread Baking Ministry')
grid.add_row('303-Linens/Vestments Ministry')
grid.add_row('304-Liturgical Planning')
grid.add_row('305-Movers Ministry')
grid.add_row('306-Music Support for Children')
grid.add_row('307-Wedding Assistant')
grid.add_row('308-Worship&Music Support Team',
                    '308-Worship & Music Support Team')

_all_ministry_grids.append(grid)

#----------------------------------------------------------------------------

grid = ministry_2d_grid('Liturgical Celebratory', 'lc')

grid.add_row(['309A-Acolyte Ministry 5:30P',
              '309B-Acolyte Ministry  9:00A',
              '309C-Acolyte Ministry 11:30A'],
             '309-Acolytes')
grid.add_row('310-Adult Choir')
grid.add_row('311-Bell Choir')
grid.add_row('312-Children\'s Music Ministry')
grid.add_row('313-Communion Ministers')
grid.add_row('314-Communion Min. Coordinator',
                '314-Communion Minister Coordinator')
grid.add_row('315-Funeral Mass Ministry')
grid.add_row(['316A-Greeters 5:30P',
              '316B-Greeters 9:00A',
              '316C-Greeters 11:30A'],
             '316-Greeters')
grid.add_row('317-Instrumentalists & Cantors')
grid.add_row(['318A-Lector Ministry  5:30P',
              '318B-Lector  Ministry 9:00A',
              '318C-Lector Ministry 11:30A'],
             '318-Lectors')
grid.add_row('319-Liturgical Dance Ministry')
grid.add_row('321-Prayer Chain Ministry')

_all_ministry_grids.append(grid)

#----------------------------------------------------------------------------

grid = ministry_2d_grid('Stewardship & Evangelization', 'se')

grid.add_row('401-Epiphany Companions')
grid.add_row('402-New Members Coffee')
grid.add_row('404-Welcome Desk')
grid.add_row('406-Evangelization Team')
grid.add_row('407-Stewardship Team')

_all_ministry_grids.append(grid)

#----------------------------------------------------------------------------

grid = ministry_2d_grid('Communication', 'cc')

grid.add_row('450-Communications Committee')
grid.add_row('451-Livestream Team Ministry', new=True)

_all_ministry_grids.append(grid)

#----------------------------------------------------------------------------

grid = ministry_2d_grid('Helping & Healing', 'hh')

grid.add_row('500-BereavementReceptionSupprt',
                '500-Bereavement Reception & Support')
grid.add_row('501-Care of Sick: Communion',
                '501-Care of Sick: Communion to the Sick and Homebound')
grid.add_row('502-Care of Sick: Meals',
                '502-Care of Sick: Meals to the Sick and Homebound')
grid.add_row('503-Childcare Ministry: Adult')
grid.add_row('504-DivorceCare')
grid.add_row('505-Healing Blanket Ministry')
grid.add_row('507-Grief Support Team')
grid.add_row('508-Messages of Hope Ministry')

_all_ministry_grids.append(grid)

#----------------------------------------------------------------------------

grid = ministry_2d_grid('Social & Fellowship', 'sf')

grid.add_row('600-Men of Epiphany')
grid.add_row('601-Sages (for 50 yrs. +)',
                '601-Sages')
grid.add_row('602-Singles Explore Life (SEL)')
grid.add_row('603-Soup Supper Ministry')
grid.add_row('604-Wednesdays for Women')
grid.add_row('605-Sunday Morning Coffee')
grid.add_row('606-Kitchen Volunteer Ministry')
grid.add_row('607-Easter Egg Plan Team 2021')
grid.add_row('609-Octoberfest Plan Team 2021',
                '609-Octoberfest Planning Team 2021', new=True)
grid.add_row('610-FeastOfEpiphanyPlanTeam\'22',
                '610-Feast Of Epiphany Planning Team 2022')
grid.add_row('612-JubileePictorialDirectory',
                '612-Jubilee Pictorial Directory', new=True)

_all_ministry_grids.append(grid)

#----------------------------------------------------------------------------

grid = ministry_2d_grid('Social Responsibility', 'sr')

grid.add_row('700-Advocates for Common Good')
grid.add_row('701-C.L.O.U.T./Justice Network',
                '701-CLOUT')
grid.add_row('703-Eyeglass Ministry')
grid.add_row('704-Habitat for Humanity')
grid.add_row('705-Hunger & Poverty Ministry')
grid.add_row('706-Prison Ministry')
grid.add_row('707-St. Vincent DePaul')
grid.add_row('709-Twinning Committee:Chiapas',
                '709-Twinning Committee: Chiapas')
grid.add_row('710-Environmental Concerns')
grid.add_row('711-Hispanic Ministry Team')

_all_ministry_grids.append(grid)

#----------------------------------------------------------------------------

grid = ministry_2d_grid('Formational', 'ff')

grid.add_row('800-ChildrenFormationCatechist',
                '800-Children\'s Formation Catechists (PreK-6th)')
grid.add_row('801-Confirmation Adult Mentor')
grid.add_row('802-GathTheChildren Catechist',
                '802-Gather the Children Catechists')
grid.add_row('803-Youth Ministry AdultMentor',
                '803-Youth Ministry Adult Mentor')
grid.add_row('805-Monday Adult Bible Study')
grid.add_row('806-Scripture Sharing Group')
grid.add_row('807-RCIA Team')
grid.add_row('808-Young Adult Ministry')
grid.add_row('809-Sunday Adult Form. Spanish',
                '809-Sunday Adult Formation in Spanish')
grid.add_row('811-Family&Children\'s WorkGrp',
                '811-Family and Children\'s Working Group', new=True)
grid.add_row('812-Adult Form. Working Group',
                '812-Adult Formation Working Group')
grid.add_row('813-Visual Faith Group', new=True)
grid.add_row('815-Baptismal Prep Mentors', new=True)
grid.add_row('816-Marriage Prep Mentors', new=True)
grid.add_row('817-Peer Mentors', new=True)

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

jotform = jotform_class('https://form.jotform.com/202346350400137',
                    _all_ministry_grids)

# These Jotform fields are for the overall Family
jotform.add_family_pre_fill_data('FID',
                    lambda fam: fam['FamRecNum'],
                    'fid')
jotform.add_family_pre_fill_data('Envelope ID',
                    lambda fam: helpers.pkey_url(fam['ParKey']),
                    'parishKey')
jotform.add_family_pre_fill_data('Emails for Jotform to send response to',
                    lambda fam: ','.join(fam['stewardship']['to_addresses']),
                    'email')

jotform.add_family_pre_fill_data('Family name',
                    lambda fam: fam['calculated']['household_name'] if 'calculated' in fam else fam['MailingName'],
                    'household')
jotform.add_family_pre_fill_data('Family annual pledge for stewardship_year-1',
                    lambda fam: "%24{val}".format(val=fam['calculated']['pledged']) if 'calculated' in fam else "%240",
                    'previousPledge')
jotform.add_family_pre_fill_data('Family contributed so far in stewardship_year-1',
                    lambda fam: "%24{val}".format(val=fam['calculated']['contributed']) if 'calculated' in fam else "%240",
                    'soFarThisYear')

# These Jotform fields are specific to a Member
jotform.add_member_pre_fill_data('mid',
                    lambda mem: mem['MemRecNum'],
                    [ f'mid{i}' for i in range(1, 8) ])
jotform.add_member_pre_fill_data('name',
                    lambda mem: helpers.url_escape(mem['full_name']),
                    [ f'name{i}' for i in range(1, 8) ])

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
    'EnvId',
    'fid',
    'Emails to reply to',
]

#--------------------------------------------------------------------------

max_number = MAX_PDS_FAMILY_MEMBER_NUM
# In 20201, Jotform can only handle 6 Members' worth of data
# But we actually have 7 Members' worth of fields on the Form
# So we have to account for this 7th Member's data here, even
# though it will always be blank
max_number += 1

jotform_gsheet_columns['members'] = list()
for member_num in range(1, max_number+1):
    member_columns = list()
    # Add the per-member columns (E.g., MID, name)
    for data in jotform.pre_fill_data['per_member']:
        member_columns.append(data['fields'][member_num - 1])

    # Add the per-member ministry grid columns
    for grid in jotform.ministry_grids:
        for row in grid.rows:
            col_heading = row['row_heading']
            member_columns.append(col_heading + f" {member_num}")

    jotform_gsheet_columns['members'].append(member_columns)

#--------------------------------------------------------------------------

jotform_gsheet_columns['family'] = [
    'Family names',
    f'CY{stewardship_year-1} pledge',
    f'CY{stewardship_year-1} amount',
    f'CY{stewardship_year} pledge',
    f'CY{stewardship_year} frequency',
    f'CY{stewardship_year} mechanisms',
    'Comments',
]

#--------------------------------------------------------------------------

jotform_gsheet_columns['epilog'] = [
    'IP',
    'Edit Link',
]
