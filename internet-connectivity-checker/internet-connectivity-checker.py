#!/usr/bin/env python3
#
# Quick / simple inetnet connectivity checker
#

import subprocess
import platform
import datetime
import time
import http.client
import urllib.parse

hostname = "google.com"
last_state = None
ping_cmd = list()
timestamp_format = "%m/%d/%Y %H:%M:%S"

# Hand-set values from the Google Form
form_server = "docs.google.com"
form_id = "1FAIpQLSeeflsGQMxGq_tlbvx69D5jNmB5Pa0ZvHGWwy-Vo4h3N0DQzA"
form_path = "/forms/d/e/{0}/formResponse".format(form_id)
form_fields = {
    "start_str" : "entry.1460998506",
    "start_timestamp" : "entry.1014226006",
    "end_str" : "entry.2108161570",
    "end_timestamp" : "entry.342404331"
    }

def setup_ping_cmd():
    # The Windows "ping" command uses the "-n" CLI parameter; Linux
    # and OS X use "-c".
    ping_cmd.append("ping")
    if "windows" in platform.system().lower():
        ping_cmd.append("-n")
    else:
        ping_cmd.append("-c")
    ping_cmd.append("1")
    ping_cmd.append(hostname)

#
# Return True if we succeed in submitting the form.
# Return False otherwise.
#
def submit_google_form(outage_start, outage_end):
    try:
        conn = http.client.HTTPSConnection(form_server, timeout=15)
    except:
        return False

    headers = { "Content-type" : "application/x-www-form-urlencoded",
                "Accept" : "text/plain" }

    start_str = outage_start.strftime(timestamp_format)
    start_ts  = outage_start.timestamp()
    end_str   = outage_end.strftime(timestamp_format)
    end_ts    = outage_end.timestamp()
    values = {
        form_fields["start_str"]       : start_str,
        form_fields["start_timestamp"] : start_ts,
        form_fields["end_str"]         : end_str,
        form_fields["end_timestamp"]   : end_ts
        }
    body = urllib.parse.urlencode(values)

    try:
        conn.request(method="POST",
                     url=form_path,
                     body=body,
                     headers=headers)
        response = conn.getresponse()
        if response and response.status == 200:
            return True

        return False
    except:
        return False

def do_ping():
    print("*** Running ping to {0} at {1}"
          .format(hostname, datetime.datetime.now().strftime(timestamp_format)))
    ret = subprocess.run(ping_cmd, timeout=15)
    return ret.returncode == 0

def main():
    setup_ping_cmd()

    # Do the ping once to establish a baseline
    last_state = do_ping()
    outage_start = None

    # Steady state loop
    print("*** Continually checking for internet connectivity...")
    while True:
        current_state = do_ping()

        if current_state != last_state:

            # If we *were* online and now we're not, this is the
            # beginning of an outage.
            if last_state:
                outage_start = datetime.datetime.now()
                outage_start_str = outage_start.strftime(timestamp_format)
                print("--- Outage start: {0}".format(outage_start_str))

            # Otherwise, we were *offline, and now we're *online*.  So
            # submit the outage duration to the Google Form.
            else:
                outage_stop = datetime.datetime.now()
                success = submit_google_form(outage_start, outage_stop)
                if not success:
                    # If we were not able to submit, then we're still offline!
                    continue

                outage_stop_str = outage_start.strftime(timestamp_format)
                print("+++ Outage stop:  {0}".format(outage_stop_str))

            last_state = current_state

        # Sleep until the next minute.  Calculate how much time it is
        # until the next "0" seconds (because the above submission may
        # have taken a few seconds).
        d = datetime.datetime.now()
        secs = d.second
        time.sleep(60 - secs)

main()
