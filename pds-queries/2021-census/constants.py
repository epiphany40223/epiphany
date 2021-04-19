import datetime

import helpers

# Overall title

census_year = 2021

title = f'Census {census_year}'

#--------------------------------------------------------------------------

# SMTP / email basics

smtp_server  = 'smtp-relay.gmail.com'
smtp_from    = f'"Epiphany Catholic Church" <census{census_year}@epiphanycatholicchurch.org>'

#--------------------------------------------------------------------------

# Already submitted PDS Family Status

already_submitted_fam_status = f'{census_year} Census'

#--------------------------------------------------------------------------

# For Census 2021, api.ecc.org is a Digital Ocean droplet running
# Ubuntu and Apache and the PHP in the php subfolder (with free LetEncrypt SSL
# certificates to make everything encrypted).

email_image_url = f'https://api.epiphanycatholicchurch.org/census-{census_year}/ecc-logo.png'
api_base_url    = f'https://api.epiphanycatholicchurch.org/census-{census_year}/?key='

#--------------------------------------------------------------------------

# Google local metadata files
gapp_id         = 'client_id.json'
guser_cred_file = 'user-credentials.json'

# URL of the published Jotform
jotform_url     = 'https://form.jotform.com/203644614900147'

# Copied from the Google Spreadsheet where Jotform is writing its
# results
jotform_gsheet_gfile_id = '12Ksrgp3XI3DFcfwMCpGv1YH6mQA3ZK4W9q1NY_Cunzo'

# Team Drive folder where to upload the CSV/spreadsheet comparison
# output files
upload_team_drive_folder_id = '1XVLa05ySaEpoKPZdMD6eE0BDfF1WoWjU'

gsheet_editors = f'census{census_year}-workers@epiphanycatholicchurch.org'

#--------------------------------------------------------------------------

MAX_PDS_FAMILY_MEMBER_NUM = 7
