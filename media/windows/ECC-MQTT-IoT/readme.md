# ECC MQTT IoT Listener
## Epiphany Catholic Church - Mosquitto Message Queuing  Telemetry Transport (MQTT) Internet-of-Things (IoT) Listener

## Overview
This application listens for incoming messages on a specified MQTT channel, parses the incoming data, and writes it to a SQLite3 database.  It is designed to run continuously in the background, initially listening to incoming messages published from IoT temperature and humidity sensors in the ECC environment.

MQTT is a messaging architecture, which uses a "publish and subscribe" model.  Data sources are referenced as "channels"; in this application, various wireless sensors subscribe to a specific channel and periodically publish data read from the sensor.  This listener application subscribes to the same channel to retrieve and handle these incoming messages.  The architecture allows for a "many-to-one" implementation, such that multiple sensors can easily publish data to the same database.  

Though MQTT provides various quality-of-service (QoS) levels to ensure message delivery, the current implementation only supports QoS of "0", which does *not* provide this level of guaranteed delivery (such as if the listener were down when a message is published).  Since data is being published every 10 minutes from the current sensors, some missing data is not deemed to be critical.

Command-line parameters can be specified to indicate the location of files used by the application:

* log file (**-l**, **-log**, **--log_file_path=**{file path})
* database file path (**-d**, **-db**, **--database_file_path=**{file path})
* MQTT credentials file path (**-c**, **--credentials_file_path=**{file path})
* MQTT broker IP address (**-b**, **--mqtt_broker=**{IP address})
* connectivity timer check (*new with v02.00*) (**-t, --timer_check=**{time in minutes})
* GMail notification credentials file path (*new with v02.00*) (**-m, --gmail_credentials_file_path=**{file path})
* last notification file path (*new with v02.00*) (**-n, --last_notice_file_path=**{file path})
* last notification silence time (*new with v02.00*) (**-s, --last_notice_silence_time=**{time in minutes})

* maximum number of log archive files to keep (*new with v02.10*) (**-a, --max_log_archives=**{count})
* maximum log size, in bytes, prior to archival (*new with v02.10*) (**-z, --archive_log_size=**{size in bytes})

If not specified, defaults will be provided for each.  Parsing of the command-line is handled with the Python module argparse, and includes brief help for each optional parameter.  In addition to the command-line parameters for file locations, **-h (or --help)** will display help, and **-v (or -ver, --version)** will display the current application version and date or release.

The application is written in Python3 and utilizes libraries as noted in the imports following (*including several new libraries required for v02.00* */ v02.10*):

```
import paho.mqtt.client as mqtt

from datetime import datetime
import time
from threading import Timer
import smtplib
from email.message import EmailMessage
import pickle
import os
import atexit
import sys
import argparse

import glob
from concurrent import futures

import gzip
import logging.handlers

import sqlite3
from sqlite3 import Error
```

The Paho MQTT client library is utilized for interfacing with the Mosquitto MQTT server running on an ECC server, and must be installed prior to running the listener application.



## Quick Start

In order to perform the initial setup for running the application:
1. Install the Python script provided.
2. Ensure the additional library requirements (***such as the Paho MQTT client library***) are installed in the Python environment, using the command 'pip install <package-name>' as required.
3. Edit the application to configure various settings (ECC_MQTT_IoT_SQLite.py); the log and SQLite3 database files will be created by the app if they do not exist.  Alternately, all file paths can be specified on the command line at invocation using filename parameters.
   * log file path
   * logging level
   * database file(s) location
   * MQTT credentials file (containing username/password authorization for connecting to MQTT)
   * MQTT broker IP address
   * (*new with v02.00*) connectivity timer check, in minutes.  This is the frequency at which the listener will check if an MQTT message has been received, and if not, will restart the listener.
   * (*new with v02.00*) GMail notification credentials file path.  These are the credentials of the GMail account used to send notifications.
   * (*new with v02.00*) last notification file path.  This file is used to store the date/time of the last successful notification sent, and used to determine whether a future notification should be sent during the specified "mute" or silence period.
   * (*new with v02.00*) last notification silence time, in minutes.  This is the silence period, use to mute multiple notifications during the time period specified.
   * *(new with v02.10*) maximum number of log archive files to keep.  This value will default to 9 unless otherwise specified.
   * (*new with v02.10*) maximum log size, in bytes, prior to archival.  Once the log file reaches this size, it will be automatically rotated and GZIP'd.  This value will default to approximately 1GB unless otherwise specified.
