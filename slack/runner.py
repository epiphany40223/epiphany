#!/usr/bin/env python3
#
# Script used to run other Python automation.  Its main purposes in
# life are:
#
# 1. Use subprocess to launch a child process, capture its
#    stdout/stderr, and if the child process returns with any kind of
#    error, emit that error to a Slack channel for humans to review.
#
# 2. If requested, also emit to a Slack channel when a child process
#    runs successfully.

import os
import sys
import tempfile
import argparse
import subprocess

import slack_sdk

# Find the path to the ECC module (by finding the root of the git
# tree).  This is robust, but it's a little clunky. :-\
try:
    out = subprocess.run(['git', 'rev-parse', '--show-toplevel'],
                         capture_output=True)
    dirname = out.stdout.decode('utf-8').strip()
    if not dirname:
        raise Exception("Could not find git root.  Are you outside the git tree?")
    moddir  = os.path.join(dirname, 'python')
    sys.path.insert(0, moddir)
    import ECC
except Exception as e:
    sys.stderr.write("=== ERROR: Could not find common ECC Python module directory\n")
    sys.stderr.write(f"{e}\n")
    exit(1)

#==========================================================================

# Defaults for CLI options
default_timeout = 10 * 60
default_channel = '#bot-errors'

#==========================================================================

def runner(args, log):
    def _add_text_block(blocks, message, position=None):
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

    #--------------------------------------------------------------------

    # Creates a temporary text file and writes content to it.
    # The file must manually be removed later!
    def _add_file(files, type, content_blob):
        content  = content_blob.decode("utf-8").strip()
        fp       = tempfile.NamedTemporaryFile(mode="w", delete=False)
        filename = fp.name
        fp.write(content)
        fp.close()

        file = {
            "title"    : type,
            "filename" : filename,
        }
        files.append(file)

    #--------------------------------------------------------------------

    result = None
    blocks = list()
    files  = list()
    try:
        log.info(f"Executing: {args.prog}")
        # Specifically choose to use "check=False" here, because if
        # subprocess.run() detects an error in the return status and throws an
        # exception, then we don't get "result" filled -- i.e., we don't get any
        # of the stdout/stderr.  We're still using a timeout value (and we won't
        # get result/stdout/stderr) because timeouts are a much lower
        # probability of occurring, and the stdout/stderr we need will still be
        # in the logs stored locally (even if we don't have them here to send to
        # slack).  This is a compromise/balance between keeping runner.py simple
        # (i.e., vs implementing a timeout with Popen()/communicate() ourselves)
        # and the likelihood of a timeout actually occurring.
        result = subprocess.run(args.prog,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                timeout=args.child_timeout,
                                check=False)
        log.debug(result)
        log.info(f"Successfully executed: {args.prog}")

    except subprocess.TimeoutExpired as e:
        # The exception string will include the command args and the fact that
        # it timed out after X seconds. We will not have a "result", so no
        # stdout/stderr.  :-(
        log.info(f"Execution timed out after {args.child_timeout} seconds")
        _add_text_block(blocks, f"{e}\nSee logs on the machine where the app ran for stdout/stderr")
    except Exception as e:
        log.info(f"Execution failed: {e}")
        _add_text_block(blocks, f"Running command \"{args.prog}\" experienced an unknown error: {e}")
    else:
        if result.stdout:
            print(result.stdout.decode('utf-8').strip())
        if result.stderr:
            print(result.stderr.decode('utf-8').strip())
        if result and result.returncode != 0:
            log.info(f"Execution returned {result.returncode} exit status")
            _add_text_block(blocks, f"Running command \"{args.prog}\" returned exit status {result.returncode}")

    #--------------------------------------------------------------------

    # If we succeeded but still want to log, then add a Slack header block
    if len(blocks) == 0 and args.log_success:
        type    = 'success'
        _add_text_block(blocks, f"Ran command `{args.prog}` successfully")
    else:
        # If we failed, there will already be at least one Slack block
        type    = 'failure'

    #--------------------------------------------------------------------

    # If there are no Slack blocks, we're done
    if len(blocks) == 0:
        return

    # If we get here, there's stuff to send to Slack.
    # If a comment was specified on the CLI, then insert it at the beginning
    # of the blocks.
    if args.comment:
        _add_text_block(blocks, args.comment, 0)

    # Add the stdout/stderr, if they exist.
    if result:
        if result.stdout:
            _add_file(files, "stdout", result.stdout)
        if result.stderr:
            _add_file(files, "stderr", result.stderr)

    # Send the blocks to Slack
    with open(args.slack_token_filename) as fp:
        token = fp.read().strip()
    slack_client = slack_sdk.WebClient(token=token)
    response = slack_client.chat_postMessage(channel=args.slack_channel,
                                            blocks=blocks)
    log.info(f"Sent {type} notification message blocks to Slack")
    log.debug(blocks)

    # Sadly, blocks can't include files.  So upload those separately (and
    # remove the corresponding local temporary files).
    for file in files:
        response = slack_client.files_upload(channels=args.slack_channel,
                                            title=file['title'],
                                            file=file['filename'])
        os.unlink(file['filename'])
        log.info(f"Sent {file['title']} file to Slack")

#==========================================================================

def setup_cli():
    parser = argparse.ArgumentParser(description='Python Runner Wrapper')

    parser.add_argument('--verbose',
                        action='store_true',
                        default=False,
                        help='Enable runner.py regular verbose logging')
    parser.add_argument('--debug',
                        action='store_true',
                        default=False,
                        help='Enable additional logging of the runner itself')
    parser.add_argument('--logfile',
                        help='Name of logfile for runner itself')

    parser.add_argument('--slack-token-filename',
                        required=True,
                        help='File containing the Slack bot authorization token')
    parser.add_argument('--slack-channel',
                        default=default_channel,
                        help='Slack channel to send messages')

    parser.add_argument('--child-timeout',
                        default=default_timeout,
                        type=int,
                        help='Timeout (in seconds) for a child complete execution')
    parser.add_argument('--comment',
                        help='Optional contextual comment added to the Slack message')
    parser.add_argument('--log-success',
                        action='store_true',
                        help='Also log if the program runs successfully')

    # There must be at least one token in the "prog" arg
    parser.add_argument('prog',
                        nargs='+',
                        help='The program to run')

    args = parser.parse_args()

    # Sanity check
    if not os.path.exists(args.slack_token_filename):
        print("ERROR: Slack token file does not exist")
        exit(1)

    return args

#==========================================================================

def main():
    # We use regular file logging, too, just for additional backup
    # logging.
    args = setup_cli()
    log = ECC.setup_logging(info=args.verbose,
                            debug=args.debug,
                            logfile=args.logfile, rotate=True,
                            slack_token_filename=args.slack_token_filename)

    runner(args, log)

#==========================================================================

if __name__ == "__main__":
    main()
