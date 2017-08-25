#!/usr/bin/env python3
#
# Quick / simple inetnet connectivity checker
#

import subprocess
import datetime
import time
import http.client
import urllib.parse

last_state = None
external_url = "https://status.github.com/api/status.json"
timestamp_format = "%m/%d/%Y %H:%M:%S"

# Hand-set values from the Google Form
form_id = "1FAIpQLSeeflsGQMxGq_tlbvx69D5jNmB5Pa0ZvHGWwy-Vo4h3N0DQzA"
form_path = "/forms/d/e/{0}/formResponse".format(form_id)
form_fields = {
    "start_str" : "entry.1460998506",
    "start_timestamp" : "entry.1014226006",
    "end_str" : "entry.2108161570",
    "end_timestamp" : "entry.342404331"
    }

#
# Return True if we succeed in submitting the form.
# Return False otherwise.
#
def submit_google_form(outage_start, outage_end):
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
        conn = http.client.HTTPSConnection("docs.google.com", timeout=15)
        conn.request(method="POST",
                     url=form_path,
                     body=body,
                     headers=headers)
        response = conn.getresponse()
        if response and response.status == 200:
            return True
    except:
        # If we get an exception, just fall through so that all errors
        # exit a common way.
        pass

    return False

def check_connectivity():
    print("*** Checking connectivity to {0} at {1}"
          .format(external_url, datetime.datetime.now().strftime(timestamp_format)))

    o = urllib.parse.urlparse(external_url)

    try:
        conn = http.client.HTTPSConnection(o.hostname, timeout=15)
        conn.request(method="GET",
                     url=o.path)
        response = conn.getresponse()
        if response and response.status == 200:
            return True
    except:
        # If we get an exception, just fall through so that all errors
        # exit a common way.
        pass

    return False

def main():
    # Do the ping once to establish a baseline
    last_state = check_connectivity()
    outage_start = None

    # Steady state loop
    print("*** Continually checking for internet connectivity...")
    while True:
        current_state = check_connectivity()

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
