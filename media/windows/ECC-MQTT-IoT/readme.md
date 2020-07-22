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

  If not specified, defaults will be provided for each.  Parsing of the command-line is handled with the Python module argparse, and includes brief help for each optional parameter.  In addition to the command-line parameters for file locations, **-h (or --help)** will display help, and **-v (or -ver, --version)** will display the current application version and date or release.

The application is written in Python3 and utilizes libraries as noted in the imports following:

```
import paho.mqtt.client as mqtt

from datetime import datetime
import os
import sys
import argparse
import logging

import sqlite3
from sqlite3 import Error
```

The Paho MQTT client library is utilized for interfacing with the Mosquitto MQTT server running on an ECC server.



## Quick Start

In order to perform the initial setup for running the application:
1. Install the Python script provided.
2. Ensure the additional library requirements are installed in the Python environment, using the command 'pip install <package-name>' as required.
3. Edit the application to configure various settings (ECC_MQTT_IoT_SQLite.py); the log and SQLite3 database files will be created by the app if they do not exist.  Alternately, all file paths can be specified on the command line at invocation using filename parameters.
   * log file path
   * logging level
   * database file(s) location
   * MQTT credentials file (containing username/password authorization for connecting to MQTT)
   * MQTT broker IP address
4. Create the MQTT user credentials file.  This is a simple text file containing a record with the authorized client username and password, comma separated.  Note that these credentials must match the credentials file created during the Mosquitto broker installation / configuration.
5. The application is designed to be run continuously in the background.



## MQTT Authorization

Connections to the broker are authenticated using simple username and password.  The password is encrypted and stored in along with username(s) in the specified authorization file.  See the installation instructions for the Mosquitto MQTT broker for further information regarding the configuration for username / password authentication.



## Database Format

The SQLite3 database currently provides one table, which contains temperature and humidity data read from each sensor on a 10-minute frequency.  Each record contains the date/time written in UTC format, along with battery voltage and percent remaining (est.), access-point RSSI, and sensor ID.  The data contains a primary key based on the sensor ID and date/time written, and a secondary index on sensor ID.

The application monitors the size of the database after every 1000 records written, and will archive it once it reaches a specified size (approximately 1GB using 4K cluster size).  The archive file is renamed to include the original creation date / time and last-modified date / time so that the included timeframe can easily be identified.



## Logging

The application makes use of the Python logging service to provide information regarding each run iteration.  The log-level may be set to various levels to indicate the desired level of detail to log; initially this is set to DEBUG, the highest level of detail.  The log level can be set lower (such as INFO) to limit the size of the log file.

