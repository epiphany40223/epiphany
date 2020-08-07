import collections
import datetime

# Overall title

title = 'Stewardship 2021'

# Start and end dates for the stewardship year

stewardship_begin_date = datetime.date(year=2021, month=1,  day=1)
stewardship_end_date   = datetime.date(year=2021, month=12, day=31)

#--------------------------------------------------------------------------

# SMTP / email basics

smtp_server  = 'smtp-relay.gmail.com'
smtp_from    = '"Epiphany Catholic Church" <stewardship2021@epiphanycatholicchurch.org>'

#--------------------------------------------------------------------------

# Already submitted PDS Family Status

already_submitted_fam_status = '2021 Stewardship'

#--------------------------------------------------------------------------

# For Stewardship 2020, redirect.ecc.org is a Digital Ocean droplet running
# Ubuntu and Apache and the PHP in the php subfolder (with free LetEncrypt SSL
# certificates to make everything encrypted).

email_image_url = 'https://api.epiphanycatholicchurch.org/stewardship-2021/stewardship-logo.png'
api_base_url = 'https://api.epiphanycatholicchurch.org/stewardship-2021/?key='

#--------------------------------------------------------------------------

# Google local metadata files
gapp_id         = 'client_id.json'
guser_cred_file = 'user-credentials.json'

# Copied from the Google Spreadsheets where Jotform is writing its
# results for the 2 forms
jotform_member_gfile_id = '1xaML3DvqtQHXvP4thbAUvs1e1_fIRs3RZSFvFtkeLAU'
jotform_family_gfile_id = '1XEdlMXJvXstwfp8uENnBXykZaQIcozgOpcRZuzURt8c'

# Team Drive folder where to upload the CSV/spreadsheet comparison
# output files
upload_team_drive_folder_id = '1yi_bqpRZS4RywnJ1TPP_BGYdi8tC7Frz'

gsheet_editors = 'stewardship2021-workers@epiphanycatholicchurch.org'

#--------------------------------------------------------------------------

# For members who change their ministry data, start / end dates to use

ministry_start_date = '11/01/2020'
ministry_end_date   = ministry_start_date

#--------------------------------------------------------------------------

# This is hard-coded from the
# https://www.jotform.com/build/91944902477164 Jotform
# Use an OrderedDict to keep the keys in order
jotform_ministry_groups = collections.OrderedDict()
jotform_ministry_groups['parishLeadership'] = 'Parish Leadership'
jotform_ministry_groups['administrationMinistries67'] = 'Administration'
jotform_ministry_groups['liturgicalPreparatory'] = 'Liturgical Prepatory'
jotform_ministry_groups['liturgicalCelebratory'] = 'Liturgical Celebratory'
jotform_ministry_groups['stewardshipamp'] = 'Stewardship & Evangelization'
jotform_ministry_groups['helpingamp'] = 'Helping & Healing'
jotform_ministry_groups['socialamp'] = 'Social & Fellowship'
jotform_ministry_groups['socialResponsibility'] = 'Social Responsibility'
jotform_ministry_groups['formationalMinistries'] = 'Formational'

