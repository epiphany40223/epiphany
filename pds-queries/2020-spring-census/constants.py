import collections
import datetime
import re

import PDSChurch

# Overall title

title = 'Parishioner Information Update 2020'

#--------------------------------------------------------------------------

# SMTP / email basics

smtp_server  = 'smtp-relay.gmail.com'
smtp_from    = '"Epiphany Catholic Church" <parishioner-info-update-2020@epiphanycatholicchurch.org>'

#--------------------------------------------------------------------------

# For Census 2020, api.ecc.org is a Digital Ocean droplet running
# Ubuntu and Apache and the PHP in the php subfolder (with free LetEncrypt SSL
# certificates to make everything encrypted).

email_image_url = 'https://api.epiphanycatholicchurch.org/census-2020/census-logo.png'
api_base_url = 'https://api.epiphanycatholicchurch.org/census-2020/?key='

#--------------------------------------------------------------------------

# Google local metadata files
gapp_id         = 'client_id.json'
guser_cred_file = 'user-credentials.json'

# Copied from the Google Spreadsheets where Jotform is writing its
# results for the form
jotform_gfile_id = '10H8Ugc8u17RA7Ed9AIpoUwzraD1Q8Q0bu9bucEkv_k4'

jotform_base_url = 'https://form.jotform.com/jsquyres/ecc-census-update-2020'

# Team Drive folder where to upload the CSV/spreadsheet comparison
# output files
upload_team_drive_folder_id = '0AJ_f-kASFErxUk9PVA'

# Google group of workers
gsheet_editors = 'parishioner-info-update-2020@epiphanycatholicchurch.org'

# PDS status if Family submitted a paper form (and should not get a reminder email)
already_submitted_fam_status = 'Not used in census 2020'

#--------------------------------------------------------------------------

# This is hard-coded from the
# https://www.jotform.com/build/200034401400025 Jotform

jotform_household_functions = {
    'email_reply'        : lambda data: data['calc']['to_emails'],

    'fid'                : lambda data: data['family']['FamRecNum'],

    'household_name'     : lambda data: data['calc']['to_names'],

    'home_address_line1' : lambda data: data['family']['StreetAddress1'],
    'home_address_line2' : lambda data: data['family']['StreetAddress2'],
    'home_address_city'  : lambda data: data['calc']['city'],
    'home_address_state' : lambda data: data['calc']['state'],
    'home_address_zip'   : lambda data: data['family']['StreetZip'],

    'landline_ac'        : lambda data: data['calc']['landline-area'],
    'landline_phone'     : lambda data: data['calc']['landline-phone'],
}

jotform_household_fields = {
    'email_reply'        : 'emailreply',

    'fid'                : 'fid',

    'household_name'     : 'householdName',

    'home_address_line1' : 'homeAddress[addr_line1]',
    'home_address_line2' : 'homeAddress[addr_line2]',
    'home_address_city'  : 'homeAddress[city]',
    'home_address_state' : 'homeAddress[state]',
    'home_address_zip'   : 'homeAddress[postal]',

    'landline_ac'        : 'landLine[area]',
    'landline_phone'     : 'landLine[phone]',
}

########################################################################

def _make_opt_key_str(mem, key):
    return mem[key] if key in mem else ''

#----------------------------------------------------------------------

def _make_sex_str(mem):
    sex = _make_opt_key_str(mem, 'Gender')
    if sex == '':
        sex = 'Prefer not to say'
    return sex

#----------------------------------------------------------------------

def _make_wedding_date(mem):
    d = _make_opt_key_str(mem, 'marriage_date')
    # Convert string from YYYY-MM-DD to MM-DD-YYYY
    if d != '':
        match = re.search('(\d\d\d\d)-(\d\d)-(\d\d)', d)
        if match:
            year  = str(match.group(1))
            month = str(match.group(2))
            day   = str(match.group(3))

            return month, day, year

    return '', '', ''

def _make_wedding_month_str(mem):
    month, day, year = _make_wedding_date(mem)
    return month

def _make_wedding_day_str(mem):
    month, day, year = _make_wedding_date(mem)
    return day

def _make_wedding_year_str(mem):
    month, day, year = _make_wedding_date(mem)
    return year

#----------------------------------------------------------------------

def _make_email_str(mem):
    emails = PDSChurch.find_any_email(mem)
    if emails is None or len(emails) == 0:
        return ''
    else:
        return emails[0]

#----------------------------------------------------------------------

def _split_phone_str(mem):
    key = 'phones'
    if key not in mem:
        return '', ''

    for phone in mem[key]:
        if phone['type'] == 'Cell':
            match = re.search('\((\d\d\d)\) (\d\d\d-\d\d\d\d)', phone['number'])
            if match:
                return match.group(1), match.group(2)

    return '', ''

def _make_cell_ac_str(mem):
    ac, phone = _split_phone_str(mem)
    return ac

def _make_cell_phone_str(mem):
    ac, phone = _split_phone_str(mem)
    return phone

#----------------------------------------------------------------------

def _make_talents_str(mem):
    talents = list()
    for talent in mem['active_talents']:
        talents.append(talent['Description'])

    return ', '.join(talents)

