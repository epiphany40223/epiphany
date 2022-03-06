#!/usr/bin/env python3
"""
    This routine will monitor tasks in the Windows task scheduler.  Specific tasks and actions for which to
    monitor are specified in a JSON-formatted file specified at runtime (or using the default tasks-to-monitor
    file path).  This file includes the name of the task, the state for which to monitor (currently, the last-run
    state or whether the task is actively running), and a restart flag to indicate whether a task that should
    run continuously should be restarted if failed.

    The routine will also alert on status failed via Slack using the specified Slack API token.

            Written by DK Fowler ... 15-Oct-2021        --- v01.00

    Modified to save the last task run-state, which is then used to compare before sending any Slack alerts;
    if the current state is the same as the last run-state, the alert is NOT sent.  This is to prevent redundant
    alerts in the event of repetitive failures (such as a task failure that results in the task not being able to
    be restarted).
            Modified by DK Fowler ... 01-Nov-2021       --- v01.10

    Modified for minor changes to support deployment.
            Modified by DK Fowler ... 20-Feb-2022       --- v01.20
"""

import os
import sys
import argparse
import pywintypes
import win32com.client
import win32api
import json

# Import the ECC Python modules

srcdir = os.path.abspath(os.path.dirname(sys.argv[0]))
moddir = os.path.abspath(os.path.join(srcdir, "..", "..", "..", "python"))
if not os.path.exists(moddir):
    print("ERROR: Could not find the ECC python modules directory.")
    exit(1)

sys.path.insert(0, moddir)

import ECC

# Define version
ecctasks_version = "01.20"
ecctasks_date = "20-Feb-2022"

TASK_ENUM_HIDDEN = 1
TASK_STATE = {
    0: 'Unknown',
    1: 'Disabled',
    2: 'Queued',
    3: 'Ready',
    4: 'Running'
}

# Parse the command line arguments for the filename locations, if present
parser = argparse.ArgumentParser(description='''Epiphany Catholic Church Windows Task Scheduler Monitor.
                                            This routine will monitor the state of specified Windows task
                                            scheduler tasks and alert via Slack messages if one of the specified
                                            tasks failed on last run or is not currently running (as defined).
                                            If a task specified as "always running" is failed, it will be restarted
                                            if specified in the definition file.''',
                                 epilog='''Filename parameters may be specified on the command line at invocation, 
                                        or default values will be used for each.''')
parser.add_argument("-l", "-log", "--log-file-path", dest="log_file_path", default="ECCwintasksmon.log",
                    help="log filename path")
parser.add_argument("-t", "-tasks", "--tasks-to-monitor-file", "--tasks-file-path", dest="tasks_file_path",
                    default="ECCtasks.json", help="tasks-to-monitor JSON filename path")
parser.add_argument("-s", "--slk", "--slk-creds-file-path", dest="slk_creds_file_path", default="slk_creds.json",
                    help="Slack API token filename path")
parser.add_argument("-r", "--lrs", "--last-run-state-file-path", dest="last_run_state_file_path",
                    default="ECCtasks_last_run_state.json", help="tasks last run-state filename path")
parser.add_argument("-v", "-ver", "--version", action="store_true",
                    help="display application version information")

args = parser.parse_args()

# If the app version is requested on the command line, print it then exit.
if args.version:
    print(F"ECC Windows task schedule monitor application, version {ecctasks_version}, {ecctasks_date}...")
    sys.exit(0)

logger = ECC.setup_logging(info=True, debug=False,
                           logfile=args.log_file_path,
                           rotate=True,
                           slack_token_filename=args.slk_creds_file_path)

# Location of the tasks-to-monitor JSON file
ECCTasks = args.tasks_file_path

# Location of the tasks last-run-state JSON file
ECCTasksLastState = args.last_run_state_file_path