# NOTE: The 1st level keys MUST of jotform_member_ministries match the
# keys of jotform_ministry_groups.
jotform_member_ministries = {
    'parishLeadership' : [
        '100-Parish Pastoral Council',
        '101-Long Range Plan Team',
        '102-Finance Advisory Council',
        '103-Worship Committee',
        '104-Stewardship & E Committee',
        '105-Youth Ministry Leadership',
        '106-Community Life Committee',
        '107-Social Resp Steering Comm',
        '108-Formation Team',
    ],
    'administrationMinistries67' : [
        '200-Audit Committee',
        '201-Collection Counter',
        '202-Facility Mgmt & Planning',
        '203-Garden & Grounds',
        '204-Parish Office Volunteers',
        '205-Participation Sheet Vol',
        '206-Space Arrangers',
        '207-Technology Committee',
        '208-Weekend Closer',
    ],
    'liturgicalPreparatory' : [
        '300-Art & Environment',
        '301-Audio/Visual/Light Minstry',
        '302-Bread Baking Ministry',
        '303-Linens/Vestments Ministry',
        '304-Liturgical Planning',
        '305-Movers Ministry',
        '306-Music Support for Children',
        '307-Wedding Assistant',
        '308-Worship&Music Support Team',
    ],
    'liturgicalCelebratory' : [
#        '309-Acolytes INTERESTED ONLY',
        [
            '309-Acolytes INTERESTED ONLY',
            '309A-Acolyte Ministry 5:30P',
            '309B-Acolyte Ministry  9:00A',
            '309C-Acolyte Ministry 11:30A',
        ],
        '310-Adult Choir',
        '311-Bell Choir',
        "312-Children's Music Ministry",
        '313-Communion Ministers',
        '314-Communion Min. Coordinator',
        '315-Funeral Mass Ministry',
#        '316-Greeters INTERESTED ONLY',
        [
            '316-Greeters INTERESTED ONLY',
            '316A-Greeters 5:30P',
            '316B-Greeters 9:00A',
            '316C-Greeters 11:30A'
        ],
        '317-Instrumentalists & Cantors',
#        '318-Lectors  MASTER LIST',
        [
            '318-Lectors  MASTER LIST',
            '318A-Lector Ministry  5:30P',
            '318B-Lector  Ministry 9:00A',
            '318C-Lector Ministry 11:30A',
        ],
        '319-Liturgical Dance Ministry',
        '320-Prayer Ministry Support',
    ],
    'stewardshipamp' : [
        '400-Communications Committee',
        '401-Epiphany Companions',
        '402-New Members Coffee',
        '403-Small Prayer Groups',
        '404-Welcome Desk',
        '405-Parish Mission Plan Team',
        '406-Evangelization Working Grp',
        '407-Stewardship Working Grp',
    ],
    'helpingamp' : [
        '500-BereavementReceptionSupprt',
        '501-Care of Sick: Communion',
        '502-Care of Sick: Meals',
        '503-Childcare Ministry: Adult',
        '504-DivorceCare',
        '505-Healing Blanket Ministry',
        '506-Prayer Chain Ministry',
        '507-Grief Support Team',
        '508-Messages of Hope Ministry',
    ],
    'socialamp' : [
        '600-Men of Epiphany',
        '601-Sages (for 50 yrs. +)',
        '602-Singles Explore Life (SEL)',
        '603-Soup Supper Ministry',
        '604-Wednesdays for Women',
        '605- Sunday Morning Coffee',
        '606-Kitchen Volunteer Ministry',
        '607-Easter Egg Plan Team',
        '608-Memorial Day Plan Team',
        '609-Trunk or Treat Plan Team',
        '610-Feast of Epiphany PlanTeam',
    ],
    'socialResponsibility' : [
        '700-Advocates for Common Good',
        '701-C.L.O.U.T./Justice Network',
        '702-Epiphany Backside Ministry',
        '703-Eyeglass Ministry',
        '704-Habitat for Humanity',
        '705-Hunger & Poverty Ministry',
        '706-Prison Ministry',
        '707-St. Vincent DePaul',
        '708-Ten Percent Committee',
        '709-Twinning Committee:Chiapas',
    ],
    'formationalMinistries' : [
        '800-ChildrenFormationCatechist',
        '801-Confirmation Prep Team',
        '802-GathTheChildren Catechist',
        '803-Youth Ministry Adult Leader',
        '804-Hispanic Ministry Team',
        '805-Monday Adult Bible Study',
        '806-Scripture Sharing Group',
        '807-RCIA Team',
        '808-Young Adult Ministry',
        '809-Sunday Adult Form. Spanish',
        '810-Childrens Form. Workng Grp',
        '811-Family Form. Working Group',
        '812-Adult Form. Working Group',
    ],
}

# These are the fields in the Jotform ministry results spreadsheet
# The ordering of these fields is critical, although the names are not
jotform_member_fields = [
    'SubmitDate',
    'EnvId',
    'mid',
    'Name',
    'DateCreated',
]

for group in jotform_ministry_groups:
    for ministry in jotform_member_ministries[group]:
        jotform_member_fields.append(ministry)

jotform_member_fields.append('Comments')
jotform_member_fields.append('IP')
jotform_member_fields.append('JotformSubmissionID')
jotform_member_fields.append('EditLink')

# These are the fields in the Jotform pledge results spreadsheet
# The ordering of these fields is critical, although the names are not
jotform_family_fields = [
    'SubmitDate',
    'EnvId',
    'fid',
    'Names',
    '2020 pledge',
    'CY2020 amount',
    '2021 pledge',
    '2021 frequency',
    '2021 mechanism',
    'Comments',
    'IP',
    'JotformSubmissionID',
    'EditLink',
]
