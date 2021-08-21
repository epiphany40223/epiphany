#!/usr/bin/env python3
#
# Helper routines
#

import sys
import os
import re

import constants

# We assume that there is a "ecc-python-modules" sym link in this directory that points to the directory with ECC.py and friends.
moddir = os.path.join(os.path.dirname(sys.argv[0]), 'ecc-python-modules')
if not os.path.exists(moddir):
    print("ERROR: Could not find the ecc-python-modules directory.")
    print("ERROR: Please make a ecc-python-modules sym link and run again.")
    exit(1)

sys.path.insert(0, moddir)

import PDSChurch

from datetime import datetime
from datetime import timedelta

#--------------------------------------------------------------------------

def jotform_date_to_datetime(d):
    # Google is showing three different date formats, depending on how
    # the volumn is formatted (even though they're actually just
    # different representations of the same date).  Shug.  Handle them
    # all.
    result = re.match('(\d{4})-(\d{2})-(\d{2}) (\d{1,2}):(\d{2}):(\d{2})', d)
    if result is not None:
        submit_date = datetime(year   = int(result.group(1)),
                               month  = int(result.group(2)),
                               day    = int(result.group(3)),
                               hour   = int(result.group(4)),
                               minute = int(result.group(5)),
                               second = int(result.group(6)))

    else:
        result = re.match('(\d{1,2})/(\d{1,2})/(\d{4}) (\d{1,2}):(\d{2}):(\d{2})', d)
        if result:
            submit_date = datetime(year   = int(result.group(3)),
                                   month  = int(result.group(1)),
                                   day    = int(result.group(2)),
                                   hour   = int(result.group(4)),
                                   minute = int(result.group(5)),
                                   second = int(result.group(6)))

        else:
            # According to
            # https://www.ablebits.com/office-addins-blog/2019/08/13/google-sheets-change-date-format/,
            # Google Sheets uses "0" as December 30, 1899.
            submit_date = datetime(month=12, day=30, year=1899)

            delta = timedelta(days=float(d))
            submit_date += delta

    return submit_date

#--------------------------------------------------------------------------

def url_escape(s):
    return s.replace('\"', '\\"')

def pkey_url(env_id):
    return "' {0}".format(str(env_id).strip())

#############################################################################

# This class doesn't hold Family or Member data.  It's really just a vehicle for
# holding a bunch of lambda functions for computing values to pre-fill into
# Jotform fields.
class jotform_class:
    def __init__(self, url):
        self.url               = url
        self.hh_pre_fill_data  = list()
        self.mem_pre_fill_data = dict()
        for i in range(0, constants.MAX_PDS_FAMILY_MEMBER_NUM):
            self.mem_pre_fill_data[i] = list()

    def _make_pre_filled_data(self, name, func, jotform_field):
        return {
            'name'          : name,
            'value_func'    : func,
            'jotform_field' : jotform_field,
        }

    def add_family_pre_fill_data(self, name, func, jotform_field):
        data = self._make_pre_filled_data(name, func, jotform_field)
        self.hh_pre_fill_data.append(data)

    def add_member_pre_fill_data(self, name, func, jotform_base_field):
        for i in range(0, constants.MAX_PDS_FAMILY_MEMBER_NUM):
            # This is tied to a specific Jotform field name.
            # The field names are 1-indexed, while the member numbers here
            # are 0-indexed, so add 1 when making the field name.
            data = self._make_pre_filled_data(name, func,
                f'hm{i+1}_{jotform_base_field}')
            self.mem_pre_fill_data[i].append(data)

#----------------------------------------------------------------------------

jotform = jotform_class(constants.jotform_url)

#----------------------------------------------------------------------------

# This is used for both the Family and the Member
PHONE_AC   = 'area code'
PHONE_NUM  = 'number'
PHONE_TYPE = 'type'

def _get_phone(fam_or_mem, type, preference):
    key = 'phones'
    found = None
    if key in fam_or_mem:
        for phone in fam_or_mem[key]:
            if 'Emergency' in phone['type']:
                # We definitely do not want this
                pass
            elif phone['type'] == preference:
                # This is the best one.  We'll take it.
                found = phone
                # If we find this, we're done (because it's the best) -- exit
                # the loop.
                break

            # Anything else is second preference; we'll take it.  But we'll keep
            # going through the loop to see if we can find the main preference.
            found = phone

    if found:
        # We found a found number.
        # Hueristic: AC is the first one, number is the rest
        parts = phone['number'].split(' ')
        ac    = parts[0]
        # PDS will put the area code inside (). Strip those off, because
        # Jotform will put the area code result in the Google sheet in ().
        if ac.startswith('('):
            ac = ac[1:]
        if ac.endswith(')'):
            ac = ac[:-1]
        num   = ' '.join(parts[1:])

        if type == PHONE_AC:
            return ac
        elif type == PHONE_NUM:
            return num
        elif type == PHONE_TYPE:
            if phone['type'] == 'Home':
                # This is a specific radio button on the Jotform
                return 'Landline'
            else:
                # This is a specific radio button on the Jotform
                return 'Cell / Mobile'

        else:
            raise Exception("Invalid phone type requested")

    else:
        # We did not find a phone number, so return no data
        return None

