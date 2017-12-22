This directory has two main scripts:

1. sync-mailman.py: reads the PDS SQLite3 database to find all
   parishioners with a specific keyword and makes a text file
   containing all their email addresses.  This text file is then
   scp'ed to the ECC mailman listserver (another Linux machine), and
   that text file is used to re-seed the parishioner listserve.

2. sync-google-group.py: read the PDS SQLite3 database to find all
   members of a given ministry and their associated email addresses.
   Sync the associated Google Group to be exactly that list of email
   addresses.