#----------------------------------------------------------------------

def _split_language_str(mem):
    key = 'language'
    if key not in mem:
        return '', ''

    l = mem[key].strip()
    tokens = l.split('/')

    # This is kinda terrible
    # "Eng" is a frequent abbreviation for "English" in the PDS data set
    # So convert that back.
    new_tokens = list()
    for t in tokens:
        if t == 'Eng':
            new_tokens.append("English")
        else:
            new_tokens.append(t.strip())

    primary = new_tokens.pop(0)
    return primary, ', '.join(new_tokens)

def _make_primary_comm_str(mem):
    primary, additional = _split_language_str(mem)
    return primary

def _make_additional_comm_str(mem):
    primary, additional = _split_language_str(mem)
    return additional

########################################################################

# Member functions

jotform_member_functions = {
    'mid'                 : lambda mem: mem['MemRecNum'],
    'title'               : lambda mem: mem['prefix'],
    'first_name'          : lambda mem: mem['first'],
    'nick_name'           : lambda mem: mem['nickname'],
    'middle_name'         : lambda mem: mem['middle'],
    'last_name'           : lambda mem: mem['last'],
    'suffix'              : lambda mem: mem['suffix'],
    'year_of_birth'       : lambda mem: mem['YearOfBirth'],
    'email'               : lambda mem: _make_email_str(mem),
    'cell_ac'             : lambda mem: _make_cell_ac_str(mem),
    'cell_phone'          : lambda mem: _make_cell_phone_str(mem),
    'sex'                 : lambda mem: _make_sex_str(mem),
    'marital_status'      : lambda mem: _make_opt_key_str(mem, 'marital_status'),
    'wedding_month'       : lambda mem: _make_wedding_month_str(mem),
    'wedding_day'         : lambda mem: _make_wedding_day_str(mem),
    'wedding_year'        : lambda mem: _make_wedding_year_str(mem),
    'occupation'          : lambda mem: _make_opt_key_str(mem, 'occupation'),
    'employer'            : lambda mem: mem['Location'],
    'skills'              : lambda mem: _make_opt_key_str(mem, 'skills'),
    'talents'             : lambda mem: _make_talents_str(mem), # talents
    'ethnicity'           : lambda mem: _make_opt_key_str(mem, 'ethnic'),
    'primary_language'    : lambda mem: _make_primary_comm_str(mem),
    'additional_language' : lambda mem: _make_additional_comm_str(mem),
}

# Jotform member fields

jotform_member_fields = list()

# Member 1
jotform_member_fields.append({
    'mid'                 : 'mid1',
    'title'               : 'title',
    'first_name'          : 'legalFirst',
    'nick_name'           : 'nicknameonly',
    'middle_name'         : 'middleName',
    'last_name'           : 'lastName39',
    'suffix'              : 'suffixif',
    'year_of_birth'       : 'yearOf',
    'email'               : 'preferredEmail',
    'cell_ac'             : 'cellPhone[area]',
    'cell_phone'          : 'cellPhone[phone]',
    'sex'                 : 'sex',
    'marital_status'      : 'maritalStatus66',
    'wedding_month'       : 'weddingDate[month]',
    'wedding_day'         : 'weddingDate[day]',
    'wedding_year'        : 'weddingDate[year]',
    'occupation'          : 'occupationif',
    'employer'            : 'employer',
    'skills'              : 'doYou',
    'talents'             : 'doYou52',
    'ethnicity'           : 'ethnicity',
    'primary_language'    : 'primaryCommunication',
    'additional_language' : 'additionalCommunication88',
})

# Member 2
jotform_member_fields.append({
    'mid'                 : 'mid2',
    'title'               : 'title90',
    'first_name'          : 'legalFirst91',
    'nick_name'           : 'nicknameonly92',
    'middle_name'         : 'middleName93',
    'last_name'           : 'lastName',
    'suffix'              : 'suffixif95',
    'year_of_birth'       : 'yearOf96',
    'email'               : 'preferredEmail99',
    'cell_ac'             : 'cellPhone100[area]',
    'cell_phone'          : 'cellPhone100[phone]',
    'sex'                 : 'sex101',
    'marital_status'      : 'maritalStatus',
    'wedding_month'       : 'weddingDate103[month]',
    'wedding_day'         : 'weddingDate103[day]',
    'wedding_year'        : 'weddingDate103[year]',
    'occupation'          : 'occupationif104',
    'employer'            : 'employer105',
    'skills'              : 'doYou106',
    'talents'             : 'doYou107',
    'ethnicity'           : 'ethnicity108',
    'primary_language'    : 'primaryCommunication111',
    'additional_language' : 'additionalCommunication',
})

