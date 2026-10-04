#!/usr/bin/env python3

"""
    This routine will poll the Cisco Meraki wireless client information for the Epiphany Catholic Church network
    and store the results into a SQLite database.  The client info includes both associated and non-associated
    clients, which allows further analysis of "traffic" within the reach of the ECC access points, even if not
    actually connected to the network.

    Detailed logging is available of the process and can be customized by changing the logging level
    below (default=DEBUG) and destination (default = "ECCMeraki.log"; uncomment line to set to "None"
    to direct to the console instead).
                Written by DK Fowler ... 21-Jan-2020

                Modified by DK Fowler ... 21-Mar-2020       --- v02.00
    Modified to include validity check on the database, as the getNetworkClients API call from the Meraki
    dashboard API has changed from the original version.  Several new fields were added, and one was deleted.
    Future such changes will cause the app to abort with an appropriate message, which may require database
    restructuring, or archival of the old and creation of a new one.

                Modified by DK Fowler ... 18-May-2020       --- v03.00
    Modified to correct error found in creation of field list for the database.  The prior version
    incorrectly overwrote the field 'switchport' with the 'sendKB' field.

                Modified by DK Fowler ... 27-Jun-2020       --- v03.01
    Modified to add database archival routine.  The existing database will be archived (renamed with
    the creation date/time and last modified date/time appended to the name), and a new database
    created once the size reaches the designated threshold.

                Modified by DK Fowler ... 14-Nov-2020       --- v03.02
    Modified base URI for the Meraki API for v1.0 of the API.  Also, several of the Python
    library calls were changed with v1; changed these to correspond to the new calls:
        dashboard.networks.getOrganizationNetworks -->
                dashboard.organizations.getOrganizationNetworks
        dashboard.clients.getNetworkClients -->
                dashboard.networks.getNetworkClients
    Finally, changed the instantiation of the Meraki dashboard client to suppress logging,
    since this is handled separately by the routine.

    Corrected minor bug where the check for the database size for archival was moved to
    after a verification that the file actually exists.

    Added additional error handling in the fringe case of a constraint failing on an
    INSERT attempt into the database.  The code will now attempt to regenerate the UTC
    timestamp for record written and re-execute the INSERT attempt once.  Also added
    appropriate ROLLBACKs to conditions where errors occur to ensure the current SQLite3
    transaction is aborted cleanly.

                Modified by DK Fowler ... 04-Dec-2020       --- v03.10
    Added additional error handling / messages for failures that occur during Meraki
    Dashboard API calls.

                Modified by DK Fowler ... 16-Dec-2020       --- v03.20
    Added additional error checking prior to getting a connection to the database.

                Modified by DK Fowler ... 26-Apr-2021       --- v03.30
    Added new field now returned from the API (adaptivePolicyGroup) to the database
    schema.

                Modified by DK Fowler ... 28-Apr-2021       --- v03.40
    Modified to handle yet another additional change made to the return from the Meraki
    API call...new field added: recentDeviceConnection.

                Modified by DK Fowler ... 27-Jun-2021       --- v03.50
    More changes made to the return from the Meraki API call...new field added:
    deviceTypePrediction.  Also added additional error checking to catch and handle
    an error that occurs when the Meraki getNetworkClients API return is modified to
    add additional fields in the future.  Finally, updated the Dashboard API library
    to the latest release, v1.10.

                Modified by DK Fowler ... 05-Sep-2021       --- v03.60
    Corrected bug that occurred during archival / recreation of database.  Previously,
    the table structure was recreated using the existing structure retrieved via the API.
    Unfortunately, this does not match the "historical" table structure, which had evolved
    over the course of many API changes through the years.  Instead, changed logic to use
    the "expected" column names as defined herein, which matches the existing structure.
    (Note the column names are the same, these are just in a different order.)

                Modified by DK Fowler ... 08-Sep-2021       --- v03.70
    Added routine to remap the returned fields: values from the Meraki getNetworkClients API
    to match the proper db order.

                Modified by DK Fowler ... 18-Dec-2021       --- v03.80
    Added routine(s) to send Slack message on failures.


"""

from datetime import datetime
import os
import sys
import argparse
import logging
import psutil

import sqlite3
from sqlite3 import Error

import socket

import meraki

# Define version
eccmeraki_version = "03.80"
eccmeraki_date = "21-Dec-2021"

# Parse the command line arguments for the filename locations, if present
parser = argparse.ArgumentParser(description='''Epiphany Catholic Church Meraki Wireless Clients Polling Application.
                                            This routine will poll information from the Cisco Meraki cloud for 
                                            wireless clients and write the data to a SQLite3 database.''',
                                 epilog='''Filename parameters may be specified on the command line at invocation, 
                                        or default values will be used for each.''')
parser.add_argument("-l", "-log", "--log_file_path", default="ECCMeraki.log",
                    help="log filename path")
parser.add_argument("-d", "-db", "--database_file_path", default="ECCMeraki.sqlite3",
                    help="Meraki SQLite3 database filename path")
parser.add_argument("-api", "--api_file_path", default="ECCMeraki_API.txt",
                    help="default API key filename path")
parser.add_argument("-s", "--slk", "--slk-creds-file-path", dest="slk_creds_file_path", default="slk_creds.json",
                    help="Slack API token filename path")
parser.add_argument("-v", "-ver", "--version", action="store_true",
                    help="display application version information")

args = parser.parse_args()

# If the app version is requested on the command line, print it then exit.
if args.version:
    print(F"ECC Meraki wireless client polling application, version {eccmeraki_version}, {eccmeraki_date}...")
    sys.exit(0)

# Set up logging...change as appropriate based on implementation location and logging level
log_file_path = args.log_file_path
# log_file_path = None  # To direct logging to console instead of file

logging.basicConfig(
    filename=log_file_path,
    level=logging.DEBUG,
    format="%(asctime)s:%(levelname)s: %(name)s: line: %(lineno)d %(message)s"
)
logger = logging.getLogger('meraki')

