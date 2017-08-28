# Notes

The scripts in this directory are not polished.  They were written for
one-time uses to convert several specific shared Google Folders to
Google Team Drives.  Each of the scripts has some hard-coded
assupmtions that are certainly not true for everyone's particular
setups of shared folders / team drives.  Additionally, since they were
intended for one-time use, they really aren't polished, or, in some
cases, complete (e.g., sometimes it was easier/faster to leave the
script incomplete and then just manually use the Google Drive web UI
to fix up what the script didn't do).

# Making a Google Account client_id.json file:

1. Make a project in the Google APIs dashboard:

    https://console.developers.google.com/apis/dashboard

2. Click "Enable API"

3. Select "Google Drive API"

4. It says "A project is needed to enable APIs".  Click on the "Create
Project" button.

5. Takes you to another page with another "Create" button to create a
project.

6. Name the project: "Python Drive access", and create it.

7. Enable the Google Drive API on this project.

8. Now create some credentials:
   - Google Drive API
   - Other UI (CLI tool)
   - User data

9. Click "What credentials do I need?"

10. Name the client "Python CLI client"

11. Click "Create client ID"

12. Pick any email address (e.g., the default is fine), and type in
"Python CLI Client" in the product name field.  Click continue.

13. Click "Download" to download client_id.json file.  Save the
client_id.json file somewhere safe.

14. Click "Done"