# Member 3
jotform_member_fields.append({
    'mid'                 : 'mid3',
    'title'               : 'title135',
    'first_name'          : 'legalFirst113',
    'nick_name'           : 'nicknameonly114',
    'middle_name'         : 'middleName115',
    'last_name'           : 'lastName116',
    'suffix'              : 'suffixif117',
    'year_of_birth'       : 'yearOf118',
    'email'               : 'preferredEmail20',
    'cell_ac'             : 'cellPhone119[area]',
    'cell_phone'          : 'cellPhone119[phone]',
    'sex'                 : 'sex120',
    'marital_status'      : 'maritalStatus121',
    'wedding_month'       : 'weddingDate122[month]',
    'wedding_day'         : 'weddingDate122[day]',
    'wedding_year'        : 'weddingDate122[year]',
    'occupation'          : 'occupationif123',
    'employer'            : 'employer124',
    'skills'              : 'doYou125',
    'talents'             : 'doYou126',
    'ethnicity'           : 'ethnicity127',
    'primary_language'    : 'primaryCommunication128',
    'additional_language' : 'additionalCommunication129',
})

# Member 4
jotform_member_fields.append({
    'mid'                 : 'mid4',
    'title'               : 'title134',
    'first_name'          : 'legalFirst136',
    'nick_name'           : 'nicknameonly137',
    'middle_name'         : 'middleName138',
    'last_name'           : 'lastName139',
    'suffix'              : 'suffixif140',
    'year_of_birth'       : 'yearOf141',
    'email'               : 'preferredEmail142',
    'cell_ac'             : 'cellPhone143[area]',
    'cell_phone'          : 'cellPhone143[phone]',
    'sex'                 : 'sex144',
    'marital_status'      : 'maritalStatus145',
    'wedding_month'       : 'weddingDate146[month]',
    'wedding_day'         : 'weddingDate146[day]',
    'wedding_year'        : 'weddingDate146[year]',
    'occupation'          : 'occupationif147',
    'employer'            : 'employer149',
    'skills'              : 'doYou148',
    'talents'             : 'doYou150',
    'ethnicity'           : 'ethnicity151',
    'primary_language'    : 'primaryCommunication152',
    'additional_language' : 'additionalCommunication153',
})

# Member 5
jotform_member_fields.append({
    'mid'                 : 'mid5',
    'title'               : 'title167',
    'first_name'          : 'legalFirst168',
    'nick_name'           : 'nicknameonly171',
    'middle_name'         : 'middleName169',
    'last_name'           : 'lastName170',
    'suffix'              : 'suffixif172',
    'year_of_birth'       : 'yearOf173',
    'email'               : 'preferredEmail174',
    'cell_ac'             : 'cellPhone175[area]',
    'cell_phone'          : 'cellPhone175[phone]',
    'sex'                 : 'sex176',
    'marital_status'      : 'maritalStatus177',
    'wedding_month'       : 'weddingDate178[month]',
    'wedding_day'         : 'weddingDate178[day]',
    'wedding_year'        : 'weddingDate178[year]',
    'occupation'          : 'occupationif179',
    'employer'            : 'employer180',
    'skills'              : 'doYou181',
    'talents'             : 'doYou182',
    'ethnicity'           : 'ethnicity183',
    'primary_language'    : 'primaryCommunication184',
    'additional_language' : 'additionalCommunication185',
})

# Member 6
jotform_member_fields.append({
    'mid'                 : 'mid6',
    'title'               : 'title186',
    'first_name'          : 'legalFirst187',
    'nick_name'           : 'nicknameonly188',
    'middle_name'         : 'middleName189',
    'last_name'           : 'lastName190',
    'suffix'              : 'suffixif191',
    'year_of_birth'       : 'yearOf192',
    'email'               : 'preferredEmail193',
    'cell_ac'             : 'cellPhone194[area]',
    'cell_phone'          : 'cellPhone194[phone]',
    'sex'                 : 'sex195',
    'marital_status'      : 'maritalStatus196',
    'wedding_month'       : 'weddingDate197[month]',
    'wedding_day'         : 'weddingDate197[day]',
    'wedding_year'        : 'weddingDate197[year]',
    'occupation'          : 'occupationif198',
    'employer'            : 'employer199',
    'skills'              : 'doYou200',
    'talents'             : 'doYou201',
    'ethnicity'           : 'ethnicity202',
    'primary_language'    : 'primaryCommunication203',
    'additional_language' : 'additionalCommunication205',
})

# Member 7
jotform_member_fields.append({
    'mid'                 : 'mid7',
    'title'               : 'title165',
    'first_name'          : 'legalFirst206',
    'nick_name'           : 'nicknameonly207',
    'middle_name'         : 'middleName208',
    'last_name'           : 'lastName209',
    'suffix'              : 'suffixif210',
    'year_of_birth'       : 'yearOf211',
    'email'               : 'preferredEmail212',
    'cell_ac'             : 'cellPhone213[area]',
    'cell_phone'          : 'cellPhone213[phone]',
    'sex'                 : 'sex214',
    'marital_status'      : 'maritalStatus215',
    'wedding_month'       : 'weddingDate216[month]',
    'wedding_day'         : 'weddingDate216[day]',
    'wedding_year'        : 'weddingDate216[year]',
    'occupation'          : 'occupationif218',
    'employer'            : 'employer219',
    'skills'              : 'doYou217',
    'talents'             : 'doYou220',
    'ethnicity'           : 'ethnicity221',
    'primary_language'    : 'primaryCommunication222',
    'additional_language' : 'additionalCommunication223',
})