#----------------------------------------------------------------------------

# These Jotform fields are for the overall Family

jotform.add_family_pre_fill_data('FID',
                    lambda fam: fam['FamRecNum'],
                    'fid')
jotform.add_family_pre_fill_data('Emails for Jotform to send response to',
                    lambda fam: ','.join(fam['census']['to_addresses']),
                    'emailreply')

jotform.add_family_pre_fill_data('Household name',
                    lambda fam: fam['last_name_salutation'],
                    'hh_name')
jotform.add_family_pre_fill_data('Household street address 1',
                    lambda fam: fam['StreetAddress1'],
                    'hh_address[addr_line1]')
jotform.add_family_pre_fill_data('Household street address 2',
                    lambda fam: fam['StreetAddress2'],
                    'hh_address[addr_line2]')
jotform.add_family_pre_fill_data('Household city',
                    lambda fam: fam['city'],
                    'hh_address[city]')
jotform.add_family_pre_fill_data('Household state',
                    lambda fam: fam['state'],
                    'hh_address[state]')
jotform.add_family_pre_fill_data('Household zip',
                    lambda fam: fam['StreetZip'],
                    'hh_address[postal]')

jotform.add_family_pre_fill_data('Household phone AC - we have it',
                    lambda fam: _get_phone(fam, type=PHONE_AC, preference='Home'),
                    'hh_phone1[area]')
jotform.add_family_pre_fill_data('Household phone # - we have it',
                    lambda fam: _get_phone(fam, type=PHONE_NUM, preference='Home'),
                    'hh_phone1[phone]')
jotform.add_family_pre_fill_data('Household phone type - we have it',
                    lambda fam: _get_phone(fam, type=PHONE_TYPE, preference='Home'),
                    'hh_phoneType')
jotform.add_family_pre_fill_data('Household phone AC - we do not have it',
                    lambda fam: _get_phone(fam, type=PHONE_AC, preference='Home'),
                    'hh_phone2[area]')
jotform.add_family_pre_fill_data('Household phone # - we do not have it',
                    lambda fam: _get_phone(fam, type=PHONE_NUM, preference='Home'),
                    'hh_phone2[phone]')

MASS_WEEKDAY = 'Weekly'
MASS_SPANISH = 'Spanish'
MASS_530     = '5:30pm'
MASS_900     = '9:00am'
MASS_1130    = '11:30am'

# These values are radio buttons on the Jotform
FREQ_NEVER     = 'Never'
FREQ_RARELY    = 'Rarely'
FREQ_SOMETIMES = 'Sometimes'
FREQ_USUALLY   = 'Usually'

def _hh_mass(fam, search):
    key = 'keywords'
    if key in fam:
        keywords = fam[key]
        for keyword in keywords:
            if search in keyword:
                for freq in [FREQ_NEVER, FREQ_RARELY, FREQ_SOMETIMES, FREQ_USUALLY]:
                    if freq in keyword:
                        return freq

    # If we get here, we didn't find a matching keyword
    return None

jotform.add_family_pre_fill_data('Household weekday mass',
                    lambda fam: _hh_mass(fam, search=MASS_WEEKDAY),
                    'hh_massWeekday')
jotform.add_family_pre_fill_data('Household spanish mass',
                    lambda fam: _hh_mass(fam, search=MASS_SPANISH),
                    'hh_massSpanish')
jotform.add_family_pre_fill_data('Household weekend mass: 5:30',
                    lambda fam: _hh_mass(fam, search=MASS_530),
                    'hh_massWeekend[0]')
jotform.add_family_pre_fill_data('Household weekend mass: 9:00',
                    lambda fam: _hh_mass(fam, search=MASS_900),
                    'hh_massWeekend[1]')
jotform.add_family_pre_fill_data('Household weekend mass: 11:30',
                    lambda fam: _hh_mass(fam, search=MASS_1130),
                    'hh_massWeekend[2]')

#----------------------------------------------------------------------------

jotform.add_member_pre_fill_data('mid',
                    lambda mem: mem['MemRecNum'],
                    'mid')
jotform.add_member_pre_fill_data('Title',
                    lambda mem: mem['prefix'],
                    'title')
jotform.add_member_pre_fill_data('First name',
                    lambda mem: mem['first'],
                    'first')