# Location of database file...change as appropriate based on implementation location
ECCMerakiDatabase = args.database_file_path

# Location of the default API key if not otherwise provided
ECCMerakiAPIkey = args.api_file_path

# Location of the Slack API token
ECCSlkAPI = args.slk_creds_file_path

# Set the default timeout for socket operations, as these sometimes timeout with the default (5 seconds).
socket.setdefaulttimeout(30)

# Define database columns expected; this list is used to verify the correct file structure, as the Meraki
# API changes the fields returned over time.
expected_col_names = ['recordWrittenUTC',
                      'networkName',
                      'networkID',
                      'id',
                      'mac',
                      'description',
                      'ip',
                      'ip6',
                      'ip6Local',
                      'user',
                      'firstSeen',
                      'lastSeen',
                      'manufacturer',
                      'os',
                      'recentDeviceSerial',
                      'recentDeviceName',
                      'recentDeviceMac',
                      'ssid',
                      'vlan',
                      'switchport',
                      'sendKB',
                      'recvKB',
                      'status',
                      'notes',
                      'smInstalled',
                      'groupPolicy8021x',
                      'adaptivePolicyGroup',        # new field added 26-Apr-2021
                      'recentDeviceConnection',     # new field added 28-Apr-2021
                      'deviceTypePrediction']       # new field added 27-Jun-2021


