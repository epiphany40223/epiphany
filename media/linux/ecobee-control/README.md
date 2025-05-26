# Ecobee control

This code was originally authored as a BA Computer Science Capstone
project at the University of Louisville in the Spring semester
of 2025.  See the LICENSE information for more information.

## Summary

Set Ecobee smart thermostat schedules by combining room reservation
data from multiple Google Calendars.

## Goal
Read conference room reservation information from the Google Calendar
REST API. Program smart thermostats to “comfortable” temperatures when
rooms are in use, more energy-efficient temperatures when not.

Epiphany Catholic Church has multiple buildings on a 21-acre campus in
Louisville, KY.  One of the buildings, the Community Center, contains
several reservable meeting rooms.  For simplicity, the heating,
ventilation, and air conditioning (HVAC) controls for the Community
Center are manually set to a constant fixed temperature range.

Epiphany would like to be more energy efficient by automatically
adjusting the HVAC controls based on the dynamic schedule of meetings
in the Community Center.  For example, when no rooms are reserved, the
heating/air conditioning units can be dialed back to conserve energy.

This will entail:

- Reading multiple Google Calendars (each Calendar is the schedule for
  one room)
- Calculating the overall HVAC usage schedule of several physical
  zones in the Community Center (represented by the Google Calendars)
- Setting the schedule of multiple corresponding Ecobee smart
  thermostats accordingly

The above algorithm will need to be run on a continual basis so that
the Ecobee schedules can be updated as rooms are reserved or released,
as room reservations start and end, etc.

---

## Instructions to setup Ecobee API

### 1. Get API Key

1. Login to the Ecobee Consummer portal. https://www.ecobee.com/en-us/
2. To get the API key, go to the top right hand side of the screen and
   press the menu options, and select "DEVELOPER". Your API key will
   be in the Name and Summary section.

### 2. Create the Credentials File

1. Inside your project folder, navigate to:

  ```
  /scripts
  ```
2. Create a new file named:

  ```
  ecobee_credentials.json
  ```
3. Open the file and paste the following template:

  ```json
  {
    "application_key": "application key goes here",
    "access_token": "access token goes here",
    "refresh_token": "refresh token goes here",
    "authorization_token": "authorization token goes here",
  }
  ```
4. Replace `"application key goes here"` with your actual API Key from the
   Ecobee Developer page.

   The others will be filled in automatically.

### 2.  Run the Token Retrieval Script

After setting up your `ecobee_credentials.json`, you need to obtain
your **Access Token** and **Refresh Token**.

1. From the `/scripts` directory, run:

   ```bash
   python Ecobee_Token_Grabber.py
   ```

   This script will:

   - Retrieve an authorization PIN.
   - Ask you to authorize your application on the Ecobee website.
   - Exchange the authorization code for Access and Refresh tokens.