jotform.add_member_pre_fill_data('Nick name',
                    lambda mem: mem['nickname'],
                    'nick')
jotform.add_member_pre_fill_data('Middle name',
                    lambda mem: mem['middle'],
                    'middle')
jotform.add_member_pre_fill_data('Last name',
                    lambda mem: mem['last'],
                    'last')
jotform.add_member_pre_fill_data('Suffix',
                    lambda mem: mem['suffix'],
                    'suffix')

jotform.add_member_pre_fill_data('Month of birth',
                    lambda mem: mem['MonthOfBirth'],
                    'mob')
jotform.add_member_pre_fill_data('Year of birth',
                    lambda mem: mem['YearOfBirth'],
                    'yob')

jotform.add_member_pre_fill_data('Cell area code',
                    lambda mem: _get_phone(mem, type=PHONE_AC, preference='Cell'),
                    'cell[area]')
jotform.add_member_pre_fill_data('Cell phone number',
                    lambda mem: _get_phone(mem, type=PHONE_NUM, preference='Cell'),
                    'cell[phone]')

jotform.add_member_pre_fill_data('Preferred email',
                    lambda mem: PDSChurch.find_any_email(mem)[0] if PDSChurch.find_any_email(mem) else '',
                    'email')

EMAILS_YES = 'Yes, please!'
EMAILS_NO  = 'No thanks'

def _ecc_happenings_email(member):
    key = 'keywords'
    if key in member:
        if 'Parish-wide Email' in member[key]:
            return EMAILS_YES

    return None

jotform.add_member_pre_fill_data('Epiphany Happenings email',
                    lambda mem: _ecc_happenings_email(mem),
                    'emails[0]')
jotform.add_member_pre_fill_data('Obituaries email',
                    lambda mem: _ecc_happenings_email(mem),
                    'emails[1]')

# Automatic opt-in for HoH+Spouse for tax+business emails, automatic opt-out for
# every other Member in the Family.
jotform.add_member_pre_fill_data('Tax documents emails',
                    lambda mem: EMAILS_YES if PDSChurch.is_member_hoh_or_spouse(mem) else EMAILS_NO,
                    'emails[2]')
jotform.add_member_pre_fill_data('Business emails',
                    lambda mem: EMAILS_YES if PDSChurch.is_member_hoh_or_spouse(mem) else EMAILS_NO,
                    'emails[3]')

# Return "yes" if the Family sometimes/usually attends Weekday mass and
# the member is HoH or spouse
def _weekday_mass_email(member):
    family = member['family']
    key = 'keywords'

    happy = False
    if key in family:
        for keyword in family[key]:
            keyword = keyword.lower()
            if MASS_WEEKDAY.lower() in keyword:
                if 'sometimes' in keyword or 'usually' in keyword:
                    if PDSChurch.is_member_hoh_or_spouse(member):
                        return EMAILS_YES
                    else:
                        return EMAILS_NO
                else:
                    return EMAILS_NO

    return None

jotform.add_member_pre_fill_data('Weekday mails email email',
                    lambda mem: _weekday_mass_email(mem),
                    'emails[4]')

jotform.add_member_pre_fill_data('Sex',
                    lambda mem: mem['Gender'],
                    'sex')

jotform.add_member_pre_fill_data('Marital status',
                    lambda mem: mem['marital_status'] if 'marital_status' in mem else None,
                    'marital')

WEDDING_MONTH = "month"
WEDDING_DAY   = "day"
WEDDING_YEAR  = "year"

def _wedding_date(mem, type):
    key = 'marriage_date'
    if key not in mem:
        return None

    # PDS may record 12/30/1899 in this field if it has no wedding date.
    # So treat any year <1900 as empty.
    if mem[key].year < 1900:
        return None

    if type == WEDDING_MONTH:
        return mem[key].month
    elif type == WEDDING_DAY:
        return mem[key].day
    elif type == WEDDING_YEAR:
        return mem[key].year
    else:
        raise Exception("Invalid wedding date type requested")

jotform.add_member_pre_fill_data('Wedding date',
                    lambda mem: _wedding_date(mem, WEDDING_MONTH),
                    'wedding[month]')
jotform.add_member_pre_fill_data('Wedding date',
                    lambda mem: _wedding_date(mem, WEDDING_DAY),
                    'wedding[day]')
jotform.add_member_pre_fill_data('Wedding date',
                    lambda mem: _wedding_date(mem, WEDDING_YEAR),
                    'wedding[year]')

LANG_CHECK      = 'check'
LANG_OTHER      = 'other'

LANG_ON_JOTFORM = ['ASL', 'English', 'French', 'German', 'Spanish']

