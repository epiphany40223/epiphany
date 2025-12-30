#!/usr/bin/env python3

import json
import logging
import random
import re
from datetime import datetime, timedelta

# --- LOGGING SETUP ---
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# --- SEED DATA ---
CATHOLIC_NAMES = [
    "St. Jude Thaddeus", "Our Lady of Lourdes", "Holy Spirit", "St. Bernadette", "St. Francis of Assisi",
    "Cathedral of the Assumption", "St. Agnes", "St. Margaret Mary", "St. Albert the Great", "St. Stephen Martyr",
    "Holy Trinity", "St. Patrick", "St. Gabriel", "St. Martha", "St. James", "St. Barnabas", "St. Raphael",
    "Holy Name", "St. Bartholomew", "St. Athanasius", "St. Lawrence", "St. Paul", "St. Polycarp",
    "St. Peter the Apostle", "Mary Help of Christians", "St. Elizabeth Ann Seton", "St. Rita", "St. Michael",
    "St. Edward", "St. Pius X", "St. John Vianney", "St. Thomas More", "St. Denis", "St. Helen",
    "Church of the Incarnation", "St. Aloysius", "St. Boniface", "St. Martin of Tours", "St. Therese",
    "St. George", "St. Cecilia", "Christ the King", "St. Benedict", "St. Augustine", "Holy Cross",
    "St. Joseph", "Epiphany Catholic Church", "St. Peter Claver", "St. Gregory", "St. Monica"
]
LOUISVILLE_ZIPS = [
    "40202", "40203", "40204", "40205", "40206", "40207", "40208", "40217",
    "40220", "40222", "40223", "40241", "40245", "40291", "40299", "40201",
    "40209", "40210", "40211", "40212", "40213", "40214", "40215", "40216",
    "40218", "40219", "40228", "40229", "40242", "40243", "40272", "40280",
    "40281", "40282", "40292"
]
STREETS = [
    "Bardstown Rd", "Shelbyville Rd", "Dixie Hwy", "Newburg Rd",
    "Taylorsville Rd", "Preston Hwy", "Winchester Rd", "Trevillian Way",
    "Hikes Ln", "Poplar Level Rd", "Lexington Rd", "Cherokee Rd",
    "Grinstead Dr"
]
FIRST_NAMES_M = [
    "John", "Michael", "James", "Robert", "William", "David",
    "Christopher", "Joseph", "Thomas", "Daniel", "Paul", "Mark", "Donald",
    "George", "Kenneth", "Steven", "Edward", "Brian", "Ronald", "Anthony",
    "Matthew", "Andrew", "Joshua", "Ryan", "Nicholas", "Alexander", "Kevin",
    "Jason", "Timothy", "Richard", "Charles", "Jeffrey", "Eric", "Stephen",
    "Raymond", "Gregory", "Benjamin", "Samuel", "Patrick", "Frank", "Scott",
    "Justin", "Brandon", "Peter", "Harold", "Henry", "Carl", "Arthur",
    "Douglas", "Dennis", "Jerry", "Lawrence", "Walter", "Tyler", "Nathan",
    "Albert", "Roy", "Eugene", "Ralph", "Russell", "Louis", "Philip",
    "Bruce", "Adam", "Harry", "Wayne", "Billy", "Steve", "Randy", "Howard",
    "Carlos", "Bobby", "Victor", "Martin", "Ernest", "Phillip", "Todd",
    "Jesse", "Craig", "Alan", "Shawn", "Clarence", "Sean", "Chris",
    "Johnny", "Earl", "Jimmy", "Antonio", "Danny", "Bryan", "Tony", "Luis",
    "Mike", "Stanley", "Leonard", "Dale", "Manuel", "Rodney", "Curtis",
    "Norman", "Allen", "Marvin", "Vincent", "Glenn", "Jeffery", "Travis",
    "Jacob", "Lee", "Melvin", "Alfred", "Kyle", "Francis", "Bradley",
    "Jesus", "Herbert", "Frederick", "Ray", "Joel", "Edwin", "Don", "Eddie",
    "Ricky", "Troy", "Randall", "Barry"
]
FIRST_NAMES_F = [
    "Mary", "Patricia", "Jennifer", "Linda", "Elizabeth", "Barbara",
    "Susan", "Jessica", "Sarah", "Karen", "Nancy", "Margaret", "Lisa",
    "Betty", "Dorothy", "Sandra", "Ashley", "Kimberly", "Donna", "Emily",
    "Michelle", "Carol", "Amanda", "Melissa", "Deborah", "Stephanie",
    "Rebecca", "Laura", "Sharon", "Cynthia", "Kathleen", "Amy", "Shirley",
    "Angela", "Helen", "Anna", "Brenda", "Pamela", "Nicole", "Samantha",
    "Katherine", "Emma", "Ruth", "Christine", "Catherine", "Debra",
    "Rachel", "Carolyn", "Janet", "Virginia", "Maria", "Heather", "Diane",
    "Julie", "Joyce", "Victoria", "Olivia", "Kelly", "Christina", "Lauren",
    "Joan", "Evelyn", "Judith", "Megan", "Cheryl", "Andrea", "Hannah",
    "Jacqueline", "Martha", "Gloria", "Teresa", "Ann", "Sara", "Madison",
    "Frances", "Kathryn", "Janice", "Jean", "Abigail", "Alice", "Judy",
    "Sophia", "Grace", "Denise", "Amber", "Doris", "Marilyn", "Danielle",
    "Beverly", "Isabella", "Theresa", "Diana", "Natalie", "Brittany",
    "Charlotte", "Marie", "Kayla", "Alexis", "Lori", "Julia", "Jamie",
    "Monica", "Rose", "Ava", "Phyllis", "Crystal", "Ella", "Mia", "Elaine",
    "Irene", "Claire", "Rita", "Tiffany", "Carmen", "Cindy", "Wendy",
    "Edna", "Valerie", "Sue", "Lucy"
]
LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
    "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez",
    "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin",
    "Lee", "Thompson", "White", "Harris", "Clark", "Lewis", "Robinson",
    "Walker", "Young", "Allen", "King", "Wright", "Scott", "Torres",
    "Nguyen", "Hill", "Flores", "Green", "Adams", "Nelson", "Baker", "Hall",
    "Rivera", "Campbell", "Mitchell", "Carter", "Roberts", "Gomez",
    "Phillips", "Evans", "Turner", "Diaz", "Parker", "Cruz", "Edwards",
    "Collins", "Reyes", "Stewart", "Morris", "Morales", "Murphy", "Cook",
    "Rogers", "Gutierrez", "Ortiz", "Morgan", "Cooper", "Peterson",
    "Bailey", "Reed", "Kelly", "Howard", "Ramos", "Kim", "Cox", "Ward",
    "Richardson", "Watson", "Brooks", "Chavez", "Wood", "James", "Bennett",
    "Gray", "Mendoza", "Ruiz", "Hughes", "Price", "Alvarez", "Castillo",
    "Sanders", "Patel", "Myers", "Long", "Ross", "Foster", "Jimenez",
    "Powell", "Jenkins", "Perry", "Russell", "Sullivan", "Bell", "Coleman",
    "Butler", "Henderson", "Barnes", "Gonzales", "Fisher", "Vasquez",
    "Simmons", "Romero", "Jordan", "Patterson", "Alexander", "Hamilton",
    "Graham", "Reynolds", "Griffin", "Wallace", "Moreno", "West", "Cole",
    "Hayes", "Bryant", "Herrera", "Gibson", "Ellis", "Tran", "Medina",
    "Aguilar", "Stevens", "Murray", "Ford", "Castro", "Marshall", "Owens",
    "Harrison"
]

