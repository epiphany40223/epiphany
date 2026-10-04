# ECC Windows Task Monitor
## Overview
This application will monitor the Windows task scheduler for specific jobs' status, and optionally alert via a Slack channel on failure.  The tasks to monitor are specified via a JSON-formatted configuration file read at initialization along with the desired state of the task -- if the task is to be in an "always running" state, any other state will cause an alert to be generated.  If the task is a "run periodic" task, a failure-state on last-run will generate the alert.  Optionally, the configuration file can specify a restart attempt, which will then be attempted along with the generation of the alert.

The application logic maintains a state file for the Slack alert generation in order to minimize extraneous alerts.  A change in task state from the last run (if the run-state doesn't match that specified in the configuration) will result in the alert being regenerated.  Otherwise, the alert is suppressed to avoid duplicate alerts.

The motivation behind the application was a rather sporadic and unusual failure of the Windows task scheduler to restart certain applications that were scheduled to run either continuously or on a specified schedule upon failure.  No error condition was indicated for the failure of the task, nor of the task scheduler failure to restart the failed job.



Command-line parameters can be specified to indicate the location of files used by the application:

* log file (**-l**, **-log**, **--log_file_path=**{file path})
* tasks to monitor file (**-t**, **-tasks**, **--tasks-to=monitor-file=**{file path})
* Slack credentials file path (**-s**, **-slk**, **--slk-creds-file-path=**{file path})
* last run state file path (**-r**, **--lrs**, **--last-run-state-file-path=**{file path})
* If not specified, defaults will be provided for each.  Parsing of the command-line is handled with the Python module argparse, and includes brief help for each optional parameter.  In addition to the command-line parameters for file locations, **-h (or --help)** will display help, and **-v (or -ver, --version)** will display the current application version and date or release.

The application is written in Python3 and utilizes libraries as noted in the imports following:

```
import os
import sys
import argparse
import logging
import pywintypes
import win32com.client
import win32api
import json
import slack_sdk
from slack_sdk.errors import SlackApiError
```



## Quick Start

In order to perform the initial setup for running the application:
1. Install the Python script provided.
2. Ensure the additional library requirements are installed in the Python environment, using the command 'pip install <package-name>' as required.
3. Edit the application to configure various settings (wintasksmon.py); the log file will be created by the app if it doesn't exist.  Alternately, all file paths can be specified on the command line at invocation using filename parameters.
   * log file path
   * tasks to monitor configuration file
   * Slack credentials file (JSON-formatted, containing both the Slack API key and channel)
   * last-run state file path (will be created at first run)
4. Create the both the specified Slack credentials file and tasks-to-monitor file.  (Sample formats were provided with distribution of the app)
5. The application is designed to be run periodically, say every 15-30 minutes.




## Logging

The application makes use of the Python logging service to provide information regarding each run iteration.  The log-level may be set to various levels to indicate the desired level of detail to log; initially this is set to DEBUG, the highest level of detail.  The log level can be set lower (such as INFO) to limit the size of the log file.  Output to ***stderr*** at level ERROR or higher are also logged (as well as sent to the console if available).

