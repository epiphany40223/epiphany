This directory has two main scripts:

1. create-ministry-rosters.py: read the PDS SQLite3 database and
   create several XLSX files containing information about members of
   various ministries, which we then upload to Google Drive (and
   convert to Google Spreadsheets).  These spreadsheets are uploaded
   over specific, pre-existing Google Spreadsheets so that their
   contents are wholly replaced without changing their URL / Google
   file identifier.

2. sync-google-group.py: read the PDS SQLite3 database to find all
   members of a given ministry and their associated email addresses.
   Sync the associated Google Group to be exactly that list of email
   addresses.