# Fixed Family Group List
FAMILY_GROUPS = [
    {"famGroupID": 1, "famGroup": "(blank)"},
    {"famGroupID": 2, "famGroup": "Active"},
    {"famGroupID": 3, "famGroup": "Inactive"},
    {"famGroupID": 4, "famGroup": "Staff"},
    {"famGroupID": 5, "famGroup": "School Only"},
    {"famGroupID": 6, "famGroup": "Religious Ed Only"},
    {"famGroupID": 7, "famGroup": "Moved"},
    {"famGroupID": 8, "famGroup": "Contributor"},
    {"famGroupID": 9, "famGroup": "Sacrament Only"},
    {"famGroupID": 10, "famGroup": "No Surviving Members"},
    {"famGroupID": 11, "famGroup": "Alumni"},
    {"famGroupID": 12, "famGroup": "Unknown"},
    {"famGroupID": 13, "famGroup": "Ministry Only"},
    {"famGroupID": 14, "famGroup": "Associated Non-Parishioner"},
    {"famGroupID": 15, "famGroup": "Friend"},
    {"famGroupID": 16, "famGroup": "Visitor"},
    {"famGroupID": 17, "famGroup": "School Family - Not Registered"}
]

# Career Types
CAREER_TYPES = [
    "Accountant", "Actor", "Architect", "Artist", "Attorney", "Auditor",
    "Baker", "Banker", "Barber", "Bartender", "Biologist", "Bookkeeper",
    "Butcher", "Carpenter", "Cashier", "Chef", "Chemist", "Civil Engineer",
    "Clergy", "Consultant", "Contractor", "Counselor", "Dancer", "Dentist",
    "Designer", "Developer", "Dietitian", "Electrician", "Engineer",
    "Entrepreneur", "Farmer", "Financial Advisor", "Firefighter",
    "Flight Attendant", "Florist", "Geologist", "Graphic Designer",
    "Hairdresser", "Healthcare Administrator", "HR Manager", "Insurance Agent",
    "Interior Designer", "IT Specialist", "Janitor", "Jeweler", "Journalist",
    "Judge", "Landscaper", "Lawyer", "Librarian", "Machinist", "Manager",
    "Marketing Specialist", "Mathematician", "Mechanic", "Medical Assistant",
    "Musician", "Nurse", "Nutritionist", "Optometrist", "Painter",
    "Paramedic", "Pharmacist", "Photographer", "Physical Therapist",
    "Physician", "Pilot", "Plumber", "Police Officer", "Programmer",
    "Project Manager", "Psychologist", "Public Relations", "Real Estate Agent",
    "Receptionist", "Recruiter", "Respiratory Therapist", "Retail Manager",
    "Sales Representative", "Secretary", "Security Guard", "Social Worker",
    "Software Engineer", "Surgeon", "Systems Analyst", "Teacher",
    "Technical Writer", "Technician", "Therapist", "Translator", "Truck Driver",
    "Veterinarian", "Waiter", "Web Developer", "Welder", "Writer",
    "Zoologist", "Administrative Assistant", "Customer Service Representative",
    "Data Analyst", "Database Administrator", "Editor", "Event Planner",
    "Fashion Designer", "Film Producer", "Laboratory Technician"
]