def main():
    recs_written = 0  # initialize counter for database records written

    # Define a variable for the maximum database size; the database will be archived and re-created
    # when it reaches this size.
    global max_db_file_size_bytes
    max_db_file_size_bytes = 1073741824  # Maximum database file size in bytes before archival; 1GB at 4K cluster size

    now = datetime.now()
    date_now_str = now.strftime("%Y-%m-%d %H:%M:%S")
    print(F"*** Initiating ECC Meraki wireless client polling, {date_now_str} ***")
    logger.info(F"*** Initiating ECC Meraki wireless client polling, {date_now_str} ***")
    print(F"*** ECC Meraki wireless client polling version {eccmeraki_version}, {eccmeraki_date} ***")
    logger.info(F"*** ECC Meraki wireless client polling version {eccmeraki_version}, {eccmeraki_date} ***")

    logger.info(F"Log filename:         {args.log_file_path}")
    logger.info(F"Database filename:    {args.database_file_path}")
    logger.info(F"API key filename:     {args.api_file_path}")

    if os.path.isfile(ECCMerakiDatabase):  # check if database file exists
        # Check the existing database size.  If the size exceeds the designated
        # threshold, archive it so a new database will be created.
        check_database_size()

    # Check if the database file is currently open by another process
    database_path = os.path.abspath(ECCMerakiDatabase)      # get full pathname
    if has_handle(database_path):
        logger.error(f"Database currently open...aborting")
        print(f"Database currently open...aborting")
        slk_message = "Database currently open...aborting"
        send_slk_and_abort(slk_message)

    # Get the Meraki API key from the specified location...
    api_key = get_api()

    # Instantiate a Meraki dashboard API session
    #       *** Note:  base URI modified for v1 of the API, 11/14/20, DKF
    try:
        dashboard = meraki.DashboardAPI(api_key=api_key,
                                        base_url='https://api.meraki.com/api/v1/',
                                        # log_file_prefix=__file__[:-3],
                                        output_log=False,
                                        print_console=False)
    except meraki.APIError as e:
        err_str = F"""Meraki error while instantiating Dashboard API instance...
                ...Meraki API error: {e}
                ...status code = {e.status}
                ...reason = {e.reason}
                ...error = {e.message}
                ...aborting"""
        logger.error(err_str)
        print(err_str)
        slk_message = "Meraki error while instantiating Dashboard API instance..."
        send_slk_and_abort(slk_message)
    except Exception as e:
        logger.error(F"Error while instantiating Meraki Dashboard API instance...{e} ")
        print(F"Error while instantiating Meraki Dashboard API instance...{e} ")
        logger.error(F"...aborting")
        print(F"...aborting")
        slk_message = F"Meraki error while instantiating Dashboard API instance...{e}"
        send_slk_and_abort(slk_message)

    # Get list of organizations to which API key has access
    try:
        organizations = dashboard.organizations.getOrganizations()
    except meraki.APIError as e:
        err_str = F"""Meraki error while attempting to get list of organizations from Meraki...{e}
                ...Meraki API error: {e}
                ...status code = {e.status}
                ...reason = {e.reason}
                ...error = {e.message}
                ...aborting"""
        logger.error(err_str)
        print(err_str)
        slk_message = F"Error while attempting to get list of organizations from Meraki...{e}"
        send_slk_and_abort(slk_message)
    except Exception as e:
        logger.error(F"Error while attempting to get list of organizations from Meraki...{e}")
        print(F"Error while attempting to get list of organizations from Meraki...{e}")
        if 'local variable \'response\' referenced before assignment' in e.__str__():
            logger.error(F"...possible Internet connection problem?")
            print(F"...possible Internet connection problem?")
        logger.error(F"...aborting")
        print(F"...aborting")
        slk_message = F"Error while attempting to get list of organizations from Meraki...{e}"
        send_slk_and_abort(slk_message)

    # Iterate through list of orgs
    for org in organizations:
        logger.info(f'Analyzing organization {org["name"]}:')
        print(f'\nAnalyzing organization {org["name"]}:')
        org_id = org['id']

        # Get list of networks in organization
        try:
            # Changed following call to reflect API changes made with v1 of API
            #       Modified by DK Fowler...14-Nov-2020
            # networks = dashboard.networks.getOrganizationNetworks(org_id)
            networks = dashboard.organizations.getOrganizationNetworks(org_id)
        except meraki.APIError as e:
            err_str = F"""Meraki error while attempting to get networks for organization {org_id} from Meraki...{e}
                    ...Meraki API error: {e}
                    ...status code = {e.status}
                    ...reason = {e.reason}
                    ...error = {e.message}
                    ...aborting"""
            logger.error(err_str)
            print(err_str)
            slk_message = F"Error occurred while getting networks for organization {org_id} from Meraki...{e}"
            send_slk_and_abort(slk_message)
        except Exception as e:
            logger.error(F"Error occurred while getting networks for organization {org_id} from Meraki...{e}")
            print(F"Error occurred while getting networks for organization {org_id} from Meraki...{e}")
            logger.error(F"...aborting")
            print(F"...aborting")
            slk_message = F"Error occurred while getting networks for organization {org_id} from Meraki...{e}"
            send_slk_and_abort(slk_message)

        recs_written = 0
        db_table = 'merakiClients'

        # First, do an integrity check on the database; check to ensure it contains the database table expected,
        # as well as the expected column names.  This check was added as a result of the Meraki API changing the
        # fields returned for the get-network-clients API.
        #       Added by DK Fowler ... 21-Mar-2020

        if os.path.isfile(ECCMerakiDatabase):  # check if database file exists

            # Check if the expected database table exists within the file
            db_check_table = check_if_table_exists(None, 'merakiClients', ECCMerakiDatabase)
            if not db_check_table:
                print(F"Database table does not exist within the specified database...aborting!")
                logger.error(F"Database table does not exist within the specified database...aborting!")
                slk_message = "Database table does not exist within the specified database...aborting!"
                send_slk_and_abort(slk_message)

            # Found expected table, now verify it's structure matches the expected column list.
            correct_structure_exists = check_table_structure(None, 'merakiClients', expected_col_names,
                                                             ECCMerakiDatabase)
            if not correct_structure_exists:
                print(F"Database structure does not match expected columns...aborting!")
                print(F"...Meraki getNetworkClients API returned parameters may have changed?")
                logger.error(F"Database structure does not match expected columns...aborting!")
                logger.error(F"...Meraki getNetworkClients API returned parameters may have changed?")
                slk_message = "Database structure does not match expected columns...aborting!"
                send_slk_and_abort(slk_message)

        # Attempt to get a connection to the db.  If it doesn't exist, we create it.
        conn = create_connection(ECCMerakiDatabase)

        # Check to ensure we have a valid db connection...if not, abort
        if conn is None:
            logger.error("No connection established to database...aborting.")
            print(F"No connection established to database...aborting.")
            slk_message = "No connection established to database...aborting."
            send_slk_and_abort(slk_message)

        # Iterate through networks
        total_nets = len(networks)
        net_counter = 1
        logger.info(F'...iterating through {total_nets} networks in organization {org_id}')
        print(F'...iterating through {total_nets} networks in organization {org_id}')

        for net in networks:
            # Check the product type to filter out any other than 'switch' and 'wireless'
            if not (('switch' or 'wireless') in net['productTypes']):
                print(F"Skipping processing for product type that is not a switch or wireless...{net['productTypes']}")
                break

            logger.info(f'Finding clients in network {net["name"]} ({net_counter} of {total_nets})')
            print(f'Finding clients in network {net["name"]} ({net_counter} of {total_nets})')
            try:
                # Get the last date/time in UTC for records in the database
                last_written_dt = select_db_last_run_time(conn, db_table)
                if last_written_dt is None:
                    print(F"No records detected in database, so setting polling start to maximum allowed (31 days).")
                else:
                    print(F"Last date/time (UTC) written to database was:  {last_written_dt}")

                # Calculate the timespan for retrieving client information.  Timespan for the Meraki Dashboard API
                # call is specified in seconds from the current date/time.
                current_utc_dt = datetime.utcnow()
                current_utc_timestamp = current_utc_dt.timestamp()  # convert datetime to a timestamp

                if last_written_dt is None:
                    client_timespan = 60 * 60 * 24 * 31  # 31 days is the max look-back time API allows
                else:
                    # Convert the last written date/time string from the database to a datetime object
                    last_written_dt_from_iso = datetime.fromisoformat(last_written_dt)
                    # Subtract the last written timestamp from the current timestamp to get the number of seconds
                    # to retrieve for the timespan
                    client_timespan = current_utc_timestamp - last_written_dt_from_iso.timestamp()

                # Get list of clients on network, filtering on timespan of either the last 31 days, or based
                # on the last date/time written to the database.
                #
                # Changed following call to reflect changes made with v1 of the API
                #       Modified by DK Fowler ... 14-Nov-2020
                # clients = dashboard.clients.getNetworkClients(net['id'],
                #                                              timespan=client_timespan,
                #                                              perPage=1000,
                #                                              total_pages='all')
                clients = dashboard.networks.getNetworkClients(net['id'],
                                                               timespan=client_timespan,
                                                               perPage=1000,
                                                               total_pages='all')
            except meraki.APIError as e:
                err_str = F"""Meraki API error occurred while retrieving list of clients for org {org_id}, network {net['id']}... 
                        ...Meraki API error: {e}
                        ...status code = {e.status}
                        ...reason = {e.reason}
                        ...error = {e.message}
                        ...aborting"""
                logger.error(err_str)
                print(err_str)
                slk_message = err_str
                send_slk_and_abort(slk_message)
            except Exception as e:
                err_str = F"""Error occurred while retrieving list of clients for org {org_id}, network {net['id']}...
                            ...error:  {e}
                            ...aborting"""
                logger.error(err_str)
                print(err_str)
                slk_message = err_str
                send_slk_and_abort(slk_message)
            else:
                # Got clients info, process and add to SQLite db...
                if clients and (len(clients) != 0):
                    # Get a list of field names returned; add fields for record-written date/time, network name and ID
                    """
                    field_names = list(clients[0].keys())
                    field_names.insert(0, 'recordWrittenUTC')
                    field_names.insert(1, 'networkName')
                    field_names.insert(2, 'networkID')
                    # Break 'usage' into 'sendKB', 'recvKB'...first, find the index of the 'usage' field
                    #       Modified 28-Apr-2021 to locate index position vs. fixed position
                    usage_index = field_names.index('usage')
                    field_names[usage_index] = 'sendKB'  # replace field 'usage'
                    field_names.insert((usage_index+1), 'recvKB')
                    """
                    logger.info(F'...found {len(clients)} client records')
                    print(F'...found {len(clients)} client records')


                    # Construct the SQL create-table statement...
                    create_table_sql_str, table_fields_dict = construct_create_table_sql(db_table,
                                                                                         expected_col_names)
                    # Have a valid db connection; see if the merakiClients db exists
                    if check_if_table_exists(conn, db_table, ECCMerakiDatabase):
                        logger.info(F"Table {db_table} already exists...continuing processing...")
                    else:
                        logger.info(F"Table {db_table} does not exist...creating...")
                        create_tbl_status = create_table_from_string(conn, db_table, create_table_sql_str)
                        if not create_tbl_status:
                            logger.error(F"Error creating table {db_table}...aborting...")
                            print(F"Error creating table {db_table}...aborting...")
                            slk_message = "Error creating table {db_table}...aborting..."
                            send_slk_and_abort(slk_message)

                    # Now loop through the clients returned and record these in the database.
                    for client in clients:
                        # Reorder the client fields returned from the API to match the current db
                        # table structure; this is due to the many changes that have occurred in
                        # the fields returned from the API.
                        #       Added by DK Fowler ... 08-Sep-2021
                        client = reorder_client_fields(client)
                        insert_record_status = create_database_record(conn,
                                                                      db_table,
                                                                      net['name'],
                                                                      net['id'],
                                                                      client,
                                                                      table_fields_dict)
                        if insert_record_status:
                            recs_written += 1

            net_counter += 1

    logger.info(F"Total client records written:  {recs_written}")
    print(F"\nTotal client records written:  {recs_written}")


