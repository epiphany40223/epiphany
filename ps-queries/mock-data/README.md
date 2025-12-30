AI prompt to generate mock data
===============================

Organizations
-------------

Generate 50 different Organizations.  Each Organization should have
all of the fields listed in the JSON example below:

```
  {
    "organizationID": 9347,
    "organizationTypeID": null,
    "organizationType": "Parish",
    "organizationName": "Epiphany Parish",
    "city": "Louisville",
    "region": null,
    "postalCode": null,
    "childOf": 4860007,
    "childOfName": "All Parishes",
    "entityTypeID": 13,
    "address_1": "914 Old Harrods Creek Rd.",
    "address_2": "",
    "state": "KY",
    "country": "USA",
    "zip": "40223",
    "zipExt": "",
    "phone": "502-555-1212",
    "fax": "",
    "organizationWebSite": "www.ecclou.org",
    "organizationEmail": "business-manager@ecclou.org",
    "vicariateId": 3,
    "regionID": 0,
    "regionName": null,
    "vicariate": "Deanery 3",
    "schoolID": 0,
    "schoolName": null,
    "localOrgID": "009",
    "organizationReportName": "Epiphany Catholic Church",
    "addressTypeID": 2,
    "religiousEducation_GradeChangeOver": "07/01",
    "enrollmentCutOff": "",
    "registrationNumber": "",
    "lastUpdated": "2025-03-06T18:48:33.647"
  }
```

* If a value in the above example is "null", it should also be "null"
  in each of the generated Organizations.

* For each generated Organization, randomly create a unique NAME that
  is suitable for a Roman Catholic Church.
  * Set the organizationName and organizationReportName fields to this
    NAME value.
  * Set the organizationWebSite field to be
    www.DOMAINNAME.example.com, where DOMAINNAME is a FQDN-valid
    abbreviation of the unique NAME of this organization
  * Set the organizationEmail field to be
    business-manager@DOMAINNAME.example.com, using the DOMAINNAME
    value as above

* In each generated Organization, randomly create a 4-digit integer
  value and set that value in the organizationId field.
  * This value must be unique among all organizations.

* Every generated Organization must:
  * Have city = "Louisville"
  * Have state = "KY"
  * Have country = "USA"
  * Have phone = "502-555-1212"
  * Have an entityTypeID = 13
  * Have an organizationType = "Parish"
  * Have address_1 that is a random, plausible street address
  * Have address_2 be blank most of the time, but sometimes have a
    random, plausible 2nd line of a street address.
  * Have zip = a valid US postal code in Louisville, KY, USA
  * Have vicariate = "Deanery X", where X is a random integer
    between 1 and 12.
    * The vicarateId should be the integer value of X

* In each generated Organization, the following fields must have the
  same values as the example:
  * childOf
  * childOfName
  * entityTypeID
  * city
  * state
  * country
  * regionID
  * regionName
  * addressTypeID
  * religiousEducation_GateChangeOver
  * enrollmentCutOff
  * registrationNumber

For any other field that is in the example that was not listed
above, make it the same value as the example.

Write out all the Organizations in JSON format, like the example
above, to a file named "organizations.json".

Family Group List
-----------------

These are a fixed list of group IDs and names:

```
[
  {
    "famGroupID": 1,
    "famGroup": "(blank)"
  },
  {
    "famGroupID": 2,
    "famGroup": "Active"
  },
  {
    "famGroupID": 3,
    "famGroup": "Inactive"
  },
  {
    "famGroupID": 4,
    "famGroup": "Staff"
  },
  {
    "famGroupID": 5,
    "famGroup": "School Only"
  },
  {
    "famGroupID": 6,
    "famGroup": "Religious Ed Only"
  },
  {
    "famGroupID": 7,
    "famGroup": "Moved"
  },
  {
    "famGroupID": 8,
    "famGroup": "Contributor"
  },
  {
    "famGroupID": 9,
    "famGroup": "Sacrament Only"
  },
  {
    "famGroupID": 10,
    "famGroup": "No Surviving Members"
  },
  {
    "famGroupID": 11,
    "famGroup": "Alumni"
  },
  {
    "famGroupID": 12,
    "famGroup": "Unknown"
  },
  {
    "famGroupID": 13,
    "famGroup": "Ministry Only"
  },
  {
    "famGroupID": 14,
    "famGroup": "Associated Non-Parishioner"
  },
  {
    "famGroupID": 15,
    "famGroup": "Friend"
  },
  {
    "famGroupID": 16,
    "famGroup": "Visitor"
  },
  {
    "famGroupID": 17,
    "famGroup": "School Family - Not Registered"
  }
]
```