# --- TRACKERS FOR UNIQUENESS ---
used_org_ids = set()
used_family_duids = set()
used_member_duids = set()
used_emails = set()
used_family_ids = set()

# --- UTILS ---
def get_ts():
    """Generates a timestamp within business hours (9-5) in the last 3 months."""
    end = datetime(2025, 12, 30, 17, 0)
    dt = end - timedelta(days=random.randint(0, 90))
    dt = dt.replace(hour=random.randint(9, 16), minute=random.randint(0, 59), second=random.randint(0, 59))
    ts = dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]
    logging.debug(f"Generated timestamp: {ts}")
    return ts

def get_uid(s, start, end):
    while True:
        val = random.randint(start, end)
        if val not in s:
            s.add(val)
            logging.debug(f"Generated unique ID: {val} (range: {start}-{end})")
            return val

def get_email(f, l):
    base = f"{f.lower()}.{l.lower()}"
    email = f"{base}@gmail.example.com"
    count = 1
    while email in used_emails:
        email = f"{base}{count}@gmail.example.com"
        count += 1
    used_emails.add(email)
    logging.debug(f"Generated unique email: {email}")
    return email

# --- DATA GENERATION ---
def run_generation():
    logging.info("Starting mock data generation...")
    organizations = []
    families = []
    members = []

    # 1. Generate 50 Organizations
    logging.info("Generating 50 organizations...")
    for i in range(50):
        name = CATHOLIC_NAMES[i]
        org_id = get_uid(used_org_ids, 1000, 9999)
        domain = re.sub(r'[^a-z]', '', name.lower())[:10]
        vic_id = random.randint(1, 12)
        zip_code = random.choice(LOUISVILLE_ZIPS)
        ts = get_ts()

        org = {
            "organizationID": org_id,
            "organizationTypeID": None,
            "organizationType": "Parish",
            "organizationName": name,
            "city": "Louisville",
            "region": None,
            "postalCode": None,
            "childOf": 4860007,
            "childOfName": "All Parishes",
            "entityTypeID": 13,
            "address_1": f"{random.randint(100, 9999)} {random.choice(STREETS)}",
            "address_2": "Suite " + str(random.randint(1, 50)) if random.random() < 0.1 else "",
            "state": "KY",
            "country": "USA",
            "zip": zip_code,
            "zipExt": "",
            "phone": "502-555-1212",
            "fax": "",
            "organizationWebSite": f"www.{domain}.example.com",
            "organizationEmail": f"business-manager@{domain}.example.com",
            "vicariateId": vic_id,
            "regionID": 0,
            "regionName": None,
            "vicariate": f"Deanery {vic_id}",
            "schoolID": 0,
            "schoolName": None,
            "localOrgID": f"{i+1:03}",
            "organizationReportName": name,
            "addressTypeID": 2,
            "religiousEducation_GradeChangeOver": "07/01",
            "enrollmentCutOff": "",
            "registrationNumber": "",
            "lastUpdated": ts
        }
        organizations.append(org)
        logging.debug(f"Created organization {i+1}/50: {name} (ID: {org_id})")

        # 2. Generate 50-100 Families per Org
        num_families = random.randint(50, 100)
        logging.info(f"Generating {num_families} families for organization '{name}'...")
        org_env_nums = set()
        for fam_idx in range(num_families):
            f_size = random.randint(1, 6)
            num_heads = 1 if f_size == 1 else random.randint(1, 2)
            f_duid = get_uid(used_family_duids, 100000, 999999)
            f_id = get_uid(used_family_ids, 1, 100000)

            heads = []
            if num_heads == 2:
                r = random.random()
                l1 = random.choice(LAST_NAMES)
                if r < 0.8: # Husband/Wife
                    heads = [{'sex': 'M', 'type': 'Husband', 'last': l1}, {'sex': 'F', 'type': 'Wife', 'last': l1}]
                elif r < 0.9: # 2 Husbands
                    heads = [{'sex': 'M', 'type': 'Husband', 'last': l1}, {'sex': 'M', 'type': 'Husband', 'last': random.choice(LAST_NAMES)}]
                else: # 2 Wives
                    heads = [{'sex': 'F', 'type': 'Wife', 'last': l1}, {'sex': 'F', 'type': 'Wife', 'last': random.choice(LAST_NAMES)}]
            else:
                s = random.choice(['M', 'F'])
                heads = [{'sex': s, 'type': 'Husband' if s == 'M' else 'Wife', 'last': random.choice(LAST_NAMES)}]

            for h in heads:
                h['first'] = random.choice(FIRST_NAMES_M if h['sex'] == 'M' else FIRST_NAMES_F)

            kids = []
            for _k in range(f_size - num_heads):
                k_sex = random.choice(['M', 'F'])
                k_last = heads[0]['last'] if num_heads == 1 or heads[0]['last'] == heads[1]['last'] else random.choice([heads[0]['last'], heads[1]['last']])
                kids.append({'sex': k_sex, 'type': 'Child', 'first': random.choice(FIRST_NAMES_M if k_sex == 'M' else FIRST_NAMES_F), 'last': k_last})

            while True:
                env = random.randint(1000, 9999)
                if env not in org_env_nums:
                    org_env_nums.add(env)
                    break

            f_zip = random.choice(LOUISVILLE_ZIPS)
            f_street = f"{random.randint(100, 9999)} {random.choice(STREETS)}"
            f_zip_plus = str(random.randint(1000, 9999))

            f_obj = {
                "mailingName": f"{heads[0]['first']} {heads[0]['last']}" if num_heads == 1 else f"{heads[0]['first']} & {heads[1]['first']} {heads[0]['last']}",
                "firstName": heads[0]['first'] if num_heads == 1 else f"{heads[0]['first']} & {heads[1]['first']}",
                "lastName": heads[0]['last'],
                "eMailAddress": get_email(heads[0]['first'], heads[0]['last']),
                "familyHomePhone": None,
                "envelopeNumber": env,
                "diocesanID": 0,
                "famGroupID": 2 if random.random() < 0.9 else random.randint(3, 17),
                "mapCode": None,
                "sDiocesanID": str(random.randint(100000, 999999)),
                "familyDUID": f_duid,
                "familyID": f_id,
                "status": True,
                "primaryPhone": None,
                "primaryAddressFull": f_street,
                "primaryAddress1": f_street,
                "primaryAddress2": None,
                "primaryAddress3": None,
                "primaryCity": "Louisville",
                "primaryState": "KY",
                "primaryPostalCode": f_zip,
                "primaryZipPlus": f_zip_plus,
                "familyParticipationStatus": "Active",
                "hasSuspense": False,
                "ownedMap": True,
                "registeredOrganizationID": org_id,
                "registeredOrganizationNameAndCity": f"{name}, Louisville",
                "strength": 0,
                "hasMembers": f_size,
                "publish_Photo": True,
                "publish_Email": True,
                "publish_Phone": True,
                "publish_Address": True,
                "sendNoMail": False,
                "primaryPublishAddress": True,
                "primaryPublishEMail": True,
                "primaryPublishPhone": True,
                "dateModified": ts
            }
            families.append(f_obj)
            logging.debug(f"Created family {fam_idx+1}/{num_families} for org '{name}': {f_obj['mailingName']} (DUID: {f_duid}, size: {f_size})")

            # 3. Generate Members
            logging.debug(f"Generating {f_size} members for family {f_obj['mailingName']}...")

            # Determine if there are children and any female heads
            has_children = len(kids) > 0
            female_heads = [h for h in heads if h['sex'] == 'F']

            today = datetime(2025, 12, 30)

            # Generate ages and birthdates for heads of household
            head_ages = []
            head_birthdates = []

            if has_children and len(female_heads) > 0:
                # At least one female head must have been 18-40 when oldest child was born
                oldest_child_age = random.randint(0, 18)
                # Female head was between 18-40 when child was born
                mother_birth_age = random.randint(18, 40)
                mother_current_age = oldest_child_age + mother_birth_age
                # Ensure mother is within valid range (25-90)
                mother_current_age = max(25, min(90, mother_current_age))

                if num_heads == 2:
                    # Assign mother_current_age to first female head
                    # Second head within 5 years
                    min_age = max(25, mother_current_age - 5)
                    max_age = min(90, mother_current_age + 5)
                    second_age = random.randint(min_age, max_age)
                    head_ages = [mother_current_age, second_age]
                else:
                    # Single female head
                    head_ages = [mother_current_age]

                # Generate birthdates for children with 10-month spacing rule
                child_birthdates = []

                # Generate oldest child's birthdate
                oldest_birth_year = today.year - oldest_child_age
                oldest_birth_month = random.randint(1, 12)
                oldest_birth_day = random.randint(1, 28)
                oldest_birthdate = datetime(oldest_birth_year, oldest_birth_month, oldest_birth_day)
                child_birthdates.append(oldest_birthdate)

                # Generate younger siblings' birthdates
                for _ in range(len(kids) - 1):
                    # Randomly decide if this is a twin/triplet (5% chance)
                    is_multiple = random.random() < 0.05 and len(child_birthdates) > 0

                    if is_multiple:
                        # Same birthdate as previous sibling
                        new_birthdate = child_birthdates[-1]
                    else:
                        # At least 10 months after previous sibling
                        prev_birthdate = child_birthdates[-1]
                        # 10 months = ~304 days
                        min_days_apart = 304
                        max_days_apart = (today - prev_birthdate).days

                        if max_days_apart > min_days_apart:
                            days_after = random.randint(min_days_apart, max_days_apart)
                            new_birthdate = prev_birthdate + timedelta(days=days_after)
                        else:
                            # If not enough time has passed, make them at least 10 months younger
                            new_birthdate = prev_birthdate + timedelta(days=min_days_apart)

                    child_birthdates.append(new_birthdate)

                # Sort birthdates (oldest first) and calculate ages
                child_birthdates.sort()
                child_ages = [(today - bd).days // 365 for bd in child_birthdates]
            else:
                # No children or no female heads - use original logic
                if num_heads == 2:
                    first_age = random.randint(25, 90)
                    head_ages.append(first_age)
                    # Second head within 5 years, but still in valid range
                    min_age = max(25, first_age - 5)
                    max_age = min(90, first_age + 5)
                    second_age = random.randint(min_age, max_age)
                    head_ages.append(second_age)
                else:
                    head_ages.append(random.randint(25, 90))

                # Generate random child birthdates with 10-month spacing
                child_birthdates = []
                for k_idx in range(len(kids)):
                    if k_idx == 0:
                        # First child - random age 0-18
                        child_age = random.randint(0, 18)
                        birth_year = today.year - child_age
                        birth_month = random.randint(1, 12)
                        birth_day = random.randint(1, 28)
                        child_birthdates.append(datetime(birth_year, birth_month, birth_day))
                    else:
                        # Subsequent children - respect 10-month rule
                        is_multiple = random.random() < 0.05 and len(child_birthdates) > 0

                        if is_multiple:
                            child_birthdates.append(child_birthdates[-1])
                        else:
                            prev_birthdate = child_birthdates[-1]
                            min_days_apart = 304
                            max_days_apart = (today - prev_birthdate).days

                            if max_days_apart > min_days_apart:
                                days_after = random.randint(min_days_apart, max_days_apart)
                                child_birthdates.append(prev_birthdate + timedelta(days=days_after))
                            else:
                                child_birthdates.append(prev_birthdate + timedelta(days=min_days_apart))

                # Sort and calculate ages
                child_birthdates.sort()
                child_ages = [(today - bd).days // 365 for bd in child_birthdates]

            # Generate birthdates for heads based on their ages
            for age in head_ages:
                birth_year = today.year - age
                birth_month = random.randint(1, 12)
                birth_day = random.randint(1, 28)
                head_birthdates.append(datetime(birth_year, birth_month, birth_day))

            for idx, p in enumerate(heads + kids):
                # Assign age and birthdate based on member type
                if p['type'] in ['Husband', 'Wife']:
                    m_age = head_ages.pop(0)
                    birthdate = head_birthdates.pop(0)
                else:
                    m_age = child_ages.pop(0)
                    birthdate = child_birthdates.pop(0)

                # Determine salutation
                if p['sex'] == 'M':
                    # Males: 5% over 25 get Dr., all others get Mr.
                    sal = "Dr." if m_age > 25 and random.random() < 0.05 else "Mr."
                else:
                    # Females
                    if m_age > 25 and random.random() < 0.05:
                        sal = "Dr."
                    elif m_age < 18:
                        sal = "Ms."
                    else:
                        # 18+ females: Ms. if single head, Mrs. if 2 heads
                        sal = "Mrs." if num_heads == 2 else "Ms."

                member_duid = get_uid(used_member_duids, 1000000, 9999999)

                # Format birthdate
                birthdate_str = birthdate.strftime("%Y-%m-%dT00:00:00")
                birth_year = birthdate.year
                birth_month = birthdate.month
                birth_day = birthdate.day

                # Determine marital status
                marital_status_id = 1 if num_heads == 2 and p['type'] != 'Child' else 0
                marital_status = "Married" if marital_status_id == 1 else "Single"

                # Generate maiden name for married females
                maiden_name = None
                if p['sex'] == 'F' and marital_status == "Married":
                    maiden_name = random.choice(LAST_NAMES)

                # Only generate email for members 10 years old or older
                member_email = get_email(p['first'], p['last']) if m_age >= 10 else None

                # Assign career type for members over 18 years old
                career_type = random.choice(CAREER_TYPES) if m_age > 18 else None

                member = {
                    "auxID": None,
                    "organizationID": org_id,
                    "memberDUID": member_duid,
                    "ownerOrganizationID": org_id,
                    "familyDUID": f_duid,
                    "salutation": sal,
                    "fullName": f"{p['last']}, {p['first']}",
                    "display_MemberName": f"{p['last']}, {p['first']}",
                    "display_MemberFullName": f"{p['last']}, {p['first']}",
                    "display_FullName": f"{p['last']}, {p['first']}",
                    "firstName": p['first'],
                    "lastName": p['last'],
                    "familyLastName": p['last'],
                    "birthdate": birthdate_str,
                    "dateOfDeath": None,
                    "age": m_age,
                    "family_HomePhone": None,
                    "homePhone": None,
                    "workPhone": None,
                    "mobilePhone": "502-555-1212",
                    "emailAddress": member_email,
                    "maritalStatusID": marital_status_id,
                    "maritalStatus": marital_status,
                    "sex": p['sex'],
                    "memberStatus": "Active",
                    "memberType": p['type'],
                    "careerType": career_type,
                    "envelopes": 0,
                    "envelopeNumber": None,
                    "gradYear": None,
                    "school": None,
                    "education": None,
                    "religion": "Catholic",
                    "language": "English",
                    "ethnicOrigin": "Caucasian",
                    "memberDeleted": 0,
                    "maidenName": maiden_name,
                    "family_RegistrationStatus": True,
                    "familyDeleted": 0,
                    "family_SendNoMail": False,
                    "family_PublishAddress": True,
                    "family_PublishPhoto": True,
                    "family_PublishEMail": True,
                    "family_PublishPhone": True,
                    "family_ParticipationStatus": "Active",
                    "familyAddres_PrimaryAddressFull": f_street,
                    "familyAddres_PrimaryCity": "Louisville",
                    "familyAddres_PrimaryState": "KY",
                    "familyAddres_PrimaryPostalCode": f_zip,
                    "familyAddres_PrimaryZipPlus": f_zip_plus,
                    "familyAddres_PrimaryFullPostalCode": f"{f_zip} {f_zip_plus}",
                    "registeredOrganizationID": org_id,
                    "registeredOrganizationNameAndCity": f"{name}, Louisville",
                    "birthdate_Year": birth_year,
                    "birthdate_Month": birth_month,
                    "birthdate_Day": birth_day,
                    "fatherName": None,
                    "motherName": None,
                    "responsibleAdultName": None,
                    "dateModified": ts
                }
                members.append(member)
                logging.debug(f"Created member: {p['first']} {p['last']} (DUID: {member_duid}, Type: {p['type']}, Age: {m_age})")

    # Save all to JSON
    logging.info(f"Generation complete. Created {len(organizations):,} organizations, {len(families):,} families, {len(members):,} members.")
    logging.info("Saving data to JSON files...")

    with open('organizations.json', 'w') as f:
        json.dump(organizations, f, indent=2)
        logging.info(f"Saved {len(organizations):,} organizations to organizations.json")

    with open('family-groups.json', 'w') as f:
        json.dump(FAMILY_GROUPS, f, indent=2)
        logging.info(f"Saved {len(FAMILY_GROUPS):,} family groups to family-groups.json")

    with open('families.json', 'w') as f:
        json.dump(families, f, indent=2)
        logging.info(f"Saved {len(families):,} families to families.json")

    with open('members.json', 'w') as f:
        json.dump(members, f, indent=2)
        logging.info(f"Saved {len(members):,} members to members.json")

if __name__ == "__main__":
    logging.info("=" * 60)
    logging.info("ParishSoft Mock Data Generator")
    logging.info("=" * 60)
    run_generation()
    logging.info("=" * 60)
    logging.info("Mock data generation completed successfully!")
    logging.info("=" * 60)