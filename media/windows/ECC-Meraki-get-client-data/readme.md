# ECC Meraki Get Network Client Data
## Epiphany Catholic Church - Get Meraki Network Client Data

## Overview
This application polls the Cisco Meraki network cloud management infrastructure to obtain network client data for the Epiphany Catholic Church environment.  Data retrieved is written to a SQLite3 database in order to provide a historical archive of the data for trending and analysis.  The information includes details of all clients that are are connected via a wired connection, as well as wireless clients, both connected and those for which probe requests are detected.

The application is designed to scheduled to run on a regular basis, usually several times an hour (e.g., every 15 minutes).  When run, it will retrieve the last date/time that information was written to the database and request only new data from the Meraki Dashboard API since that time.

Command-line parameters can be specified to indicate the location of files used by the application:

* log file (**-l**, **-log**, **--log_file_path=**{file path})

* database file path (**-d**, **-db**, **--database_file_path=**{file path})

* Meraki API key filename path (**-api**, **--api_file_path=**{file path})

* Slack credentials filename path (**-s**, **--slk**, **--slk-creds-file-path=**{file path})

  If not specified, defaults will be provided for each.  Parsing of the command-line is handled with the Python module *argparse*, and includes brief help for each optional parameter.  In addition to the command-line parameters for file locations, **-h (or --help)** will display help, and **-v (or -ver, --version)** will display the current application version and date or release.

The application is written in Python3 and utilizes libraries as noted in the imports following:

```
from datetime import datetime
import os
import sys
import argparse
import logging
import psutil
import json
import slack_sdk
from slack_sdk.errors import SlackApiError

import sqlite3
from sqlite3 import Error

import socket

import meraki
```



## Quick Start

In order to perform the initial setup for running the application:
1. Install the Python script provided.
2. Ensure the additional library requirements are installed in the Python environment, using the command 'pip install <package-name>' as required.
3. Edit the application to configure various settings (ECC-Meraki-get-client-data.py); the log and SQLite3 database files will be created by the app if they do not exist.  Alternately, all file paths can be specified on the command line at invocation using filename parameters.
   * log file path
   * logging level
   * database file(s) location
   * Meraki API key filename location
   * Slack credentials (API key and channel) filename location 
4. Copy the Meraki Dashboard API key file into the specified location, or manually create/edit this.  The key file is a simple text file containing the 40-character API key.
5. Copy the Slack credentials file into the specified location, or manually create/edit this.  This credentials file is JSON-formatted with keys for the API key and channel for sending alerts.
6. The application is designed to be scheduled to run on a regular basis (at least once / hour recommended, every 15 minutes for better visibility).




### V03.80 Release Notes (December 18, 2021)

Added routine(s) to send Slack message on failures.

### V03.70 Release Notes (September 8, 2021)

Added routine to remap the returned fields: values from the Meraki getNetworkClients API to match the proper database order.

### V03.60 Release Notes (September 5, 2021)

Corrected bug that occurred during archival / recreation of database.  Previously, the table structure was recreated using the existing structure retrieved via the API.  Unfortunately, this does not match the "historical" table structure, which had evolved over the course of many API changes through the years.  Instead, changed logic to use the "expected" column names as defined, which matches the existing table structure.  (Note the column names are the same, these are just in a different order.)

### V03.50 Release Notes (June 27, 2021)

More changes made to the return from the Meraki API call...new field added:  deviceTypePrediction.  Also added additional error checking to catch and handle an error that occurs when the Meraki getNetworkClients API return is modified to add additional fields in the future.  Finally, updated the Dashboard API library to the latest release, v1.10.

### V03.40 Release Notes (April 28, 2021)

Modified to handle yet another additional change made to the return from the Meraki API call...new field added: recentDeviceConnection.

### V03.30 Release Notes (April 26, 2021)

Added new field now returned from the API (adaptivePolicyGroup) to the database schema.

### V03.20 Release Notes (December 16, 2020)

Added additional error checking prior to getting a connection to the database.

### V03.10 Release Notes (December 4, 2020)

Added additional error handling / messages for failures that occur during Meraki Dashboard API calls.

### V03.02 Release Notes (November, 2020)

With v03.02 of the application, the Meraki Dashboard API was upgraded to the latest release (v1.0).  With this release of the API, in addition to changes to the base URI, several structural changes were made to the function calls, including *getOrganizationNetworks* and *getNetworkClients*.  

Also, a database archival routine was added such that its size is checked upon execution and if it exceeds a specified threshold (approximately 1GB), the database is archived and a new version will be created at the next iteration.

Finally, some additional error checking / handling was added to handle a fringe case where a collision on client-ID and record written datetime rarely occurred (this is the primary key for the database).  Now if this occurs, an attempt will be made to regenerate datetime written prior to INSERTing the record.  In the event of a failure on INSERT, database ROLLBACKs were added to ensure the current transaction was terminated appropriately.



## Meraki Dashboard Authorization

All requests made to the Cisco Meraki Dashboard API must first be initialized utilizing an API key defined in the Meraki Dashboard.  The application stores this key in an external file which is read by the application at runtime from the specified location.



## Polling Details

When the application is run at the scheduled interval, it will first initialize the Meraki Dashboard API by reading and providing the API key from the specified key file.  Next, it will request a list of organization IDs associated with the ECC network.  It will then iterate through this list and request a list of all network IDs for this organization.  This list is filtered to exclude all product types except for *switches* or *wireless*.  Following this, it will retrieve the last-written date/time (in UTC) from the database if records exist.  It will then iterate through all of the returned network IDs and request all client information beginning from the last-written date/time to the current time.

Meraki only allows retrieving the last 31 days maximum of client data, so if the database does not currently exist, the polling timeframe will be set to this maximum.

Finally, the returned client data is parsed, pre-pended with date/time written, network name and ID, the client usage data is broken into separate fields for sent/received bytes, and the record is written to the database.  A count of the number of records written is maintained and summarized at the completion of the run.



## Slack Alerts (New with V03.80)

Alerts are generated to the default ECC Slack notifications channel on fatal errors that occur during polling.  (Note that sporadic failures do occur, likely due to occasional downtime with the Meraki API service or other rare network issues.)

## Database Format

The SQLite3 database currently contains one table, with network client data for each poll request.  Each record contains the date/time written in UTC format, along with network identification (name, ID), client identification (IP, MAC address, description, client ID, user, device manufacturer, OS), access point / switch identification (MAC, SSID, name, VLAN), client details for the specified poll timeframe (sent/received bytes, status (online/offline), 802.1x group policy), among others.  The data contains a primary key based on the client ID and date/time written, and a secondary index on client ID.

The application will create both the database and client table if these do not exist.

The application monitors the size of the database, and will archive it once it reaches a specified size (approximately 1GB using 4K cluster size).  The archive file is renamed to include the original creation date / time and last-modified date / time so that the included timeframe can easily be identified.



## Logging

The application makes use of the Python logging service to provide information regarding each run iteration.  The log-level may be set to various levels to indicate the desired level of detail to log; initially this is set to DEBUG, the highest level of detail.  The log level can be set lower (such as INFO) to limit the size of the log file.