def walk_tasks(top, topdown=True, onerror=None, include_hidden=True,
               serverName=None, user=None, domain=None, password=None):
    scheduler = win32com.client.Dispatch('Schedule.Service')
    scheduler.Connect(serverName, user, domain, password)
    if isinstance(top, bytes):
        if hasattr(os, 'fsdecode'):
            top = os.fsdecode(top)
        else:
            top = top.decode('mbcs')
    if u'/' in top:
        top = top.replace(u'/', u'\\')
    include_hidden = TASK_ENUM_HIDDEN if include_hidden else 0
    try:
        top = scheduler.GetFolder(top)
    except pywintypes.com_error as error:
        if onerror is not None:
            onerror(error)
            logger.error(f'...{win32api.FormatMessage(error.excepinfo[5])}')
        return
    for entry in _walk_tasks_internal(top, topdown, onerror, include_hidden):
        yield entry


def _walk_tasks_internal(top, topdown, onerror, flags):
    try:
        folders = list(top.GetFolders(0))
        tasks = list(top.GetTasks(flags))
    except pywintypes.com_error as error:
        if onerror is not None:
            onerror(error)
            logger.error(f'...{win32api.FormatMessage(error.excepinfo[5])}')
        return

    if not topdown:
        for d in folders:
            for entry in _walk_tasks_internal(d, topdown, onerror, flags):
                yield entry

    yield top, folders, tasks

    if topdown:
        for d in folders:
            for entry in _walk_tasks_internal(d, topdown, onerror, flags):
                yield entry


def add_text_block(blocks, message, position=None):
    block = {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": message,
        }
    }
    if position is None:
        blocks.append(block)
    else:
        blocks.insert(position, block)


def get_slack_creds():
    """
            This routine will read the Slack credentials file specified (in JSON format) and
            return a dictionary with the specified contents (API token and channel).
                    Written by DK Fowler ... 15-Oct-2021

    :return:        Dictionary containing the Slack credentials (API token and channel).
    """
    json_slk_creds_dict = {}
    try:
        with open(ECCSlkAPI, "r") as slk_creds:
            json_slk_creds_dict = json.load(slk_creds)
    # Handle [Errno 2] No such file or directory, JSON decoding error (syntax error in file)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error(F"Missing or invalid Slack credentials JSON file...")
        logger.error(F"...error:  {e}")
        print(F"Missing or invalid Slack credentials JSON file...")
        print(F"...error:  {e}")
        sys.exit(1)
    return json_slk_creds_dict


def get_tasks_to_monitor():
    """
            This routine will read the tasks-to-monitor JSON file and return a dictionary with
            its contents.  The file contains a JSON-formatted list of task-scheduler tasks to
            monitor, the state for which to check (either last-run results, or currently running),
            and a flag as to whether to auto-restart the task if it has failed.
                    Written by DK Fowler ... 15-Oct-2021
    :return:        List of dictionaries containing the tasks-to-monitor
    """

    # Attempt to open the tasks-to-monitor/state file and read contents
    try:
        with open(ECCTasks, "r") as tasks_to_monitor:
            json_tasks_list = json.load(tasks_to_monitor)
    # Handle [Errno 2] No such file or directory, JSON decoding error (syntax error in file)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error(F"Missing or invalid tasks-to-monitor JSON file...")
        logger.error(F"...error:  {e}")
    logger.debug(json_tasks_list)
    return json_tasks_list


def get_tasks_last_run_state():
    """
            This routine will read the tasks last-run-state file specified (in JSON format) and
            return a dictionary with the specified contents (task name and last-run-state).  If
            the file does not exist, and empty dictionary is returned.
                    Written by DK Fowler ... 01-Nov-2021

    :return:        List of dictionaries containing the task names and last-run-state.
    """
    json_tasks_run_state_list = []
    # Attempt to open the tasks last-run-state file and read contents
    try:
        with open(ECCTasksLastState, "r") as tasks_run_states:
            json_tasks_run_state_list = json.load(tasks_run_states)
    # Handle [Errno 2] No such file or directory, JSON decoding error (syntax error in file)
    except FileNotFoundError as e:
        logger.info(F"No existing tasks last-run-state JSON file found...")
        logger.info(F"...error:  {e}")
    except json.JSONDecodeError as e:
        logger.error(F"Invalid tasks last-run-state JSON file...aborting")
        sys.exit(1)

    return json_tasks_run_state_list