def get_api():
    """
        This routine will attempt to read the default API key from the specified external file.
                Written by DK Fowler ... 02-Jan-2020
        :return api_key:    ECC Meraki API key read from specified external file

    """
    try:
        with open(ECCMerakiAPIkey, 'r', encoding='utf-8') as f:
            try:
                api_key = f.readline(40)  # API key should be 40 bytes in length
                return api_key
            except Exception as e:
                logger.error(F"Error occurred during attempt to read ECC Meraki API key from file...")
                logger.error(F"...error:  {e}")
                logger.error(F"...aborting...")
                print(F"Error occurred during attempt to read ECC Meraki API key from file...")
                print(F"...error:  {e}")
                print(F"...aborting...")
                slk_message = F"Error occurred during attempt to read ECC Meraki API key from file...\n{e}"
                send_slk_and_abort(slk_message)
    except Exception as e:
        logger.error(F"Error during attempt to open ECC Meraki API key file...{e}")
        logger.error(F"...aborting...")
        print(F"Error during attempt to open ECC Meraki API key file...{e}")
        print(F"...aborting...")
        slk_message = F"Error during attempt to open ECC Meraki API key file...{e}"
        send_slk_and_abort(slk_message)


def check_if_table_exists(conn, meraki_table, meraki_connection_database):
    """
        This routine will check for the existence of the table passed in meraki_table in the
        database file meraki_connection_database.  If it exists, the function will return true; otherwise
        it will return false.
            Written by DK Fowler ... 15-Mar-2020
    :param conn:                        database connection (may exist already, or be set to None)
    :param meraki_table:                table name to check for existence
    :param meraki_connection_database:  database file to check for table existence
    :return:                            True if table exists; otherwise, False
    """
    if conn is None:
        try:
            conn = create_connection(meraki_connection_database)
        except Error:
            logger.error(
                F"Error connecting to database {meraki_connection_database} to check for table {meraki_table} existence.")
            print(
                F"Error connecting to database {meraki_connection_database} to check for table {meraki_table} existence.")
            return False

    # Check the SQLite master table for the table name
    c = conn.cursor()
    find_table_query = "SELECT count(name) FROM sqlite_master WHERE type='table' AND name=? "
    logger.debug(F"Find table query string:  {find_table_query}")
    c.execute(find_table_query, (meraki_table,))

    # Now check the number returned; if not 1, then table doesn't exist
    found_flag = False
    if c.fetchone()[0] == 1:
        logger.info(f"Table '{meraki_table}' found...")
        found_flag = True
    else:
        logger.info(f"Table '{meraki_table}' not found...")

    # commit the changes (none here)
    conn.commit()
    # close the connection

    return found_flag


def check_table_structure(conn, meraki_table, expected_col_names, meraki_connection_database):
    """
        This routine will check for the expected structure of the table passed in meraki_table in the
        database file meraki_connection_database.  If the defined fields match the expected structure
        as passed in the column names list the function will return true; otherwise it will return false.
            Written by DK Fowler ... 15-Mar-2020
            Modified by DK Fowler ... 21-Mar-2020
        Added parameter to pass expected column names list to provide greater flexibility in handling
        different Meraki client database types.

    :param conn:                        database connection (may exist already, or be set to None
    :param meraki_table:                table name to check for correct structure
    :param expected_col_names:          list containing expected column names for passed table
    :param meraki_connection_database:  database file to check for correct structure
    :return:                            True if table matches expected structure; otherwise, False
    """

    if conn is None:
        try:
            conn = create_connection(meraki_connection_database)
        except Error:
            logger.error(
                F"Error connecting to database {meraki_connection_database} to check for table {meraki_table} existence.")
            print(
                F"Error connecting to database {meraki_connection_database} to check for table {meraki_table} existence.")
            return False

    # Check the SQLite master table for the table name
    c = conn.cursor()

    # Get a list of column names from the first record in the table
    # From example at: https://www.daniweb.com/programming/software-development/threads/
    #                       124403/sqlite3-how-to-see-column-names-for-table
    #   cur.execute("SELECT * FROM SomeTable")
    #   col_name_list = [tuple[0] for tuple in cur.description]
    find_first_rec_query = "SELECT * FROM '" + meraki_table + "' LIMIT 1"
    logger.debug(F"Get first record table query string:  {find_first_rec_query}")
    c.execute(find_first_rec_query)

    col_names = [cols[0] for cols in c.description]
    if col_names == expected_col_names:
        logger.info(F"Column names for table {meraki_table} match expected structure for database "
                    F"{meraki_connection_database}.")
        return True
    else:
        logger.error(F"Columns do not match expected structure for table {meraki_table}, database "
                     F"{meraki_connection_database}.")
        print(F"Columns do not match expected structure for table {meraki_table}, database "
              F"{meraki_connection_database}.")
        return False


