#!/usr/bin/env python3

#
# pip3 install xmltodict
# pip3 install pytz
# pip3 install dnspython
#
# The DMARC XML schema (https://tools.ietf.org/html/rfc7489) is simple
# enough that xmltodict can easily handle it.
#

import os
import re
import csv
import pytz
import datetime
import argparse
import xmltodict

from dns import resolver
from dns import reversename

from pprint import pprint

######################################

# My local timezone name.
local_tz_name = 'America/Louisville'
local_tz      = pytz.timezone(local_tz_name)

######################################

parser = argparse.ArgumentParser(description='Process XML DMARC reports')

parser.add_argument('--file',
                    required=True,
                    nargs='+',
                    action='append',
                    help='Filename of an XML DMARC report to process')

args = parser.parse_args()

######################################

# Sanity check that the files are there

for list_item in args.file:
    for filename in list_item:
        if not os.path.exists(filename):
            print("ERROR: Could not open file: {file}"
                  .format(file=filename))
            exit(1)

######################################

# Do a reverse lookup of an IP address.  Keep a cache because we're
# likely to see the same IP address multiple times.
reverse_lookup_cache = dict()

def reverse_lookup(ip_address):
    if ip_address in reverse_lookup_cache:
        return reverse_lookup_cache[ip_address]

    addr = reversename.from_address(ip_address)
    try:
        ptr = resolver.query(addr, "PTR")[0]
    except:
        # If it fails to resolve, then just put in the IP address
        ptr = ip_address

    print("Resolved {ip} -> {name}".format(ip=ip_address, name=ptr))

    reverse_lookup_cache[ip_address] = ptr
    return ptr

######################################

# Read / parse the XML files.
# Make a list dicts that we'll output to a CSV.

# Flatten the DMARC data into what can be output as a single row
def make_dmarc_row(d, domain):

    def _make_template(d, domain):
        template = dict()

        f = d['feedback']

        # Extract:
        # - report_metadata.org_name
        # - report_metadata.email
        # - report_metadata.report_id
        # - report_metadata.date_range.begin --> Converted to a datetime
        # - report_metadata.date_range.end --> Converted to a datetime
        rm = f['report_metadata']
        template['Reporting Org Name'] = rm['org_name']
        template['Reporting Domain']   = domain
        template['Reporting Email']    = rm['email']
        template['Report ID ']         = rm['report_id']
        ds = datetime.datetime.fromtimestamp(int(rm['date_range']['begin']),
                                             tz=local_tz)
        template['Report Date Start '] = ds
        de = datetime.datetime.fromtimestamp(int(rm['date_range']['end']),
                                             tz=local_tz)
        template['Report Date End ']   = de

        # Extract:
        # - policy_published.domain
        # - policy_published.adkim
        # - policy_published.aspf
        # - policy_published.p
        # - policy_published.pct
        p = f['policy_published']
        template['Policy Domain']         = p['domain']
        template['Policy DKIM alignment'] = p['adkim']
        template['Policy SPF alignment']  = p['aspf']
        template['Policy Action']         = p['p']
        template['Policy Percent']        = p['pct']

        return template

    #------------------------------------------------------

    def _make_out_row(template, record):

        # Auth results may be one or more domains
        def _process_auth_results(out_row, data, label):
            selector = None

            if type(data) is list:
                domains   = list()
                results   = list()
                selectors = list()
                for d in data:
                    domains.append(d['domain'])
                    results.append(d['result'])
                    if 'selector' in d:
                        selectors.append(d['selector'])

                domain   = ','.join(domains)
                result   = ','.join(results)
                selector = ','.join(selectors)

            else:
                domain = data['domain']
                result = data['result']
                if 'selector' in data:
                    selector = data['selector']

            out_row['Auth Results {label} Domain'
                    .format(label=label)] = domain
            out_row['Auth Results {label} Result'
                    .format(label=label)] = result
            out_row['Auth Results {label} Selector'
                    .format(label=label)] = selector

        #------------------------------------------------------

        # For each record, extract:
        # - row.source_ip
        # - row.count
        # - row.policy_evaluated.disposition
        # - row.policy_evaluated.dkim
        # - row.policy_evaluated.spf
        # - identifiers.header_from
        # - auth_results.dkim.domain
        # - auth_results.dkim.result
        # - auth_results.spf.domain
        # - auth_results.spf.result
        out_row = template.copy()

        # Resolve the source IP into a name, if possible
        row = record['row']
        ip_name = reverse_lookup(row['source_ip'])

        out_row['Source IP']      = row['source_ip']
        out_row['Source IP name'] = ip_name
        out_row['Count']          = row['count']
        pe = row['policy_evaluated']
        out_row['Evaluated Policy Disposition'] = pe['disposition']
        out_row['Evaluated Policy DKIM']        = pe['dkim']
        out_row['Evaluated Policy SPF']         = pe['spf']

        i = record['identifiers']
        out_row['Identifiers Header From'] = i['header_from']

        ar = record['auth_results']
        if 'dkim' in ar:
            _process_auth_results(out_row, ar['dkim'], 'DKIM')
        if 'spf' in ar:
            _process_auth_results(out_row, ar['spf'], 'SPF')

        return out_row

    #------------------------------------------------------

    out_rows = list()

    template = _make_template(d, domain)

    f = d['feedback']
    r = f['record']
    if type(r) is list:
        for record in r:
            row = _make_out_row(template, record)
            out_rows.append(row)
    else:
        row = _make_out_row(template, r)
        out_rows.append(row)

    return out_rows

################################################################

out_rows = list()

prog = re.compile('^(.+?)\!')

for list_item in args.file:
    for filename in list_item:
        print("Processing filename: " + filename)

        # The first part of the filename is the source domain.  This
        # is relevant because the owning organization name/info isn't
        # always the same as the source domain (e.g., Yahoo owns a
        # whole bunch of properties -- att.net, yahoo.com,
        # sbcglobal.net, aol.com, ...etc., but the XML always just
        # shows "Yahoo").
        basename = os.path.basename(filename)
        match    = prog.search(basename)
        domain   = match.group(1)

        with open(filename) as f:
            xml_string = f.read()
            d = xmltodict.parse(xml_string)

            rows = make_dmarc_row(d, domain)
            for row in rows:
                out_rows.append(row)

#---------------------------------------------------------------

# Make a union of all the column names
fieldnames = dict()
for row in out_rows:
    for name in row:
        fieldnames[name] = True

#---------------------------------------------------------------

out_file = 'results.csv'
if os.path.exists(out_file):
    os.unlink(out_file)
with open(out_file, 'w') as csvfile:
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames,
                            quoting=csv.QUOTE_ALL)
    writer.writeheader()

    for row in out_rows:
        writer.writerow(row)

print("Wrote results to: {f}".format(f=out_file))