4. Create the MQTT user credentials file.  This is a simple text file containing a record with the authorized client username and password, comma separated.  Note that these credentials must match the credentials file created during the Mosquitto broker installation / configuration.
5. Create the GMail notification credentials file (*new with v02.00*).  This is a simple text file containing a record with the authorized GMail origination address and password, comma separated.  These are the credentials the application uses in order to send notifications, such as when the listener is restarted when no MQTT messages are received within the specified timeframe.
   - **Note:**  (*new with v02.10*)  The GMail credentials file now also contains two additional parameters following the origination address and password; additionally, the sender local host name and destination e-mail address are included in the same record, comma separated.
6. The application is designed to be run continuously in the background.



## V02.00 Release Notes (August, 2020)

Several enhancements and bug fixes were made for the v02.00 release, as noted:

1.  Changes were made to help ensure the listener remains connected to the MQTT broker as a result of network outages.  Previously, though connections to the broker were automatically reestablished following a network interruption, a subscription to the channel may not have reoccurred without stopping and restarting the listener.  The call to subscribe to the channel was moved to the connection routine such that when an auto-reconnection occurs, the channel is also re-subscribed.

2. A timer was added to check whether MQTT messages have been received during the specified timeframe, and if not, the listener is automatically restarted.  This timer is set to 20 minutes as a default (2 sensor publication timeframes).  This is another safeguard in case the auto-reconnection to the broker is not successful, or if a network interruption is not detected automatically.

3. Should an restart of the listener be initiated as described above, the listener will attempt to send a GMail notification to the specified account.  In order to prevent spamming of repeat notifications should multiple restarts of the listener continue over an extended time period, a "mute" period can be specified (set to one day by default), such that no additional notifications will be sent following the first during the specified mute / silence timeframe.

4. A bug was corrected that would cause the startup of the listener to fail if the database did not exist.  This was due to the check for rotating / archiving the database when it reaches a specified size.  This check will now simply return if the file does not exist, allowing the database to be created on the first connection attempt.




## V02.10 Release Notes (November, 2020)

Several additional enhancements were included in the v02.10 release, among these:

1. Code was added to automatically rotate the log file based on a specified maximum size, in bytes.  Once this limit is hit, the built-in Python rotating log handler is called to first rotate the log, then the old log file is GZIP'd.  This is handled by starting a new separate thread to handle the compression, since this can take some time for very large files.  This helps to avoid interfering with the primary purpose of the script to handle incoming MQTT messages.  The number of already-compressed archive files is also check to ensure only a maximum number of archives are maintained as specified.  If the maximum number has been reached, the oldest file is deleted and the remaining archive files are renamed so that the oldest archived log always has a ".1" extension, and the newest has an extension of the maximum number of archived logs maintained.  Once a successful GZIP has occurred, the latest, uncompressed rotated log file is deleted.

2. Minor modifications were made to the mail credentials file to include the sender local host name (if specified, or None), and the destination e-mail address for alerts.  This allows a more generic usage of the e-mail routines for other applications / domains / users.

   #### Migration steps to v02.10:

   - Stop any existing scheduled tasks for prior versions.

   - Edit the ECCMQTTIoT_GMail_Credentials.txt file to include the new parameters for sender local host name and destination e-mail addresses.

   - Modify any other default parameters as noted above either in the Python script or preferably via command-line switches for the scheduled task.

   - Restart the scheduled task.

     

## MQTT Authorization

Connections to the broker are authenticated using simple username and password.  The password is encrypted and stored in along with username(s) in the specified authorization file.  See the installation instructions for the Mosquitto MQTT broker for further information regarding the configuration for username / password authentication.



## Database Format

The SQLite3 database currently provides one table, which contains temperature and humidity data read from each sensor on a 10-minute frequency.  Each record contains the date/time written in UTC format, along with battery voltage and percent remaining (est.), access-point RSSI, and sensor ID.  The data contains a primary key based on the sensor ID and date/time written, and a secondary index on sensor ID.

The application monitors the size of the database after every 1000 records written, and will archive it once it reaches a specified size (approximately 1GB using 4K cluster size).  The archive file is renamed to include the original creation date / time and last-modified date / time so that the included timeframe can easily be identified.



## Logging

The application makes use of the Python logging service to provide information regarding each run iteration.  The log-level may be set to various levels to indicate the desired level of detail to log; initially this is set to DEBUG, the highest level of detail.  The log level can be set lower (such as INFO) to limit the size of the log file.