# This is processing for a radio button: one of many
def _mem_primary_language(member, return_value):
    key = 'language'
    if key not in member:
        return None

    # In PDS, we have "American Sign Language", on Jotform we have "ASL"
    languages  = member[key].replace('American Sign Language', 'ASL')
    parts      = languages.split('/')
    primary    = parts[0].strip()

    if return_value == LANG_CHECK:
        if primary in LANG_ON_JOTFORM:
            return primary
        else:
            return "Other"
    elif return_value == LANG_OTHER:
        if primary in LANG_ON_JOTFORM:
            return None
        else:
            return primary
    else:
        raise Exception(f"Invalid language type requested")

    # Should never get here -- this is just for defensive programming
    return None

jotform.add_member_pre_fill_data('Primary communication language',
                    lambda mem: _mem_primary_language(mem, LANG_CHECK),
                    'primaryLang')
jotform.add_member_pre_fill_data('Primary communication language other',
                    lambda mem: _mem_primary_language(mem, LANG_OTHER),
                    'primaryLang[other]')

# This is processing for checkboxes: many of many
def _mem_additional_language(member, return_value):
    key = 'language'
    if key not in member:
        return None

    # In PDS, we have "American Sign Language", on Jotform we have "ASL"
    languages = member[key].replace('American Sign Language', 'ASL')
    # Skip the primary (0th entry)
    parts     = languages.split('/')[1:]
    if len(parts) == 0:
        return None

    checks = dict()
    others = list()
    for language in parts:
        if language in LANG_ON_JOTFORM:
            checks[language] = True
        else:
            checks['Others'] = True
            others.append(language)

    if return_value == LANG_CHECK:
        # Jotform wants a comma-delimited list for selecting multiple checkboxes
        return ','.join(checks.keys())
    elif return_value == LANG_OTHER:
        return '/'.join(others)
    else:
        raise Exception(f"Invalid language type requested")

    # Should never get here -- this is just for defensive programming
    return None

jotform.add_member_pre_fill_data('Additional communication languages',
                    lambda mem: _mem_additional_language(mem, LANG_CHECK),
                    'additionalLang')
jotform.add_member_pre_fill_data('Additional communication languages other',
                    lambda mem: _mem_additional_language(mem, LANG_OTHER),
                    'additionalLang[other]')

STUDENT_BOOL   = 'bool'
STUDENT_SCHOOL = 'school'

STUDENT_YES = 'Yes'
STUDENT_NO  = 'No'

def _mem_student(mem, type):
    key = 'occupation'
    if key not in mem:
        return None

    student = False
    school  = None

    occupation = mem[key].lower()
    if occupation == 'student':
        student = True
        key = 'Location'
        if key in mem:
            school = mem[key]

    if type == STUDENT_BOOL:
        return STUDENT_YES if student else STUDENT_NO
    elif type == STUDENT_SCHOOL:
        return school
    else:
        raise Exception("Requested invalid student type")

jotform.add_member_pre_fill_data('Are you a student',
                    lambda mem: _mem_student(mem, STUDENT_BOOL),
                    'student')
jotform.add_member_pre_fill_data('School attending',
                    lambda mem: _mem_student(mem, STUDENT_SCHOOL),
                    'school')

EMPLOYED_BOOL       = 'bool'
EMPLOYED_OCCUPATION = 'occupation'
EMPLOYED_EMPLOYER   = 'employer'

EMPLOYED_YES = 'Yes'
EMPLOYED_NO  = 'No'

def _mem_employed(mem, type):
    key = 'occupation'
    if key not in mem:
        return None

    employed    = False
    occuptation = None
    employer    = None

    student = _mem_student(mem, STUDENT_BOOL)
    if student == STUDENT_YES:
        if type == EMPLOYED_BOOL:
            return EMPLOYED_NO
        else:
            return None

    key = 'occupation'
    if key in mem:
        occupation = mem[key].strip()
    key = 'Location'
    if key in mem:
        employer = mem[key].strip()

    if type == EMPLOYED_BOOL:
        return EMPLOYED_YES if len(occupation) + len(employer) > 0 else EMPLOYED_NO
    elif type == EMPLOYED_OCCUPATION:
        return occupation
    elif type == EMPLOYED_EMPLOYER:
        return employer
    else:
        raise Exception("Requested invalid employed type")

jotform.add_member_pre_fill_data('Are you employed/retired',
                    lambda mem: _mem_employed(mem, EMPLOYED_BOOL),
                    'employed')
jotform.add_member_pre_fill_data('Occupation',
                    lambda mem: _mem_employed(mem, EMPLOYED_OCCUPATION),
                    'occupation')
jotform.add_member_pre_fill_data('Employer',
                    lambda mem: _mem_employed(mem, EMPLOYED_EMPLOYER),
                    'employer')