def create_connection(db_file):
    """ This routine will create a database connection to the SQLite database specified by the db_file
        (From SQLite Tutorial at sqlitetutorial.net)
                Modified by DK Fowler ... 21-Jan-2020
    :param db_file: database file
    :return: Connection object or None
    """
    conn = None
    try:
        conn = sqlite3.connect(db_file)
        logger.debug(F"Connected to database:  {db_file}")
    except Error as e:
        logger.error(F"Error occurred while attempting to establish connection to database...")
        logger.error(F"...{e}")
        print(F"Error occurred while attempting to establish connection to database...")
        print(F"...{e}")

    return conn


def create_table(conn, create_table_sql):
    """ This routine will create a table from the create_table_sql statement passed
        (From SQLite Tutorial at sqlitetutorial.net)
                Modified by DK Fowler ... 21-Jan-2020
    :param conn: Connection object
    :param create_table_sql: a CREATE TABLE statement
    :return:    True if successful, else False
    """
    try:
        c = conn.cursor()
        c.execute(create_table_sql)
        logger.info(F"Successfully created database table")
        c.close()
        return True
    except sqlite3.Error as e:
        logger.error(F"Error occurred while attempting to create database table...")
        logger.error(F"...{e}")
        print(F"Error occurred while attempting to create database table...")
        print(F"...{e}")
        return False


def check_if_table_exists(conn, merakiTable, ECCMerakiDatabase):
    """
        This routine will check for the existence of the table passed in merakiTable in the
        database file ECCMerakiDatabase.  If it exists, the function will return true; otherwise
        it will return false.
            Written by DK Fowler ... 21-Jan-2020
    :param conn:                database connection (may exist already, or be set to None
    :param merakiTable:         table name to check for existence
    :param ECCMerakiDatabase:   database file to check for table existence
    :return:                    True if table exists; otherwise, False
    """
    if conn is None:
        try:
            conn = create_connection(ECCMerakiDatabase)
        except Error:
            logger.error(
                F"Error connecting to database {ECCMerakiDatabase} to check for table {merakiTable} existence.")
            print(
                F"Error connecting to database {ECCMerakiDatabase} to check for table {merakiTable} existence.")
            return False

    # Check the SQLite master table for the table name
    c = conn.cursor()
    find_table_query = "SELECT count(name) FROM sqlite_master WHERE type='table' AND name=? "
    logger.debug(F"Find table query string:  {find_table_query}")

    try:
        c.execute(find_table_query, (merakiTable,))
    except sqlite3.Error as e:
        logger.error(F"Error attempting to verify structure of Meraki database...")
        logger.error(F"...error:  {e}")
        logger.error(F"...aborting")
        print(F"Error attempting to verify structure of Meraki database...")
        print(F"...error:  {e}")
        print(F"...aborting")
        slk_message = F"Error attempting to verify structure of Meraki database...{e}"
        send_slk_and_abort(slk_message)

    # Now check the number returned; if not 1, then table doesn't exist
    found_flag = False
    if c.fetchone()[0] == 1:
        logger.info(f"Table '{merakiTable}' found...")
        found_flag = True
    else:
        logger.info(f"Table '{merakiTable}' not found...")

    # commit the changes (none here)
    conn.commit()

    return found_flag


def create_table_from_string(conn, db_table, create_table_sql_str):
    """
        This routine will attempt to create a database table given the passed database connection,
        table name, and SQL creation string.  If successful, it will also create secondary
        indicies.
            Written by DK Fowler ... 21-Jan-2020
    :param conn:                database connection (may exist already, or be set to None)
    :param db_table:            table name to create
    :param create_table_sql_str string containing SQL statement to create table
    :return:                    True if table created successfully; otherwise, False
    """

    table_success = False  # Assume failure
    indicies_success = False

    # Check to make sure we have a database connection
    if conn is not None:
        # SQL strings to create secondary indicies.
        sql_create_meraki_sec_index1 = "CREATE INDEX " + "id_idx ON " + \
                                       db_table + "(id);"
        table_exists = check_if_table_exists(conn, db_table, ECCMerakiDatabase)
        if not table_exists:
            table_success = create_table(conn, create_table_sql_str)
            if not table_success:
                logger.debug(F"Error occurred attempting to create table {db_table}...aborting")
                slk_message = F"Error occurred attempting to create table {db_table}...aborting"
                send_slk_and_abort(slk_message)
            # Create secondary indicies
            try:
                indicies_success = conn.execute(sql_create_meraki_sec_index1)
                # indicies_success = conn.execute(sql_create_meraki_sec_index2)
            except sqlite3.Error as e:
                logger.error(F"Error creating secondary indicies for table {db_table}, {e}")
                print(F"Error creating secondary indicies for table {db_table}, {e}")
        else:
            logger.debug(F"Database table {db_table} exists...")
            table_success = True  # Set the success flags, as table and indicies already exist
            indicies_success = True
    else:
        logger.error("Error...the Meraki database connection did not exist when attempting to create "
                     F"table {db_table}")
        logger.error(F"...aborting")
        print("Error...the Meraki database connection did not exist when attempting to create "
              F"table {db_table}")
        print(F"...aborting")
        slk_message = F"Error...the Meraki database connection did not exist when attempting to create " \
                      F"table {db_table}"
        send_slk_and_abort(slk_message)

    if table_success and indicies_success:
        return True
    else:
        return False