Write out all the organizations in JSON format, like the example
above, to a file named "family-groups.json".

Families
--------

For each of the generated organizations, generate between 50 to 100
random Families.  Each Family should have all of the fields listed in
the JSON example below:

```
{
  "mailingName": "John Smith",
  "firstName": "John & Amy",
  "lastName": "Smith",
  "eMailAddress": "johnsmith@gmail.example.com",
  "familyHomePhone": null,
  "envelopeNumber": 142,
  "diocesanID": 0,
  "famGroupID": 2,
  "mapCode": null,
  "sDiocesanID": "116840",
  "familyDUID": 156881,
  "familyID": 679,
  "status": true,
  "primaryPhone": null,
  "primaryAddressFull": "1234 Main Dr",
  "primaryAddress1": "1234 Main Dr",
  "primaryAddress2": null,
  "primaryAddress3": null,
  "primaryCity": "Louisville",
  "primaryState": "KY",
  "primaryPostalCode": "40241",
  "primaryZipPlus": "6422",
  "familyParticipationStatus": "Active",
  "hasSuspense": false,
  "ownedMap": true,
  "registeredOrganizationID": 9347,
  "registeredOrganizationNameAndCity": "Epiphany Parish, Louisville",
  "strength": 0,
  "hasMembers": 1,
  "publish_Photo": true,
  "publish_Email": true,
  "publish_Phone": true,
  "publish_Address": true,
  "sendNoMail": false,
  "primaryPublishAddress": true,
  "primaryPublishEMail": true,
  "primaryPublishPhone": true,
  "dateModified": "2024-01-03T00:00:00",
}
```

* If a value in the above example is "null", it should also be "null"
  in each of the generated Families.

* Each generated Family will contain between 1 to 6 Members.
  * Each Family will always have exactly 1 or 2 Heads of the
    Household.  A Head of Household is either:
    * Husband (male)
    * Wife (female)
  * For Families with 2 Heads of Households:
    * Make 80% of them have a Husband and Wife
    * The other 20% can be randomly split between Families with 2
      Husbands and Families with 2 Wives
  * All other Members of the Family will be male or female Children
  * Generate gender-appropriate random first names for all Members of
    each Family.
  * Generate random last names:
    * For a Family with two Heads of Household:
      * For a Family with a Husband and Wife, all Members of this
        Family should share the same last name.
      * For all other Families with two Heads of Household, the
        Children should share the last name with one of the Heads of
        Household.
    * For a Family with a single Head of Household, all Members of
      this Family should share the same last name.

* Each Family must be assigned to one of the Organizations listed in
  the organizations.json file.
  * The Family field registeredOrganizationID should be the
    organizationID from the Organization
  * The Familiy field registeredOrganizationNameAndCity should be the
    organizationName followed by "," and the city of the Organization.

* The Family fields should be set as follows:
  * The firstName, lastName, and mailingName fields are appropriate
    listings of the names of the Heads of Household for that Family.
  * The emailAddress field should be a suitable, valid random email
    address popular email hosting providers, but end all domains with
    "example.com".  For example, if making a random email address
    joe@gmail.com, change the output to be joe@gmail.example.com.
    * The emailAddress must be unique among all generated Families.
  * The envelopeNumber should be a random 4 digit integer that is
    unique among all Families in a given Organization.
  * At least 90% of the generated Families should have a famGroupID of
    2; the remaining 5% can be other valid IDs from the Family Group
    list IDs (from the family-groups.json file).
  * The familyDUID field must be a 6 digit integer.  It must be unique
    among all generated Families.
  * The familyID must be a unique integer.
  * Generate a random street address with a Louisville, KY, USA zip
    code to fill in the primaryAddress* fields.
  * Set a dateModified field of a timestamp within the last 3 months
    in the same format as the example.

For any other field that is in the example that was not listed
above, make it the same value as the example.

Write out all the Families in JSON format, like the example above, to
a file named "families.json".

Members
=======

Each Member generated in the Family section should have all of the
fields listed in the JSON example below:

