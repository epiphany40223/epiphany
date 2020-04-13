# Google Uploader Python client

## Instructions to setup Ubuntu

```
# pip3 install --upgrade httplib2
# pip3 install --upgrade google-api-python-client oauth2client
```

## Setting up credentials

Setting up and downloading credentials from the Google cloud console:

1. Go to console.cloud.google.com
1. Make a project
1. Go to "APIs and Credentials"
1. Enable APIs and services
   1. Enable the "Google Drive API"
1. Credentials
1. Make a new credentia / select "Help me Choose"
   1. Select that we're using the Google Drive API
   1. Select "Other UI (Windows, CLI tool)"
   1. Select "User data"
   1. Make the credentials
   1. Download the JSON client secret file
   1. The google uploader script defaults to looking for
      `client_id.json` (vs. the lengthy, unique filename that you
      likely downloaded).

## Obtaininig specific user credentials

Using the `client_id.json` that you just downloaded:

1. Run the script on a machine where you have access to a web browser.
   1. It will open a Google auth page on the browser.
   1. Complete the google auth.
   1. When done, a `user_credentials.json` file will be written.
   1. This file can be copied to the machine where the script will be
      run for real.