def construct_create_table_sql(table_name, field_names):
    """
        This routine will construct a SQLite CREATE TABLE SQL statement from the passed parameters.
        This can be used in subsequent calls to the SQLite Python API to create a new database
        table for the passed table name.

        The field names come from the Meraki API get-client information.

        In addition to returning a string containing the SQL statement to create the table, it will
        also return a dictionary containing field name and datatype for subsequent use in the
        application.
                Written by DK Fowler ... 22-Jan-2020

                Modified by DK Fowler ... 21-Mar-2020
        Modified to reflect changes in the returned fields from the Meraki get network clients API call.
        It appears that new fields ip6Local, usage, notes, smsInstalled, and groupPolicy8021x were added
        to the returned data, and the prior field switchport was dropped.
    :param table_name:          Database table to create (if it doesn't exist)
    :param field_names:         List containing fields for creation of table
    :return datatype_dict:      Dictionary containing field name as key with datatype returned
    :return: SQL_create_str:    SQL string to create the table
    """

    # Create datatype list
    #       Modified 28-Apr-2021 to add additional field for recentDeviceConnection
    #       Modified 27-Jun-2021 to add additional field for deviceTypePrediction
    field_sql_types = ['TEXT'] * 18
    for i in range(0, 4):       # vlan, switchport, sendKB, recvKB
        field_sql_types.append('INTEGER')
    for i in range(0, 7):
        field_sql_types.append('TEXT')

    # Create a SQLite datatype dictionary, with the key being field name from the field_name list passed
    # and the value being the datatype defined in the field_sql_types list
    datatype_dict = {}
    try:
        datatype_dict = {field_name: field_sql_types[idx] for idx, field_name in enumerate(field_names)}
    except IndexError as e:
        # Added 27-Jun-2021 to catch change in API return (more field names than data types)
        index_err_string = 'Error occurred while creating the datatype dictionary...\n' \
                           '(Perhaps the Meraki API return has changed?)\nAborting...'
        logger.error(F'{index_err_string},\nError:  {e}')
        print(F'{index_err_string},\nError:  {e}')
        slk_message = F"{index_err_string},\nError:  {e}"
        send_slk_and_abort(slk_message)

    logger.debug(F"SQLite datatype dictionary created:  {datatype_dict}")

    # Construct SQL table create string
    SQL_create_str = "CREATE TABLE IF NOT EXISTS " + table_name + " ("

    # Loop through data fields...adding to the SQL CREATE statement with field name, datatype
    for field_idx in range(0, len(field_names)):
        SQL_create_str += field_names[field_idx] + " "
        SQL_create_str += field_sql_types[field_idx]
        SQL_create_str += ", "

    # Add the primary key and terminate the CREATE string
    SQL_create_str += "PRIMARY KEY (id, recordWrittenUTC) ); "

    logger.debug(F"SQL {table_name} table create string: ")
    logger.debug(F"...{SQL_create_str}")

    return SQL_create_str, datatype_dict


def reorder_client_fields(org_client):
    """
        This routine will reorder the passed dictionary of client columns to match the existing
        database table structure.  This is required due to the frequent changes that have
        occurred over time with the fields returned from the Meraki getNetworkClients API.
            Written by DK Fowler ... 08-Sep-2021
    :param org_client:      dictionary containing the field: value pairs returned from the API
    :return:                reordered dictionary of field: value pairs matching db/table structure
    """

    new_client = {}
    for db_field in expected_col_names[3:]:
        try:
            # for sendKB/recvKB, we need to pull the values from the 'usage' dictionary elements
            if db_field == 'sendKB':
                new_client[db_field] = org_client['usage']['sent']
            elif db_field == 'recvKB':
                new_client[db_field] = org_client['usage']['recv']
            else:
                new_client[db_field] = org_client[db_field]
        except Error as e:
            print(F"Error during reordering of returned API client fields...{e}")
            print(F"...Meraki getNetworkClients API return has changed?")
            logger.error(F"Error during reordering of returned API client fields...{e}")
            logger.error(F"...Meraki getNetworkClients API return has changed?")
            slk_message = F"Error during reordering of returned API client fields...{e}\n"
            slk_message += "...Meraki getNetworkClients API return has changed?"
            send_slk_and_abort(slk_message)

    return new_client


def construct_insert_table_sql(db_table, db_fields):
    """
        This routine will construct a SQLite INSERT statement to be used in an attempt to
        write a new record to the table passed.
            Written by DK Fowler ... 24-Oct-2019
    :param db_table:        table name to which a record INSERT will be attempted
    :param db_fields        Dictionary of field names for the record
    :return:                SQLite string containing the INSERT statement
    """

    # logger.debug(F"DB fields:  {db_fields}")
    db_insert_sql_str = '''INSERT INTO ''' + db_table + ''' ('''

    field_cnt = 0
    # logger.debug(F"Length of passed field list:  {len(db_fields)}")
    for field in db_fields:
        field_cnt += 1
        db_insert_sql_str += field
        # logger.debug(F"...field count:  {field_cnt}, field:  {field}")
        if field_cnt != len(db_fields):  # don't add the comma for the last field
            db_insert_sql_str += ', '
        else:
            db_insert_sql_str += ') VALUES ('

    # Insert placeholders for all fields with a trailing "," until the last field; in this case, remove the
    # trailing "," and terminate.
    ph_range = range(0, len(db_fields) - 1)
    for field_ph in ph_range:
        db_insert_sql_str += '''?,'''

    db_insert_sql_str += '''?)'''

    logger.debug(F"SQL INSERT statement:  '{db_insert_sql_str}'")

    return db_insert_sql_str