def save_tasks_last_run_state(tasks_states):
    """
            This routine will save the list of tasks' last-states (task name, state).
                    Written by DK Fowler ... 01-Nov-2021

    :param tasks_states:     List of dictionaries containing the task name and last-run-state
    :return:                True if successful, else False
    """

    try:
        with open(ECCTasksLastState, "w") as tasks_run_states:
            json.dump(tasks_states, tasks_run_states)
    # Handle [Errno 2] No such file or directory, JSON decoding error (syntax error in file)
    except json.JSONDecodeError as e:
        logger.error(F"Invalid format for saving tasks last-run-states...{e}")
        logger.error(F"...tasks run states contents:")
        logger.error(F"......{tasks_states}")
        return False
    except Exception as e:
        logger.error(F"Error occurred while saving tasks last-run-states...{e}")
        logger.error(F"...tasks run states contents:")
        logger.error(F"......{tasks_states}")
        return False

    return True


def main():
    logger.info(F"*** Initiating Epiphany Catholic Church Windows task monitor ***")
    logger.info(F"Version:  {ecctasks_version}    Version date:  {ecctasks_date}")
    json_task_list = get_tasks_to_monitor()  # get list of tasks and desired monitoring state
    json_last_run_state_list = get_tasks_last_run_state()  # get list of tasks last-run-state
    for task in json_task_list:
        logger.debug(f'Task: {task["task"]}')
    n = 0
    for folder, subfolders, tasks in walk_tasks('/'):
        n += len(tasks)
        tasks_last_run_state = []  # create a list (of dictionaries) to hold current task, run-state
        for task in tasks:
            settings = task.Definition.Settings
            for task_chk_index, task_to_check in enumerate(json_task_list):
                if task_to_check["task"] in task.Path:
                    slk_message = ""
                    logger.debug(f'*** Found the targeted task..."{task_to_check["task"]}"')
                    if task_to_check["status"] == 'last_run':
                        if task.LastTaskResult != 0:
                            logger.info(f'Task failed on last run!!!')
                            slk_message = f'Task [{task_to_check["task"]}] failed on last run!!!'
                            tasks_last_run_state.append({"task": task_to_check["task"],
                                                         "last_state": "failed"})
                            if task_to_check["run_flag"] == 'restart':
                                run_task_status = run_task(task)
                                if not run_task_status:
                                    slk_message = slk_message + \
                                                  f'\nError occurred attempting to restart task:  {task_to_check["task"]}'
                        else:
                            logger.info(f'*** Task completed successfully on last run at:  {task.LastRunTime}')
                            # slk_message = f'Task [{task_to_check["task"]}] completed successfully on last run at:' \
                            #               f'  {task.LastRunTime} '
                            tasks_last_run_state.append({"task": task_to_check["task"],
                                                         "last_state": "success"})
                    elif task_to_check["status"] == 'running':
                        if task.State != 4:
                            slk_message = f'Task [{task_to_check["task"]}] is not running!!!'
                            logger.info(slk_message)
                            if task_to_check["run_flag"] == 'restart':
                                run_task_status = run_task(task)
                                if not run_task_status:
                                    slk_message += \
                                        f'\nError occurred attempting to restart task:  {task_to_check["task"]}'
                            tasks_last_run_state.append({"task": task_to_check["task"],
                                                         "last_state": "not running"})
                        else:
                            logger.info(f'Task {task_to_check["task"]} is running...')
                            # logger.info(f'...sending Slack message...')
                            # slk_message = f'Task [{task_to_check["task"]}] is running...'
                            tasks_last_run_state.append({"task": task_to_check["task"],
                                                         "last_state": "running"})
                    else:
                        logger.error(f'Specified task status to check is invalid!')
                        slk_message = f'Invalid status to check specified for task [{task_to_check["task"]}]...'

                    if slk_message != "":
                        # Check the last run-status; if this matches the current state, don't send a Slack alert
                        send_slack = check_last_run_state(json_last_run_state_list, task_to_check, task)
                        if send_slack:
                            logger.info(f'...sending Slack message')
                            slk_status = send_to_slack(slk_message)
                            if not slk_status:
                                print(f'...error occurred while sending to Slack...')
                                logger.error(f'...error occurred while sending to Slack...')

                    save_tasks_last_run_state(tasks_last_run_state)

    logger.debug(f'Found {n} tasks.')