2. Follow the on-screen instructions:

   - Go to [ecobee.com](https://www.ecobee.com/), log in to the web
     portal, and click on the **Profile** tab.
   - Select **My Apps** from the menu on the right and click **Add
     Application**.
   - Paste the provided PIN code into the textbox labeled **"Enter PIN
     code"** and click **Validate**.
   - After authorizing the app, return to your terminal and press
     **Enter** to continue.

After validating, review and authorize the requested permissions.
Once done, return to the terminal and press Enter to continue.

### 3. Create new `ecobee_credentials.json`

1. Inside your project folder, navigate to:

  ```
  /src/ecobee
  ```
2. Create a file named:

  ```
  ecobee_credentials.json
  ```
Once you receive your Access Token and Refresh Token from the script.

Manually update your `ecobee_credentials.json` file to include them,
so it looks like this:

  ```json
  {
    "application_key": "YOUR_API_KEY",
    "access_token": "YOUR_ACCESS_TOKEN",
    "refresh_token": "YOUR_REFRESH_TOKEN"
  }
  ```
---
## Instructions to Set Up Google Calendar API

The steps listed in this readme are a simplified version of the
official guide provided by Google.  If you run into any issues or need
more detailed instructions, refer to the full guide here: [Google
Calendar API Quickstart
(Python)](https://developers.google.com/workspace/calendar/api/quickstart/python)

---

### Enable the API

1. Click the link below to enable the Calendar API in your Google
   Cloud project: [Enable Calendar
   API](https://console.cloud.google.com/flows/enableapi?apiid=calendar-json.googleapis.com)

### Configure the OAuth Consent Screen

If you're using a new Google Cloud project, configure the OAuth
consent screen:

1. In the Google Cloud Console, go to: **Menu > Google Auth Platform >
   Branding** [Go to
   Branding](https://console.cloud.google.com/apis/credentials/consent)
2. If prompted with **"Google Auth platform not configured yet"**,
   click **Get Started**.
3. Fill out the following sections:
   - **App Information**
     - App name (e.g., `Calendar Access App`)
     - User support email
   - Click **Next**
   - **Audience**
     - Select **Internal**
     - Click **Next**
   - **Contact Information**
     - Provide your email address
     - Click **Next**
   - **Finish**
     - Review the **Google API Services User Data Policy**
     - Agree and click **Continue**
   - Click **Create**

---

### Authorize Credentials for a Desktop App

1. Go to:
   **Menu > Google Auth Platform > Clients**
   [Go to Clients](https://console.cloud.google.com/apis/credentials)
2. Click **Create Credentials > OAuth Client ID**
3. Under **Application type**, select **Desktop app**
4. Enter a name for your client (e.g., `Calendar Desktop App`)
5. Click **Create**
6. Download the `.json` file and **rename it to** `application_id.json`

---

### Move Your Credentials File

- Move the `application_id.json` file to the following folder in your
  project:

  ```
  /src/google_calendar/
  ```

---

## Instructions to Build and Run

Follow these steps to set up and run the project:

### 1. Clone the Repository and Set Up Your Python Environment

Clone and Set up your Python environment however you prefer

### 2. Install Dependencies

Navigate to the `src` folder and install the required packages:

```
pip install -r requirements.txt
```
---

### 3. Run the Script

Make sure you have your `application_id.json` file placed inside here:

```
src/google_calendar/
```

Then run the main script:

```
python main.py
```

---

If this is your first time running the script, a browser window will
open prompting you to authorize access to your Google account. After
authorization, your token will be saved locally for future runs.

---

## Instructions to Run in GitHub Actions

1. **Create Your Github Secrets**

- Open Settings
- Click on Secrets and Variables
- Select Actions
- Create the following secrets:
   - `ECOBEE_CREDENTIALS`
   - `GOOGLE_CREDENTIALS`
   - `TOKEN_JSON`

- The following secrets should have this format:
   ```
   ECOBEE_CREDENTIALS {"application_key":"XXXXXXXXXXXXXX", "access_token":"XXXXXXXXXXXXXX", "refresh_token" "XXXXXXXXXXXXXXXX"}
   GOOGLE_CREDENTIALS {"installed": {"client_id":"xxxxxxxxxxxxxxxxx", "project_id" "xxxxx", "auth_uri":"xxxxxxxxxxxxxxxxxxxxxxxx", "token_uri":"xxxxxxxxxxxxxxxx", "auth_provider_x509_cert_url":"xxxxxxxxxxxxxxxx", "client_secret":"XXXXXXX", "redirect_uris":["xxxxxxxx"]}}
   TOKEN_JSON {"token":"xxxxxxxx", "refresh_token":"xxxxxxxx", "token_uri":"xxxxxx", "client_id":"xxxxxx", "client_secret":"xxxxx", "scopes":["xxxxx"], "universe_domain":"xxxxx", "account":"", "expiry":"xxxxx"}
   ```

2. **Place your .yml file inside the .github/workflows/ directory in
the root of your repository**

3. **Check your Actions tab to see the workflow running, logs, and
status**

  - To trigger your workflow manually select the proper workflow under
    the Actions tab on the left side
  - Once on the workflow look for the blue banner at the top of the
    workflow, and click Run Workflow
  - Make sure Use Workflow from is on the proper branch
  - Click the green run workflow button and refresh the page to see
    your workflow

---

## Instructions to Run Tests

1. **Create Test Events in Google Calendar**

   - Open Google Calendar.
   - Create events starting from the current time and covering the next 7 days.
   - Use the following calendars:
     - `Ecobee Test1 Modes`
     - `Ecobee Test2 Modes`
   - Each event should be named using this format:

     ```
     Ecobee <thermostat_name> = <mode>
     ```

     Example:

     ```
     Ecobee Test1 = Occupied
     Ecobee Test2 = Unoccupied
     ```

   - **Available Modes**:
     - `home`: Thermostat is in active use (e.g., people are home).
     - `away`: Thermostat is in away/energy-saving mode.
     - `sleep`: Thermostat is in overnight/sleep settings.

   > Make sure that event names match exactly, including spaces and
   > capitalization, so the scheduling script can parse them
   > correctly.

2. **Run the test calendar creation script**:

   ```bash
   python tests/create_test_calendar.py
   ```

3. **Run the schedule verification script**:

   ```bash
   python tests/schedule_test.py
   ```
4. When all events are covered and the test passes, the expected
   output will print the following:

```bash
SUCCESS: All test intervals are covered by scheduling
```

This setup allows you to test the scheduling behavior without needing
a live Ecobee device.

---

## Authors/Contact Info

* alhussainawiabel@gmail.com
* tanner.jordan@louisville.edu
* zachary.ballard@louisville.edu
* cody.gividen@louisville.edu