def create_database_record(conn, db_table, network_name, network_id, client, values_dict):
    """
        This routine will attempt to write a record to the passed table with the passed
        list of record names / values.  If successful, the routine will return True, else False.
            Written by DK Fowler ... 22-Jan-2020
    :param conn:            database connection (may exist already, or be set to None)
    :param db_table:        table name to which a record write is attempted
    :param network_name:    network name
    :param network_id:      network ID
    :param client           client dictionary containing field name: value
    :param values_dict:     dictionary of field names: field values for the record
    :return:                True if table created successfully; otherwise, False
    """

    # First create a SQL string for INSERTing the record into the passed table
    sql_insert = construct_insert_table_sql(db_table, values_dict.keys())

    # Get the current date/time in UTC for the record INSERT
    recordWrittenUTC = datetime.utcnow()

    logger.debug(F"......date written set to: {datetime.strftime(recordWrittenUTC, '%Y-%m-%d %H:%M:%S.%f')}")
    cur = conn.cursor()  # Get a cursor for the db connection
    # Make sure we have a database connection
    if conn is not None:
        logger.debug(F"Attempting record insert...table:  {db_table}")
        try:
            val_list = []
            date_written_str = datetime.strftime(recordWrittenUTC, "%Y-%m-%d %H:%M:%S.%f")
            val_list.insert(0, date_written_str)  # insert common key values in the beginning of the value list
            val_list.insert(1, network_name)
            val_list.insert(2, network_id)
            idx = 3
            # for db_key, db_val in client.items(): # removed 8-Sep-2021, DKF
            for db_val in client.values():
                # Usage in sent/received kilobytes is included in the client record as an embedded dictionary;
                # break this into separate send/received fields for ease in analysis.
                # *** No longer required as of v03.70, as passed client has now been reordered
                # *** to match the db table structure.
                #       Removed 08-Sep-2021...DK Fowler
                """
                if db_key == 'usage':
                    val_list.insert(idx, client['usage']['sent'])
                    idx += 1
                    val_list.insert(idx, client['usage']['recv'])
                    idx += 1
                else:
                """
                val_list.insert(idx, db_val)
                idx += 1

            # print(F"Values used in INSERT:  {val_list}")
            logger.debug(F"...field values {val_list}")
            cur.execute(sql_insert, val_list)
            logger.debug(F"Record written for network {network_name} ({network_id}), client: {client['id']}, "
                         F"date: {recordWrittenUTC}, table: {db_table}")
        except sqlite3.IntegrityError as e:
            # this error generated when a unique constraint fails
            logger.error(F"Error inserting record into database:  {e}")
            print(F"Error inserting record into database:  {e}")
            # try regenerating the current time stamp and re-excuting the insert;
            # (a conflict on timestamp and id should REALLY never happen, but just
            # to handle a potentially fringe case...)
            recordWrittenUTC = datetime.utcnow()
            date_written_str = datetime.strftime(recordWrittenUTC, "%Y-%m-%d %H:%M:%S.%f")
            val_list.insert(0, date_written_str)  # insert common key values in the beginning of the value list
            # print(F"Values used in INSERT:  {val_list}")
            logger.debug(F"...new field values {val_list}")
            # rollback any prior uncommitted transactions, then attempt the INSERT again
            conn.rollback()
            try:
                cur.execute(sql_insert, val_list)
                logger.debug(F"Record written for network {network_name} ({network_id}), client: {client['id']}, "
                             F"date: {recordWrittenUTC}, table: {db_table}")
            except sqlite3.Error as e:
                logger.error(F"...second attempt to INSERT record failed:  {e}")
                print(F"...second attempt to INSERT record failed:  {e}")
                cur.close()
                conn.rollback()
                return False
        except sqlite3.Error as e:
            cur.close()
            conn.rollback()
            logger.error(F"Error writing to database table {db_table}, {e}")
            err_string = e.__str__()  # returns string with error message
            # define text for duplicate primary key error; (would be more effective to check extended error code,
            # but Python doesn't seem to support this yet??
            unique_err_str = "UNIQUE constraint failed:"

            # The following error should NEVER occur, as the date written is part of the key and is
            # created in this routine.
            if unique_err_str in err_string:
                logger.error(F"Duplicate key detected...record already exists in database...")
            else:  # only display error msg to console if error other than dup-key occurs
                print(F"Error writing to database table {db_table}, {e}")
            return False
        except ValueError as e:  # Catches malformed INSERT in some instances...
            logger.error(F"Value error occurred during attempt to INSERT record in table {db_table}, error:  {e}")
            logger.error(F"...SQL INSERT statement:  {sql_insert}")
            logger.error(F"...Values used in INSERT:  {val_list}")
            print(F"Value error occurred during attempt to INSERT record in table {db_table}, error:  {e}")
            print(F"...SQL INSERT statement:  {sql_insert}")
            print(F"...Values used in INSERT:  {val_list}")
            cur.close()
            conn.rollback()
            return False
        except Exception as e:
            logger.error(F"Exception occurred during INSERT:  {e}")
            logger.error(F"...SQL INSERT statement:  {sql_insert}")
            logger.error(F"...Values used in INSERT:  {val_list}")
            print(F"Exception occurred during INSERT:  {e}")
            print(F"...SQL INSERT statement:  {sql_insert}")
            print(F"...Values used in INSERT:  {val_list}")
            cur.close()
            conn.rollback()
            return False
    else:
        logger.error(F"No database connection detected while attempting to write new record, table {db_table}")
        print(F"No database connection detected while attempting to write new record, table {db_table}")
        slk_message = F"No database connection detected while attempting to write new record, table {db_table}"
        send_slk_and_abort(slk_message)

    conn.commit()
    cur.close()
    return True


