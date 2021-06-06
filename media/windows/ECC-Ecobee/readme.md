# ECC Ecobee
## Epiphany Catholic Church - Ecobee Thermostat Data Retrieval

## Overview
This application will poll information for the Ecobee thermostats for Epiphany Catholic Church and write the resultant data to a SQLite database.

The data retrieved is extensive -- the Ecobee service provides detailed data covering over two dozen record types (even more for utility customers).  Some of this data is maintained on a historical basis, for our purposes here, primarily historical runtime information.  This data is reported from the thermostats every 15 minutes or so (more frequently on equipment status changes), and is maintained on intervals of every 5 minutes.  This historical data is quite large, with 288 records maintained for each thermostat for each day (12 5-min. increments * 24 hours).  So, retrieving 90 days of information will result in almost 26,000 records for one thermostat.

Additional thermostat details are available as a snapshot in time for most of the remaining record types.  This includes point-in-time information on items such as current settings, notifications, programs, events, firmware version, etc.

The application will first poll the historical runtime information for each thermostat.  The timeframe for each iteration is determined by examining the existing data from the SQLite database to determine the last revision interval (5-minute time slice) that was reported and written.  It will then poll the Ecobee service to determine the latest interval that was reported to the service.  If newer information is available, it will then be requested.  This process follows the recommendations given on the Ecobee site to avoid unnecessary polling requests (see [Thermostat Summary Polling](https://www.ecobee.com/home/developer/api/documentation/v1/operations/get-thermostat-summary.shtml) for more details).

If no runtime information is currently available in the database, the application will default to using the first-reported date retrieved for this thermostat from the Ecobee service (essentially the in-service date).  Data requests for the runtime information only support up to 31 days retrieval per request; therefore, larger requests must be broken up into smaller ones not to exceed this limit.  The application automatically determines the retrieval window and will adjust the polling requests to accommodate this restriction.  This is generally only an issue during the first-run, when several months of data is to be retrieved for each thermostat, beginning with the in-service date.

Following the polling of the runtime information, data is retrieved for the point-in-time or snapshot data.  One record is written for each data-type retrieved for each thermostat; so, the number of records written for each data-type is determined by the frequency by which the application is run.  That is, if it is run hourly, one record will be retrieved per thermostat, per data-type, for each hour.  Or, one per day, per thermostat, per data-type if run daily.



#### Update 01-Jun-2021 (v03.20)

The v03.20 version includes the following changes:

1.  The Ecobee API was modified around 27-May-2021 to return additional fields for the thermostat runtime details.  These new fields are *actual_voc*, *actual_co2*, *actual_aq_accuracy*, and *actual_aq_score*.  In order to support these new fields, Sheriff Fanous updated the Pyecobee library and object definitions (to version v1.3.11).  The latest v03.20 release requires this new library version.

   ##### Migration steps to v03.20

   - Stop any existing scheduled tasks for previous releases (CRON / Task Scheduler).

   - To support the new fields mentioned above, the thermRuntime SQLite3 database table must be modified to include these new fields in the record.  Open the database in SQLite3 and issue the following commands to add the new columns:

     ```
     alter table thermRuntime add column actual_voc INTEGER;
     alter table thermRuntime add column actual_co2 INTEGER;
     alter table thermRuntime add column actual_aq_accuracy INTEGER;
     alter table thermRuntime add column actual_aq_score INTEGER;
     ```

   - To include the most current fixes to the Pyecobee Python library, the customized version provided in the zip archive needs to be installed to replace the current version.  To uninstall the prior Pyecobee Python library, use

     ```
     pip uninstall Pyecobee
     ```

   - Install the customized Pyecobee library from the .zip archive provided, using

     ```
     pip install ./Pyecobee-ECC.zip -v
     ```

     Restart the scheduled task.




#### Update 08-Dec-2020 (v03.10 / v03.11)

The v03.10 / v03.11 (and updates since v03.01) version includes the following changes:

1.  The Python library used to interface with the Ecobee API has been changed back to the original author's (Sheriff Fanous, @sfanous).  This is due to support issues with the fork that was previously utilized (@mumblepins).  As of this date, the *most* supported version seems to be from @sfanous, and he has committed to keep this up-to-date with Ecobee's API changes over time.  Still, the current release does not currently support on of the Ecobee API object (for thermostat reminders).  See details in the migration steps following.

2. Ecobee continues to make unannounced changes to the returns from their API.  This includes undocumented objects (such as thermostat reminders), badly-formed returns ("empty" or largely blank records sometimes returned for runtime data, with insufficient number of data fields), new return fields (fanSpeed added to thermostat settings object), etc.  Additionally, new selection parameters were added to the 'get thermostat details' API for the 'audio' and 'energy' objects (note that these objects are now **NOT** selected by default).  The code has been modified to support these issues.

3. Ecobee changed the approach to authorization as of 01-Dec-2020 to support JWT-formatted access tokens up to 7KB in length (vs. the earlier 32-byte format), and longer PIN-codes in the format "xxxx-xxxx" (vs. the earlier 4-byte format); see further details here:  [ecobee API authorization changes](https://www.ecobee.com/home/developer/api/documentation/v1/auth/developer-migration-summary.shtml).  The code supports these new formats, but in order to use the new, longer PINs and tokens, the application must be re-authorized in the Ecobee portal (see details on migration to the latest release following).

4. E-mail notification code has been added to send notification of critical failures of the application, with a new command line parameter to support Gmail credentials as noted following:

   - GMail user/password credentials file (**-m**, **--gmail_credentials_file_path=**{file path}) 

5. As a result of the new e-mail notification routines, new imports are required for the *smtplib* and *email.message*; the current list of included libraries required is as follows:  

   ```
   from datetime import datetime
   from datetime import timedelta
   import time
   import pytz
   import json
   import os
   import fnmatch
   import sys
   import argparse
   import smtplib
   from email.message import EmailMessage
   
   from pyecobee import *
   
   import sqlite3
   from sqlite3 import Error
   
   import urllib3
   import certifi
   import socket
   import dns.resolver
   from dns.exception import DNSException
   from pythonping import ping
   ```

6. A database archival routine was added to automatically archive the database once it reaches a specified size (currently set to approximately 1GB in the code).

7. Numerous changes have been made to enhance the error handling in the application, as well as code refactoring for efficiency.

   ##### Migration steps to v03.10 / v03.11

   - Stop any existing scheduled tasks for previous releases (CRON / Task Scheduler).

   - Edit the ECCMQTTIoT_GMail_Credentials.txt file to include the new parameters for sender local host name and destination e-mail addresses (comma separated, as noted in the *Quick Start* below).

   - Modify any other default parameters as noted above either in the Python script or preferably via command-line switches for the scheduled task.

   - To support the new 'fanSpeed' thermostat parameter, the thermSettings SQLite3 database table must be modified to include this new field in the record.  Open the database in SQLite3 and issue the following command to add the new column:

     ```
     alter table thermSettings add column fan_speed
     ```

   - To include the most current fixes to the Pyecobee Python library, the customized version provided in the zip archive needs to be installed to replace the current version (from @mumblepins).  To uninstall the prior Pyecobee Python library, use

     ```
     pip uninstall Pyecobee
     ```

   - Install the customized Pyecobee library from the .zip archive provided, using

     ```
     pip install ./Pyecobee-ECC.zip -v
     ```

   - Ensure any new libraries are installed as noted above.

   - To re-authorize the application to use the new PIN and access-token format, do the following:

     - Edit the authorization token JSON file ( *ECCEcobee_tkn.json* by default) and replace the access, refresh, and authorization tokens with "bogus values", such as "xxxx"
     - Run the Python script; this will fail due to an authorization error, but a new authorization PIN code will be issued in the new format("xxxx-xxxx").  Examine the log file to retrieve this PIN.
     - Access the ECC Ecobee portal and log in
     - Select "My Apps" from the menu at top right
     - Select "ECC Ecobee Python Data Archival" application
     - Select "Add Application" and follow prompts
     - At the prompt, specify the new 9-character PIN retrieved from the log file
     - Follow the prompts to authorize the application (this is now a series of confirmation screens)
     - Re-run the Python script; the application should now be authorized and a new set of access / refresh tokens will be issued

   - For the first execution following the upgrade, it is suggested that the application be run from the command line, as this will attempt to retrieve all missing historical runtime data which could take some time.  Otherwise, if run from the task scheduler, this could result in the next scheduled execution occurring before the prior one has finished.

   - Restart the scheduled task.



#### Update 07-Jan-2020 (v03.01)

The v03.01 version includes the following changes:
1.  The authorization tokens are now stored in a JSON file vs. the original method of using the Python shelve small-database format.
2.  Command-line parameters can now be specified to indicate the location of files used by the application:
   * log file (**-l**, **-log**, **--log_file_path=**{file path})
   * database file (**-d**, **-db**, **--database_file_path=**{file path})
   * authorization token file (**-a**, **-auth**, **--authorize_file_path=**{file path})
   * default API key file (**-api**, **--api_file_path=**{file path})
   * thermostat revision intervals (**-i**, **-int**, **--int_file_path=**{file path})
   
   If not specified, defaults will be provided for each.  Parsing of the command-line is handled with the Python module argparse, and includes brief help for each optional parameter.  In addition to the command-line parameters for file locations, **-h (or --help)** will display help, and **-v (or -ver, --version)** will display the current application version and date or release.
   
3.  Default file names no longer contain embedded spaces for better cross-platform support.  Some of the file names used in prior versions of the
   application were renamed for consistency (e.g, .json extensions for JSON-formatted files).  **Before updating to the current release, ensure that either command-line parameters are used for invocation to ensure the existing files are correctly identified, or rename the existing files to match the default names:**
   * ECCEcobee.log (log file)
   * ECCEcobee.db (SQLite3 DB)
   * ECCEcobee_tkn.json (JSON authorization token file)
   * ECCEcobee_API.txt (default API key file)
   * ECCEcobee_therm_interval.json (JSON thermostat revision intervals working file)
4.  In the event of repeated time-outs on the API calls, the prior release would attempt an HTTPS connection and run a series of PING tests to the site *google.com* as additional diagnostic information.  This has been enhanced to include the site *ecobee.com*, and an additional DNS resolution test is performed to verify name-resolution functionality.

**Note:  Due to the change in the storage format for the authorization tokens, upon upgrading to this release the existing authorization token files should be deleted, then the application run with the proper *new* file path specifications.  This initial iteration will prompt for the application to be re-authorized and log the authorization PIN to the log file.  At that time, an administrator will need to log onto the Ecobee portal and re-add the application along with the authorization PIN.**



#### Update 02-Jan-2020 (v02.09)

The v02.09 version of the application polls and records most, if not all, of the useful information from the thermostats.  While v01.00 recorded historical runtime information and basic thermostat settings, this version adds support for virtually all of the instantaneous (or snapshot) data provided by the Ecobee service.  This includes polling, deserialization, and recording over 40 SQLite3 databases.  See information below regarding data structure for further details.

This release also adds some additional error handling for common errors, such as timeouts on the Ecobee API calls.  (This would occasionally occur in the initial release due to the large amount of data requested during initial runs for the historical runtime information.  This is now detected and the application will automatically retry up to four times before failing with an appropriate message.)  Finally, some minor refactoring and code clean-up was done with this release.

This latest release also utilizes several other libraries not included in the initial release; among these are:
   * urllib3 - utilized for checking access to various sites in order to validate Internet access in the event of repeated timeout errors
   * certifi - default certificate store used for HTTPS access to sites above
   * socket - used to set socket connection timeout values to a value higher than the default
   * pythonping - used for pinging various sites to further validate Internet access in the event of repeated timeout errors



## Quick Start

In order to perform the initial setup for running the application:
1. Install the Pyecobee library from the included archive file:
   
   *New with v03.10*:
   
   ```
   pip install ./Pyecobee-ECC -v
   ```
   
   
   This will install the ECC customized version of the Pyecobee library from Sherif Fanous, the original author, with additions to support the 'thermostat reminders' (until such time that the pull-request is merged with his library to support these modifications).
   
      ~~'pip install ./Pyecobee-mumblepins.zip -v'~~
   ~~This installs the library into the local Python environment from the provided archive.  (Note:  for other than Windows platforms, it may be necessary to download the newest archive from here:  [Pyecobee - mumblepins](https://github.com/mumblepins/Pyecobee).~~
   ~~Alternatively, the Pyecobee library should be able to be installed directly from mumblepins repository as follows:~~
      ~~'pip install git+https://github.com/mumblepins/Pyecobee.git',~~
   ~~(though this has not been tested and verified yet.  There also may be an issue with incompatibilities with any future releases of the Pyecobee library without specifying the specific version used at the time of this release.)~~
   ~~Note that the Pyecobee library located in the PyPi package repository is NOT the correct version; it is the original release by Sherif Fanous, which does not appear to be maintained.~~
   
2. Ensure the additional library requirements are installed in the Python environment, using the command 'pip install <package-name>' as required.  The v03.10 release utilizes the following imports:  

```
from datetime import datetime
   from datetime import timedelta
   import pytz
   import json
   import os
   import fnmatch
   import sys
   import argparse

   from pyecobee import *

   import sqlite3
   from sqlite3 import Error

   import urllib3
   import certifi
   import socket
   import dns.resolver
   from dns.exception import DNSException
   from pythonping import ping
```


3. Edit the application to configure various settings (ECC Pycobee Data.py); all files will be created by the app if they do not exist, with the exception of the default API key file.  Alternately, all file paths can be specified on the command line at invocation using filename parameters (see v03.01/v03.10 release notes for more details).
   * log file path
   * logging level
   * database file location
   * authorization tokens file location
   * default API key file location (used for initial running of the app); this file must be created prior to the initial run after creating the API key from the ECC Ecobee portal
   * thermostat revision interval file location
   * *(new with v03.10)* GMail credentials file location

4. Schedule the application to run on a recurring basis.  Suggested scheduling is to run once each hour in order to collect snapshot data hourly.

## SQLite Data Structure
All data associated with the Ecobee thermostats is written to one database with multiple tables.  The application will determine if the database exists, and if not, will create it automatically.  This is also true for the tables within the database.  As described above, there are many different record types associated with the details of a thermostat, and tables are created for each record type.

The runtime historical data is keyed based on the combination of thermostat id, runtime date, and runtime time as reported from the thermostat.  As the data is reported and maintained by the service in local thermostat time, there likely will be gaps and / or overwrite situations that occur as a result of daylight savings time changes.  As of the initial version of this application, no allowances are made for this limitation, as it appears to be a restriction in the implementation by Ecobee.

All snapshot data tables are keyed based on a combination of thermostat id and record-written date/time in UTC.  Given the timestamp when the records are written, there should be no issues with gaps or duplicates as with the historical runtime data.

For further information regarding the details of the thermostat object definitions provided by the Ecobee service, see here: [Ecobee Thermostat Objects](https://www.ecobee.com/home/developer/api/documentation/v1/objects/api-object-definitions.shtml)

### Blank (empty) and duplicate records
The data returned from the Ecobee service for the historical runtime records sometimes contains only the time slot date/time stamp and thermostat identification -- all other data fields are set to '0'.  This seems to occur due to two conditions. The first is for situations where the thermostat was not connected to the network for a sufficiently-long timeframe, resulting in a loss of some of the 5-minute time slots.  The second situation occurs when the API request window includes the most recent data available from the service for the requested thermostat.  In this case, it is common for the last 8-10 records returned to include only partial or all-zero data.  Subsequent requests for the same window will then return valid or more complete data for the same time slots.

***Note as of 05-Dec-2020:***  *The API now returns improperly-formatted data for these "empty" time slots, with an insufficient number of parameters (32 returned instead of the documented 33).  The application has been modified to ignore these records.*

The application handles all-zero record returns by ignoring these and not writing them to the database.  These are counted and reported in the statistics for each run however.  (There may be some argument that these should be recorded, as they would indicate times when the thermostat was not connected; however, this can be inferred from the missing time slots in the database.)  On successive iterations of the application, if a duplicate key is detected for a given time slot and thermostat, the existing data in the database is compared against the latest data returned from the service.  The record with the most non-zero data will be recorded in the database.
### Deserialization of Data Structures
The data returned from the Ecobee service for the thermostat details is quite detailed, and provided in a JSON format.  Recording this in a useful fashion to SQLite databases required deserializing the data at multiple levels, as the structure includes lists with embedded lists, sometimes 4-5 levels deep.  The application breaks these embedded lists into linkable database tables, providing the ability to recombine these as necessary based on common keys between the tables.  All tables record the thermostat id, name, and date/time written (in UTC) as the first fields in the record, so child lists can be rejoined to the parent record via this key.  (The date/time written is recorded as the same value between parent and child records.)  Though this approach is perhaps different from the suggested common-practice methods of linking tables using the SQLite row-ID, it does provide some advantage for data analysis.  Since the child tables include the key thermostat identification information, it is not always necessary to relink the child record to the parent in order to retrieve this key information, and the child tables can be standalone and analyzed directly if necessary.

Note that the deserialization has been tested with the existing data selections and current Ecobee API, but will likely need to be modified if future API changes add subsequent levels of embedded lists (deeper than the current level).
### API-defined objects vs. non-defined
The Ecobee API utilized provides native Python object definitions for both root-level and embedded (complex) list objects.  However, the returned data also provides definitions for "simple" lists, those for which no pre-defined object is provided.  These usually consists of lists of 2-3 elements at max, though some are substantially larger (e.g., the Schedule list, which provides the program schedule information for each 30-minute interval throughout the day, for a total of 48 elements).  The application deserializes these lists as well and records them into separate SQLite tables; the field definitions are created by the application, not the API.  The end result is a more human-readable and more easily-usable record definition than would be otherwise provided if the data was simply recorded in raw format.
## Logging
The application makes use of the Python logging service to provide information regarding each run iteration.  The log-level may be set to various levels to indicate the desired level of detail to log; initially this is set to DEBUG, the highest level of detail.  This is recommended for the first month or so of running new versions to ensure any bugs are logged appropriately.  After that time period, the log level can be set lower (such as INFO) to limit the size of the log file.

Note that using DEBUG logging, the log file will grow to approximately 500K within one week of hourly runs, so it is imperative to rotate the logs periodically to avoid overly-large log files.

## Pyecobee Library
The application makes use of a library that wraps the Ecobee API's into a simple but powerful set of API calls that return native Python objects.  This library was originally written by Sherif Fanous [@sfanous](https://github.com/sfanous/Pyecobee);  it is well documented here along with all of the object definitions, and Python getter / setter functions.  ~~Unfortunately, it doesn't seem to be maintained any longer, which is a problem as new fields are added to the object definitions / Ecobee API calls.  There are a number of forks for this that DO seem to be maintained; the one I've chosen to use is by Daniel Sullivan (mumblepins), here:  [Pyecobee mumblepins](https://github.com/mumblepins/Pyecobee).  This library must first be installed into the local Python environment in order to use the ECC Ecobee application.~~

*(As of v03.10, 05-Dec-2020):  A modified version of @sfanous' library is now provided, which includes extensions to support the 'thermostat reminders'.  Note the installation instructions above, for installing from the provided archive file.  Once these modifications are merged into the main library by the author, this should no longer be necessary.*

## Ecobee API and Date / Time
The underlying Ecobee API expects some API requests to be in thermostat time (local time), while others expect it to be in UTC form.  The library methods used here that accept a datetime object as an argument expects the argument to be passed in thermostat time.  The datetime object passed must be a timezone aware object.  The method will then either use the passed in datetime object as is, or convert it to its UTC time equivalent depending on the requirements of the ecobee API request being executed.  This is another advantage (consistency at least!) in the use of the library
vs. the core Ecobee service routines.

## Authorization and Access to the Ecobee Service
The ecobee API is based on extensions to the OAuth 2.0 framework.  See here: [Authorization and Access](https://www.ecobee.com/home/developer/api/documentation/v1/auth/auth-intro.shtml) for details on how this is implemented.  The application makes the necessary calls to ensure updated access tokens are produced and / or refreshed as they expire.  If all else fails and these somehow become corrupted, detailed steps will be logged in order to re-authorize the application through the Ecobee portal.

*(Note as of v03.10, 05-Dec-2020):  See the release notes above regarding changes made by Ecobee to the authorization process for JWT access tokens and longer PINs.*

## Error handling
I have spent quite a bit of effort in identifying and handling the most common errors that can occur.  In most cases, if a severe error occurs, re-running the application at a later time should result in success without causing issues with data integrity, etc.