def check_last_run_state(last_run_state_list, task_to_check, task_detail):
    """
            This routine will check the task's (passed in task_to_check) last-run-state (passed in last_run_state_list),
            against the current task state.  If the status-check is "running", the last-run-state was not "running", and the
            current run-state is not "running", then the routine will return False.  If the status-check is "last_run",
            the last-run-state was "failed", and the current "last-run-status" was not "0" (success), then the routine will
            return False.  Otherwise, it will return True.

            A True return indicates the current task's status is not the same as the previous run (meaning an alert should be
            issued), and is used to filter out redundant Slack alerts.
                    Written by DK Fowler ... 01-Nov-2021

    :param last_run_state_list:     List of dictionaries containing tasks, last-run-result previously saved
    :param task_to_check:           Task name to check
    :param task_detail:             Current details of the matching running tasks (including state and last-run-status)
    :return:                        False, if current task state matches stored state from last run; else, True
    """

    # If there is no information in the last-run-state list, then we can assume we want to send the alert
    if len(last_run_state_list) == 0:
        return True

    if task_to_check["status"] == "running":
        for last_run_task in last_run_state_list:
            if (last_run_task["task"] == task_to_check["task"]) and \
                    (last_run_task["last_state"] == "not running") and \
                    (task_detail.State != 4):
                return False
    elif task_to_check["status"] == "last_run":
        for last_run_task in last_run_state_list:
            if (last_run_task["task"] == task_to_check["task"]) and \
                    (last_run_task["last_state"] == "failed") and \
                    (task_detail.LastTaskResult != 0):
                return False
    else:
        logger.error(f'Specified task status is invalid while checking last-run status, task: {task_to_check["task"]}, '
                     f'check-status: {task_to_check["status"]}.')

    return True


def send_to_slack(slk_message):
    blocks = list()
    add_text_block(blocks, slk_message)

    # Get Slack credentials
    slk_creds = get_slack_creds()
    # Create the Slack client object
    slack_client = slack_sdk.WebClient(token=slk_creds["token"])
    try:
        response = slack_client.chat_postMessage(channel=slk_creds["channel"],
                                                 blocks=blocks,
                                                 text=slk_message)
        return True
        # print(response)
    except SlackApiError as e:
        print(f"Error occurred posting to Slack, error: {e}")
        logger.error(f"Error occurred posting to Slack, error:  {e}")
        return False


def run_task(task):
    """
            This routine will attempt to start the task passed.  Note that enabling and starting
            a task requires the process to run in the context of the task owner or administrator.
                    Written by DK Fowler ... 16-Oct-2021
    :return:    True, if successful; else False
    """

    try:
        task.Enabled = True
        running_task = task.Run(task)
        logger.info(f'...restarted task')
        return True
    except pywintypes.com_error as error:
        logger.error(f'Error occurred while attempting to restart task...{error}')
        logger.error(f'...{win32api.FormatMessage(error.excepinfo[5])}')
        return False
    except Exception as e:
        logger.error(f'Error occurred while attempting to restart task...{e}')
        return False


if __name__ == '__main__':
    main()