def select_db_last_run_time(conn, db_table):
    """
    Query last run time from the specified SQLite database connection.
    (Based on SQLite Tutorial at sqlitetutorial.net)

    This routine will return the last run date/time written to the passed SQLite table, based
    on previous calls to the Meraki Dashboard get network clients API.  The intent is to provide the last
    run date/time in order to set the next polling starting point.
            Written by DK Fowler ... 24-Jan-2020

    :param conn:        the database connection object
    :param db_table:    the SQLite3 database table to be queried
    :return:            the last run date/time interval recorded in UTC, or None if none
    """

    cur = conn.cursor()

    # Build SQL query string, including exclusion of "blank" records...
    #   Note:   The Python SQLite API does not support parameterizing the table name, so we need to build
    #           the SQL SELECT statement with the passed table name.
    last_written_sql = "SELECT * FROM " + db_table + " ORDER BY recordWrittenUTC DESC LIMIT 1"
    logger.debug(F"SQL for last record written to database table {db_table}:  ")
    logger.debug(F"{last_written_sql}")
    try:
        cur.execute(last_written_sql)
    except sqlite3.Error as e:
        logger.debug(F"Error occurred while attempting to retrieve last run date/time from table {db_table}...")
        logger.debug(F"...error occurred was: {e}")
        print(F"Error occurred while attempting to retrieve last run date/time from table {db_table}...")
        print(F"...error occurred was: {e}")
        # Check for table not found in database; this would occur on first initialization of a new database
        if 'no such table' in e.__str__():
            logger.info(F"...new database will be initialized")
            print(F"...new database will be initialized")
            last_written_dt = None
            return last_written_dt
        else:
            logger.debug(F"...aborting...")
            print(F"...SQL retrieval statement:  {last_written_sql}")
            print(F"...aborting...")
            cur.close()
            conn.close()
            slk_message = F"Error occurred while attempting to retrieve last run date/time from table {db_table}...\n"
            slk_message += F"...SQL retrieval statement:  {last_written_sql}"
            send_slk_and_abort(slk_message)

    rows = cur.fetchall()

    row_cnt = 0
    for row in rows:
        row_cnt = row_cnt + 1
        logger.debug(F"Last run date/time (UTC) for table {db_table}: {row[0]}")
        logger.debug(row)
        last_written_dt = row[0]  # recordWrittenUTC is the first column in the returned row
    """
        If no rows are returned for this thermostat, then there were previously no entries written in
        the passed table.  This would typically happen during first run of the routine.  In this case, 
        return None for the last run date/time.
    """
    if row_cnt == 0:
        last_written_dt = None
        logger.debug(F"No records found for table {db_table} while retrieving last date/time written")

    cur.close()
    return last_written_dt


def check_database_size():
    """
    This routine will check the existing database size and compare it against the designated
    threshold size.  If it exceeds it, a routine to archive the exiting database will be called.
            Written by DK Fowler ... 27-Jun-2020
    """

    global max_db_file_size_bytes

    db_size_bytes = os.path.getsize(ECCMerakiDatabase)

    if db_size_bytes >= max_db_file_size_bytes:
        logger.info(F"Database size of {db_size_bytes} exceeds maximum ({max_db_file_size_bytes}), "
                    F"archiving file...")
        print(F"Database size of {db_size_bytes} exceeds maximum ({max_db_file_size_bytes}), "
              F"archiving file...")
        archive_db()


def archive_db():
    """
        This routine will "archive" the existing database file by renaming it, such that the next
        program iteration will re-create a new one.  The archival file name will be in the form:
        {db filename}-{create-date/time}-{mod-date/time}.{db extension}, where
        create-date/time is the database creation date/time in the form "YYYYMMDDHHMM", and
        mod-date/time is the database last-modified date/time in the form "YYYYMMDDHHMM".
                Written by DK Fowler ... 27-Jun-2020
    """

    logger.info(F"Beginning database archival...")
    print(F"Beginning database archival...")

    # Get the creation / last modified date/time of the existing file for use in constructing the
    # archival file name...
    db_modified_time = os.path.getmtime(ECCMerakiDatabase)
    db_create_time = os.path.getctime(ECCMerakiDatabase)
    # Convert timestamps to strings in proper form
    db_create_string = datetime.fromtimestamp(db_create_time).strftime('%Y%m%d%H%M')
    db_modified_string = datetime.fromtimestamp(db_modified_time).strftime('%Y%m%d%H%M')
    # Get the filename/ext string of the existing database
    db_basename = os.path.basename(ECCMerakiDatabase)
    # Split the filename into name/extension components
    fn = os.path.splitext(db_basename)
    db_filename = fn[0]
    db_ext = fn[1]
    # Construct the new archival filename
    archival_db_name = db_filename + "-" + db_create_string + "-" + db_modified_string + db_ext
    print(F"Archival database name:  {archival_db_name}.")

    # Attempt to rename the existing database
    try:
        os.rename(ECCMerakiDatabase, archival_db_name)
        logger.info(F"Renamed database to: {archival_db_name}.")
        print(F"Renamed database to:  {archival_db_name}.")
    except Error as e:
        logger.error(F"Error attempting to archive (rename) database file: {e}...")
        logger.error(F"...original database name:  {ECCMerakiDatabase}")
        logger.error(F"...archival database name:  {archival_db_name}")
        print(F"Error attempting to archive (rename) database file: {e}...")
        print(F"...original database name:  {ECCMerakiDatabase}")
        print(F"...archival database name:  {archival_db_name}")


def has_handle(database_path):
    for proc in psutil.process_iter():
        try:
            for item in proc.open_files():
                if database_path == item.path:
                    logger.error(f"Database file currently open by process:  {proc.pid},"
                                 f"{proc.name}...")
                    print(f"Database file currently open by process:  {proc.pid},"
                          f"{proc.name}...")

                    return True
        except Exception:
            pass

    return False


def get_slack_creds():
    """
            This routine will read the Slack credentials file specified (in JSON format) and
            return a dictionary with the specified contents (API token and channel).
                    Written by DK Fowler ... 15-Oct-2021

    :return:        Dictionary containing the Slack credentials (API token and channel).
    """
    json_slk_creds_dict = {}
    # Attempt to open the tasks-to-monitor/state file and read contents
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


def send_slk_and_abort(slk_message):
    slk_message = "Fatal error occurred during Meraki client polling...\n" + slk_message
    slk_status = send_to_slack(slk_message)
    if not slk_status:
        print(f'...error occurred while sending to Slack...')
        logger.error(f'...error occurred while sending to Slack...')
    sys.exit(1)


if __name__ == '__main__':
    start_time = datetime.now()
    main()
    end_time = datetime.now()
    logger.info(f'Meraki wireless client polling complete, total runtime {end_time - start_time}')
    print(f'\nMeraki wireless client polling complete, total runtime {end_time - start_time}')
