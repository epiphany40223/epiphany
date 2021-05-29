#!/usr/bin/env python3

"""

Script to download user counter printing data from Epiphany's Ricoh printer.

We are screen-scraping from the Ricoh web UI to download CSV data of cumulative
printing totals based on usernames/account numbers.  The Ricoh tracks this
data cumulatively since the beginning of time, so the numbers are always
increasing.

We use this script to download the most recent CSV data and save it to a
file.  Other Python code will then process that file.

"""

import os
import sys
import base64
import os.path
import argparse
import urllib.request
import http.cookiejar

from bs4 import BeautifulSoup

# We assume that there is a "ecc-python-modules" sym link in this
# directory that points to the directory with ECC.py and friends.
moddir = os.path.join(os.getcwd(), 'ecc-python-modules')
if not os.path.exists(moddir):
    print("ERROR: Could not find the ecc-python-modules directory.")
    print("ERROR: Please make a ecc-python-modules sym link and run again.")
    exit(1)

sys.path.insert(0, moddir)

import ECC

log = None

#-----------------------------------

# BeautifulSoup has different options depending on how it was bunbled /
# installed.  Try two different ways.
def get_soup(content):
    # Ubuntu 20
    try:
        return BeautifulSoup(content, features='html5lib')
    except:
        pass

    # Ubuntu 18
    try:
        return BeautifulSoup(content, features='html.parser')
    except:
        pass

    raise Exception("Unable to load BeautifulSoup")

#-----------------------------------

# The "wimToken" field value appears to be how the Ricoh validates HTTP POSTs
# that come from a previous HTTP GET page.
def find_wimToken(soup, page, log):
    key    = 'name'
    target = 'wimToken'
    inputs = soup.find_all('input')
    for input in inputs:
        # input is not a regular dictionary (it's a BeautifulSoup object), so we
        # cannot check "if key in input".  Instead, we just use a "try" block to
        # see if it works.
        try:
            if input[key] == target:
                return input['value']
        except:
            pass

    log.critical(f"ERROR: Did not find expected 'wimToken' field in {page} page -- aborting")
    exit(1)

#-----------------------------------

def add_cli_args():
    parser = argparse.ArgumentParser(description='Ricoh user counter CSV downloader')
    parser.add_argument('--ip',
                        required=True,
                        help='IP address for Ricoh printer')
    parser.add_argument('--user',
                        default='admin',
                        help='Username for Ricoh login')
    parser.add_argument('--password-filename',
                        required=True,
                        help='Filename containing the Ricoh login password')
    parser.add_argument('--csv',
                        required=True,
                        help='Output CSV file')

    parser.add_argument('--logfile',
                        default='ricoh-download-logfile',
                        help='Optional output logfile')

    parser.add_argument('--slack-token-filename',
                        required=True,
                        help='File containing the Slack bot authorization token')

    parser.add_argument('--verbose',
                        default=False,
                        action='store_true',
                        help='Enable verbose output')
    parser.add_argument('--debug',
                        default=False,
                        action='store_true',
                        help='Enable extra debugging')

    args = parser.parse_args()

    return args

#------------------------------------------------

def check_args(args, log):
    if not os.path.exists(args.password_filename):
        log.critical(f"Ricoh password downloader password filename does not exist ({args.password_filename})")
        exit(1)

    with open(args.password_filename) as fp:
        args.password = fp.read().strip()

#------------------------------------------------

# Make an opener associated with a cookie jar to hold web cookies
def get_opener(log):
    cj     = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

    return opener, cj

#------------------------------------------------

# Open original URL to get initial cookies.
# This sets the Ricoh cookieOnOffChecker=on cookie.
def get_initial_page(opener, args, log):
    log.info("Getting Ricoh initial page...")
    url = f'http://{args.ip}/web/guest/en/websys/webArch/mainFrame.cgi'

    request = opener.open(url)

    # We don't even need to read the request result; the cookie has been
    # set in the cookie jar already.

#------------------------------------------------

# Get the next 2 Ricoh cookies:
#
# risessiond=[some integer]
# wimsesid=--
#
# These come from authForm.cgi.
def login(opener, cookie_jar, args, log):
    # First, get the login page so that we can get the embedded wimToken value
    log.info("Getting Ricoh login page...")
    url     = f'http://{args.ip}/web/guest/en/websys/webArch/authForm.cgi'
    request = opener.open(url)
    content = request.read()
    soup    = get_soup(content)

    # Find the hidden "wimToken" field value; it is needed to POST to
    # the login page.
    wimToken = find_wimToken(soup, "login", log)

    # Now POST to the login.cgi form with the wimToken value.
    log.info("Logging in to Ricoh...")
    url    = f'http://{args.ip}/web/guest/en/websys/webArch/login.cgi'
    fields = {
        "wimToken"      : wimToken,
        "open"          : "",
        "userid_work"   : "",
        "password_work" : "",
        "userid"        : base64.b64encode(args.user.encode('utf-8')),
        "password"      : base64.b64encode(args.password.encode('utf-8')),
    }
    data    = urllib.parse.urlencode(fields).encode()
    request = opener.open(url, data=data)

    # We don't even have to read the content; the cookies have been set already.

    # If we successfully logged in, the risessionid cookie value will be an
    # integer.
    for cookie in cookie_jar:
        if cookie.name == 'risessionid':
            try:
                val = int(cookie.value)
                assert(val > 0)
                return
            except:
                pass

    raise Exception("Failed to login to the Ricoh (check the password?)")

#------------------------------------------------

def download_csv(opener, args, log):
    # First, get userCounter page so that we can get the wimToken value
    log.info("Getting userCounter...")
    url     = f'http://{args.ip}/web/entry/en/websys/status/getUserCounter.cgi'
    request = opener.open(url)
    content = request.read()
    soup    = get_soup(content)

    # Find the hidden "wimToken" field value.
    wimToken = find_wimToken(soup, "getUserCounter", log)

    # Now POST to get the user counter CSV Data with the wimToken value
    log.info("Downloading CSV data...")
    url    = f'http://{args.ip}/web/entry/en/websys/status/downloadUserCounter.cgi'
    fields = {
        "wimToken"            : wimToken,
        "accessConf"          : "",
        "offset"              : "0",
        "userCounterListPage" : "",
        "count"               : "9999",
    }
    data    = urllib.parse.urlencode(fields).encode()
    request = opener.open(url, data=data)
    content = request.read()

    with open(args.csv, "wb") as fp:
        fp.write(content)
    log.debug(f"Wrote {args.csv}")

#------------------------------------------------

# Log us out when done
def logout(opener, args, log):
    log.info("Logging out of the Ricoh...")
    url     = f'http://{args.ip}/web/guest/en/websys/webArch/logout.cgi'
    request = opener.open(url)

    # We don't even need to read the resulting request

#------------------------------------------------

def main():
    args = add_cli_args()
    global log
    log = ECC.setup_logging(info=args.verbose,
                            debug=args.debug,
                            logfile=args.logfile, rotate=True,
                            slack_token_filename=args.slack_token_filename)
    check_args(args, log)

    opener, cookie_jar = get_opener(log)
    get_initial_page(opener, args, log)
    login(opener, cookie_jar, args, log)
    download_csv(opener, args, log)
    logout(opener, args, log)

if __name__ == "__main__":
    main()