```
{
  "auxID": null,
  "organizationID": 9347,
  "memberDUID": 1137296,
  "ownerOrganizationID": 9347,
  "familyDUID": 156881,
  "salutation": "Mr.",
  "fullName": "Smith, Johnrey",
  "display_MemberName": "Smith, Johnrey",
  "display_MemberFullName": "Smith, Johnrey",
  "display_FullName": "Smith, Johnrey",
  "firstName": "Johnney",
  "lastName": "Smith",
  "familyLastName": "Smith",
  "birthdate": "1971-08-20T00:00:00",
  "dateOfDeath": null,
  "age": 54,
  "family_HomePhone": null,
  "homePhone": null,
  "workPhone": null,
  "mobilePhone": "502-555-1212",
  "emailAddress": "johnsmith@gmail.example.com",
  "maritalStatusID": 1,
  "maritalStatus": "Married",
  "sex": "M",
  "memberStatus": "Active",
  "memberType": "Husband",
  "careerType": "Engineer",
  "envelopes": 0,
  "envelopeNumber": null,
  "gradYear": null,
  "school": null,
  "education": null,
  "religion": "Catholic",
  "language": "English",
  "ethnicOrigin": "Caucasian",
  "memberDeleted": 0,
  "maidenName": null,
  "family_RegistrationStatus": true,
  "familyDeleted": 0,
  "family_SendNoMail": false,
  "family_PublishAddress": true,
  "family_PublishPhoto": true,
  "family_PublishEMail": true,
  "family_PublishPhone": true,
  "family_ParticipationStatus": "Active",
  "familyAddres_PrimaryAddressFull": "1234 Main Dr",
  "familyAddres_PrimaryCity": "Louisville",
  "familyAddres_PrimaryState": "KY",
  "familyAddres_PrimaryPostalCode": "40241",
  "familyAddres_PrimaryZipPlus": "6422",
  "familyAddres_PrimaryFullPostalCode": "40241 6422",
  "registeredOrganizationID": 9347,
  "registeredOrganizationNameAndCity": "Epiphany Parish, Louisville",
  "birthdate_Year": 1971,
  "birthdate_Month": 8,
  "birthdate_Day": 20,
  "fatherName": null,
  "motherName": null,
  "responsibleAdultName": null,
  "dateModified": "2024-01-03T00:00:00",
}
```

* If a value in the above example is "null", it should also be "null"
  in each of the generated Members, unless explicitly described
  differently below.

* The Member fields should be set as follows:
  * The name-related fields should be set corresponding to the names
    generated in the Families section
  * The age-related fields should be set as follows:
    * Children should be between 0 and 18 years old.
    * No Children within the same Family should be born within 10
      months of each other, unless they were born on exactly the
      same day.
    * Heads of Households should be between 25 and 90 years old,
      assuming that any children in the Family were birthed from when
      at least one of the female Heads of Household were between 18 and 40 years old.
    * Make the ages of the Heads of Households be within 5 years of each other.
  * Salutations can be:
    * For males:
      * For 5% of male Members over the age of 25: Dr.
      * All other males should be Mr.
    * For females:
      * For 5% of female Members over the age of 25: Dr.
      * All other females should be Ms. if they are the only Head of
        Household, or Mrs. if there are 2 Heads of Household.
  * The other name-related fields should be set according to the
    conventions shown in the example.
  * The memberDUID must be a 7-digit integer.  It must be unique
    between all generated Members.
  * The familyDUID should be the same value as the Family that this
    Member belongs to.
  * The maritalStatusID and maritalStatus should be 1 and "Married",
    respectively, if there are 2 Heads of Houshold in this Member's
    Family.  Otherwise, they should be 0 and "Single", otherwise.
  * Set mobilePhone to 502-555-1212.
  * Set sex to "M" for males and "F" for females.
  * Set memberType to "Husband" for Husbands, "Wife" for Wives, and
    "Child" for Children.
  * maidenName should be null for all males and unmarried females.
    For married females, generate a last name.
  * The family* and registeredOrganization* fields should be set
    according to their corresponding values for the Member's Family.
  * Set a dateModified field of a timestamp within the last 3 months
    in the same format as the example.
  * emailAddress should be null for Members who are less than 10
    years old.  Otherwise, they should be suitable email addresses
    per the guidance in the Families section.  Member email addresses
    must be unique between all generated Members.
  * Set the careerType field to be one of 100 different random careers
    for any Member who is over 18 years old.

For any other field that is in the example that was not listed
above, make it the same value as the example.

Write out all the Members in JSON format, like the example above, to
a file named "members.json".
