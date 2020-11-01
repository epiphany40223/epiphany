#!/usr/bin/env python3

"""
    This routine will listen for messages on the MQTT channel specified and add the data contained
    to a SQLite3 database.
                Written by DK Fowler ... 09-Jun-2020

    Modified to add routine to automatically archive the database when it reaches a designated
    size threshold.
                Modified by DK Fowler ... 13-Jun-2020       --- v01.10

    Modified to change the MQTT blocking loop to a non-blocking one; this allows handling keyboard
    interrupts to print exit summary statistics and cleanup MQTT.  Added an exit handler to print
    summary statistics.  Added keyboard interrupt (CTRL-C) handler that calls the exit handler.
    The exit handler now will print a summary of the total number of MQTT messages received and
    the number of database records written, as well as the total run-time.  Added error handling
    to the MQTT connection handler that will print a verbose error message if the connect fails.

    Note that handling keyboard interrupts and the expected behavior will likely differ under
    other operating systems than Windows and may require modification.
            Modified by DK Fowler ... 29-Jun-2020           --- v01.20

    Modified to fix a couple of issues:
        1) The database was not correctly created at initial runtime if it did not exist.

        This was due to a bug that would cause the check_database_size routine to fail if the
        database did not currently exist (as at first run or when database has been archived).

        2) On reconnect (e.g., after network disruption), the topic was not resubscribed.

        Moved the attempt to subscribe to the channel to the on_connect callback so that if a
        reconnection occurs, the topic will be resubscribed at that time.

            Modified by DK Fowler ... 01-Aug-2020           --- v01.30

    Modified to add additional functionality to check for loss of connectivity; added timer
    to check periodically for the last MQTT message published.  If greater than the specified
    time period, the application will restart itself.

            Modified by DK Fowler ... 08-Aug-2020           --- v01.40

    Modified to add notification of a restart via GMail.  Added GMail account credential retrieval
    from a file specified in the command-line arguments.  Added support for a "mute" period for
    notifications (in minutes) as an argument, such that repeat notices will not be sent within
    the specified timeframe.  The last notification date/time will be saved to a file specified
    as an argument for later retrieval.

            Modified by DK Fowler ... 13-Aug-2020           --- v02.00
"""

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
import logging

import sqlite3
from sqlite3 import Error

# Define version
eccmqtt_iot_version = "02.00"
eccmqtt_iot_date = "13-Aug-2020"

# Parse the command line arguments for the filename locations, if present
parser = argparse.ArgumentParser(description='''Epiphany Catholic Church MQTT IoT Listener Application.
                                            This routine will listen for MQTT messages on the prescribed 
                                            IoT temp/humidity channel and write the data to a SQLite3 database.''',
                                 epilog='''Filename parameters may be specified on the command line at invocation, 
                                        or default values will be used for each.''')
parser.add_argument("-l", "-log", "--log_file_path", default="ECCMQTTIoT.log",
                    help="log filename path")
parser.add_argument("-d", "-db", "--database_file_path", default="ECCTempHum.sqlite3",
                    help="IoT Temperature / Humidity SQLite3 database filename path")
parser.add_argument("-c", "--credentials_file_path", default="ECCMQTTIoT_Credentials.txt",
                    help="default MQTT user/pass credentials filename path")
parser.add_argument("-b", "--mqtt_broker", default="127.0.0.1",
                    help="default MQTT broker address")
parser.add_argument("-t", "--timer_check", default=20,
                    help="default connectivity check timer, in minutes")
parser.add_argument("-m", "--gmail_credentials_file_path", default="ECCMQTTIoT_GMail_Credentials.txt",
                    help="default GMail user/pass credentials filename path")
parser.add_argument("-n", "--last_notice_file_path", default="ECCMQTTIoT_Last_Notice.dat",
                    help="default last notification filename path")
parser.add_argument("-s", "--last_notice_silence_time", default=1440,
                    help="default last notification silence time, in minutes")
parser.add_argument("-v", "-ver", "--version", action="store_true",
                    help="display application version information")

args = parser.parse_args()

# If the app version is requested on the command line, print it then exit.
if args.version:
    print(F"ECC MQTT IoT Listener application, version {eccmqtt_iot_version}, {eccmqtt_iot_date}...")
    sys.exit(0)

# Set up logging...change as appropriate based on implementation location and logging level
log_file_path = args.log_file_path
# log_file_path = None  # To direct logging to console instead of file

logging.basicConfig(
    filename=log_file_path,
    level=logging.DEBUG,
    format="%(asctime)s:%(levelname)s: %(name)s: line: %(lineno)d %(message)s"
)
logger = logging.getLogger('MQTTIoT')

# Location of database file...change as appropriate based on implementation location
ECCMQTTIoT_database = args.database_file_path

# Location of the default MQTT credentials if not otherwise provided
ECCMQTTIoT_mqtt_credentials = args.credentials_file_path

# Default MQTT broker
ECCMQTTIoT_broker = args.mqtt_broker

# Default connectivity check timer
ECCMQTTIoT_conn_timer = args.timer_check

# Location of the default GMail credentials for notifications if not otherwise provided
ECCMQTTIoT_gmail_credentials = args.gmail_credentials_file_path

# Location of the default GMail credentials for notifications if not otherwise provided
ECCMQTTIoT_last_notice = args.last_notice_file_path

# Default last notification silence time, in minutes (default is 24 hours / 1 day)
ECCMQTTIoT_notice_silence = args.last_notice_silence_time

# Define database fields
field_names = ['recordWrittenUTC',
               'dewPointF',
               'temperatureF',
               'relHumidityPercent',
               'battVoltage',
               'battPercent',
               'apRSSI',
               'sensorName']


def main():
    # Global to define the database archival threshold
    global max_db_file_size_bytes
    # Counter for received messages
    global recvd_message_cnt
    # Counter for database records written
    global database_records_written
    # Flag to indicate a received message on the channel during the timer
    global received_msg
    received_msg = False

    max_db_file_size_bytes = 1073741824  # Maximum database file size in bytes before archival; 1GB at 4K cluster size
    recvd_message_cnt = 0
    database_records_written = 0

    now = datetime.now()
    date_now_str = now.strftime("%Y-%m-%d %H:%M:%S")
    print(F"*** Initiating ECC MQTT IoT listener, {date_now_str} ***")
    logger.info(F"*** Initiating ECC MQTT IoT listener, {date_now_str} ***")
    print(F"*** ECC ECC MQTT IoT listener version {eccmqtt_iot_version}, {eccmqtt_iot_date} ***")
    logger.info(F"*** ECC ECC MQTT IoT listener version {eccmqtt_iot_version}, {eccmqtt_iot_date} ***")

    logger.info(F"Log filename:               {args.log_file_path}")
    logger.info(F"Database filename:          {args.database_file_path}")
    logger.info(F"MQTT credentials filename:  {args.credentials_file_path}")
    logger.info(F"MQTT broker address:        {args.mqtt_broker}")
    logger.info(F"Connectivity timer:         {args.timer_check}")
    logger.info(F"GMail credentials filename: {args.gmail_credentials_file_path}")
    logger.info(F"Notice silence time:        {args.last_notice_silence_time}")

    # Before connecting to the MQTT broker, check the existing database size (if it exists).  If
    # the size exceeds the designated threshold, archive it so a new database will be created.
    check_database_size()

    # Get the MQTT credentials from the specified location...
    mqtt_user, mqtt_pass = get_credentials()

    # Instantiate the MQTT client
    mqttc = mqtt.Client()

    # Instantiate the connectivity check timer and start it
    # The timer argument is passed in minutes; we need to convert this to seconds
    # After debugging, replace with a call to connectivity_check
    # Note that the arguments parameter for the timer must be a list
    timer = Timer(ECCMQTTIoT_conn_timer * 60, connectivity_check, args=[mqttc])
    timer.start()

    # Enable MQTT logging (not needed; all important messages are logged except PINGREQ / PINGRESP
    # mqttc.enable_logger(logger=logger)

    # Register the exit handler
    atexit.register(cleanup_mqtt, mqttc)

    # Set up callbacks
    mqttc.on_message = on_message
    mqttc.on_connect = on_connect
    mqttc.on_disconnect = on_disconnect
    mqttc.on_subscribe = on_subscribe
    mqttc.on_log = on_log

    # Set username and password to use for the connection to the broker, if required
    # Following for testing only...change for production.
    mqttc.username_pw_set(mqtt_user, password=mqtt_pass)

    # Assume we're running on the local host where the MQTT broker is running
    mqttc.connect(ECCMQTTIoT_broker, 1883, 60)

    # Subscribe to the ECC temp/humidity sensor channel; moved to on_connect callback
    # mqttc.subscribe("ECCTempHum", 0)

    # Loop forever, keeping the connection alive and waiting for messaged published to the channel
    try:
        mqttc.loop_start()

        while True:
            time.sleep(.1)

    except (KeyboardInterrupt, SystemExit):
        print(F"Ctrl-C interrupt!")
        return


def on_connect(mqttc, obj, flags, rc):
    if rc == 0:
        logger.info(F"Connected to broker...rc: {mqtt.connack_string(rc)}")
        print(F"Connected to broker...rc: {mqtt.connack_string(rc)}")

        try:
            # Subscribe to the ECC temp/humidity sensor channel
            sub_rc = mqttc.subscribe("ECCTempHum", qos=0)

            if sub_rc[0] != 0:
                logger.info(F"Error occurred while subscribing to channel..."
                            F"rc: {str(sub_rc[0])}")
                print(F"Error occurred while subscribing to channel..."
                      F"rc: {str(sub_rc[0])}")
                sys.exit(1)

        except Exception as e:
            logger.info(F"Error occurred while subscribing to channel..."
                        F"error: {str(e)}")
            print(F"Error occurred while subscribing to channel..."
                  F"error: {str(e)}")
            sys.exit(1)

    else:
        logger.error(F"Error connecting to broker, return code: {mqtt.connack_string(rc)}")
        print(F"Error connecting to broker, return code:  {mqtt.connack_string(rc)}")
        sys.exit(1)


def on_disconnect(mqttc, obj, msg):
    logger.info(F"Lost connection to broker...")
    print(F"Lost connection to broker...")


def on_message(mqttc, obj, msg):
    global recvd_message_cnt
    global database_records_written
    global received_msg

    # Set a flag to indicate we've received a message during the timer execution
    received_msg = True

    msg_time = datetime.utcnow()
    logger.debug(F"Topic: {msg.topic}  QoS: {str(msg.qos)},  {str(msg.payload)}")
    print(F"Topic: {msg.topic}  QoS: {str(msg.qos)},  {str(msg.payload)}")

    # After every 1000 records, check the database size and if it exceeds the designated
    # threshold, archive it.
    if (recvd_message_cnt % 1000) == 0:
        check_database_size()

    recvd_message_cnt += 1

    # Received message on subscribed channel...add it to the database.
    add_db_record(msg.topic, msg.payload, msg_time)
    # If successful in adding record to database, increment the counter
    if add_db_record:
        database_records_written += 1

    # Check the database records written count; every 100 records, output a message
    if ((database_records_written % 100) == 0) and (database_records_written != 0):
        print(F"{database_records_written} records added to database")
        logger.info(F"{database_records_written} records added to database")


def on_subscribe(mqttc, obj, mid, granted_qos):
    logger.info(F"Subscribed: {str(mid)}  QoS: {str(granted_qos)}")
    print(F"Subscribed: {str(mid)}  QoS: {str(granted_qos)}")


def on_log(mqttc, obj, level, string):
    print(string)
    # logger.debug(string)


def connectivity_check(mqttc):
    """
        This routine will check to see if a message was published to the subscribed channel
        during the specified timer interval, and if not, will restart the script.
            Written by DK Fowler ... 08-Aug-2020

    :param mqttc:           MQTT client object
    :return:                none
    """

    global received_msg

    now = datetime.now()
    date_now_str = now.strftime("%Y-%m-%d %H:%M:%S")
    print(F"*** {date_now_str} *** timer expired")
    # logger.debug(F"*** {date_now_str} *** timer expired")
    if not received_msg:
        # An MQTT message was not received during the timer execution, so alert and
        # re-execute the script
        print(F"Message not received for {ECCMQTTIoT_conn_timer} minutes...")
        logger.info(F"Message not received for {ECCMQTTIoT_conn_timer} minutes..")
        print(F"...restarting ECC MQTT IoT listener...")
        logger.info(F"...restarting ECC MQTT IoT listener...")
        print_exit_summary(mqttc)

        # Check the date/time the last notification was sent; if it was greater than the
        # specified "mute" period, send an email notification
        last_notice_datetime = get_last_notice()
        last_notice_time_delta = datetime.now() - last_notice_datetime
        last_notice_age_min = last_notice_time_delta.total_seconds() / 60

        # If we're not in the specified "mute" period for notifications, send an alert of the
        # restart via email
        if last_notice_age_min > ECCMQTTIoT_notice_silence:
            # Generate an email alert prior to re-executing
            # Get the originator email credentials from the specified location...
            mail_origin, mail_pass = get_email_credentials()

            mail_subject = 'ECC IoT Listener Restart'
            mail_from = 'ECC IoT Listener'
            # For ECC...
            mail_to = 'temp-sensors@epiphanycatholicchurch.org'
            mail_body = f'\nNo MQTT message has been received within {ECCMQTTIoT_conn_timer} ' \
                        f'minutes.\nECC IoT Listener has been restarted.\n '

            gmail_send_status = send_mail(mail_origin,
                                          mail_pass,
                                          mail_subject,
                                          mail_from,
                                          mail_to,
                                          mail_body)

            if gmail_send_status:
                # save the datetime of the last notification
                save_last_notice(datetime.now())

        # execute the script again; the __file__ variable contains the name of the
        # currently executing script
        with open(__file__, 'rb') as f:
            # compile this script into a bytecode object, and associate the filename
            # with the code object making debugging a bit easier
            code = compile(f.read(), __file__, 'exec')
            # exec(code, globals(), locals())
            exec(code)
            # should not reach here...
            sys.exit(0)
    else:
        print(F"Message WAS received during timer execution...")

    # Reset the flag indicating a message has been received during the timer execution
    received_msg = False

    # Restart the timer
    timer = Timer(ECCMQTTIoT_conn_timer * 60, connectivity_check, args=[mqttc])
    timer.start()


def add_db_record(topic, mqtt_msg, msg_time):
    """
        This routine will attempt to add a new database record to the specified SQLite
        database by parsing the MQTT message payload received.  It will first check for
        the existence of the database itself and create it if it does not, as well as
        the table used for the data.
            Written by DK Fowler ... 09-Jun-2020

    :param topic:           MQTT topic to which the message containing data is published
    :param mqtt_msg:        MQTT message payload (unparsed)
    :param msg_time:        time the message was received by the listener in UTC
    :return:                True if successful in adding record, else False
    """

    # Attempt to get a connection to the db.  If it doesn't exist, we create it.
    conn = create_connection(ECCMQTTIoT_database)

    # Check to ensure we have a valid db connection...if not, abort
    if conn is None:
        logger.error("No connection established to database...aborting.")
        print(F"No connection established to database...aborting.")
        sys.exit(1)

    db_table = 'ECCTempHum'

    # Construct the SQL create-table statement...
    create_table_sql_str, table_fields_dict = construct_create_table_sql(db_table,
                                                                         field_names)
    # Have a valid db connection; see if the db exists
    if check_if_table_exists(conn, db_table, ECCMQTTIoT_database):
        logger.debug(F"Table {db_table} already exists...continuing processing...")
    else:
        print(F"Table {db_table} does not exist...creating...")
        logger.info(F"Table {db_table} does not exist...creating...")
        create_tbl_status = create_table_from_string(conn, db_table, create_table_sql_str)
        if not create_tbl_status:
            logger.error(F"Error creating table {db_table}...aborting...")
            print(F"Error creating table {db_table}...aborting...")
            sys.exit(1)

    # Sample message payload looks like:
    # field1=47.10&field2=73.45&field3=39.17&field4=3.41&field5=93.53&field6=-67&field7=ECCTH01
    # First, split the message by the '&' delimiter between fields
    #   *** Note that the raw message is a byte object, so we must convert it first to a string
    msg_fields = (mqtt_msg.decode("utf-8")).split('&')

    # We should now have a list of all the fields in format of 'field=value'; break this to
    # get the values in a separate list

    field_values = []
    for msg in msg_fields:
        msg_value = msg.split('=')
        field_values.append(msg_value[1])  # field value should be in second element in list

    insert_record_status = create_database_record(conn,
                                                  db_table,
                                                  table_fields_dict,
                                                  field_values,
                                                  msg_time)

    # Close the database connection if it is open
    if conn:
        conn.close()

    if insert_record_status:
        return True
    else:
        return False


def create_connection(db_file):
    """ This routine will create a database connection to the SQLite database specified by the db_file
        (From SQLite Tutorial at sqlitetutorial.net)
                Modified by DK Fowler ... 09-Jun-2020
    :param  db_file:    database file
    :return:            Connection object or None
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
                Modified by DK Fowler ... 09-Jun--2020
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


def check_if_table_exists(conn, ECCMQTTIoTTable, ECCMQTTIoTDatabase):
    """
        This routine will check for the existence of the table passed in ECCMQTTIoTTable in the
        database file ECCMQTTIoTDatabase.  If it exists, the function will return true; otherwise
        it will return false.
            Written by DK Fowler ... 09-Jun-2020
    :param conn:                    database connection (may exist already, or be set to None
    :param ECCMQTTIoTTable:         table name to check for existence
    :param ECCMQTTIoTDatabase:      database file to check for table existence
    :return:                        True if table exists; otherwise, False
    """
    if conn is None:
        try:
            conn = create_connection(ECCMQTTIoTDatabase)
        except Error:
            logger.error(
                F"Error connecting to database {ECCMQTTIoTDatabase} to check for table "
                F"{ECCMQTTIoTTable} existence.")
            print(
                F"Error connecting to database {ECCMQTTIoTDatabase} to check for table "
                F"{ECCMQTTIoTTable} existence.")
            return False

    # Check the SQLite master table for the table name
    c = conn.cursor()
    find_table_query = "SELECT count(name) FROM sqlite_master WHERE type='table' AND name=? "
    logger.debug(F"Find table query string:  {find_table_query}")
    c.execute(find_table_query, (ECCMQTTIoTTable,))

    # Now check the number returned; if not 1, then table doesn't exist
    found_flag = False
    if c.fetchone()[0] == 1:
        logger.debug(f"Table '{ECCMQTTIoTTable}' found...")
        found_flag = True
    else:
        logger.info(f"Table '{ECCMQTTIoTTable}' not found...")

    # commit the changes (none here)
    conn.commit()

    return found_flag


def create_table_from_string(conn, db_table, create_table_sql_str):
    """
        This routine will attempt to create a database table given the passed database connection,
        table name, and SQL creation string.  If successful, it will also create secondary
        indicies.
            Written by DK Fowler ... 09-Jun-2020
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
        sql_create_mqttiot_sec_index1 = "CREATE INDEX " + "sensor_idx ON " + \
                                        db_table + "(sensorName);"
        table_exists = check_if_table_exists(conn, db_table, ECCMQTTIoT_database)
        if not table_exists:
            table_success = create_table(conn, create_table_sql_str)
            if not table_success:
                logger.debug(F"Error occurred attempting to create table {db_table}...aborting")
                sys.exit(1)
            # Create secondary indicies
            try:
                indicies_success = conn.execute(sql_create_mqttiot_sec_index1)
                # indicies_success = conn.execute(sql_create_mqttiot_sec_index2)
            except sqlite3.Error as e:
                logger.error(F"Error creating secondary indicies for table {db_table}, {e}")
                print(F"Error creating secondary indicies for table {db_table}, {e}")
        else:
            logger.debug(F"Database table {db_table} exists...")
            table_success = True  # Set the success flags, as table and indicies already exist
            indicies_success = True
    else:
        logger.error("Error...the MQTT IoT database connection did not exist when attempting to create "
                     F"table {db_table}")
        logger.error(F"...aborting")
        print("Error...the MQTT IoT database connection did not exist when attempting to create "
              F"table {db_table}")
        print(F"...aborting")
        sys.exit(1)

    if table_success and indicies_success:
        return True
    else:
        return False


def construct_create_table_sql(table_name, field_names):
    """
        This routine will construct a SQLite CREATE TABLE SQL statement from the passed parameters.
        This can be used in subsequent calls to the SQLite Python API to create a new database
        table for the passed table name.

        The field names are defined as a global list.

        In addition to returning a string containing the SQL statement to create the table, it will
        also return a dictionary containing field name and datatype for subsequent use in the
        application.
                Written by DK Fowler ... 10-Jun-2020

    :param table_name:          Database table to create (if it doesn't exist)
    :param field_names:         List containing fields for creation of table
    :return datatype_dict:      Dictionary containing field name as key with datatype returned
    :return: SQL_create_str:    SQL string to create the table
    """

    # Create datatype list
    field_sql_types = []
    field_sql_types.insert(0, 'TEXT')  # date/time message received, in UTC
    for i in range(1, 6):
        field_sql_types.append('REAL')  # values for dewpoint, temp, hum, batt voltage / percent
    field_sql_types.append('INTEGER')  # AP RSSI
    field_sql_types.append('TEXT')  # sensor

    # Create a SQLite datatype dictionary, with the key being field name from the field_name list passed
    # and the value being the datatype defined in the field_sql_types list
    datatype_dict = {}
    datatype_dict = {field_name: field_sql_types[idx] for idx, field_name in enumerate(field_names)}

    logger.debug(F"SQLite datatype dictionary created:  {datatype_dict}")

    # Construct SQL table create string
    SQL_create_str = "CREATE TABLE IF NOT EXISTS " + table_name + " ("

    # Loop through data fields...adding to the SQL CREATE statement with field name, datatype
    for field_idx in range(0, len(field_names)):
        SQL_create_str += field_names[field_idx] + " "
        SQL_create_str += field_sql_types[field_idx]
        SQL_create_str += ", "

    # Add the primary key and terminate the CREATE string
    SQL_create_str += "PRIMARY KEY (sensorName, recordWrittenUTC) ); "

    logger.debug(F"SQL {table_name} table create string: ")
    logger.debug(F"...{SQL_create_str}")

    return SQL_create_str, datatype_dict


def construct_insert_table_sql(db_table, db_fields):
    """
        This routine will construct a SQLite INSERT statement to be used in an attempt to
        write a new record to the table passed.
            Written by DK Fowler ... 10-Jun-2020
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


def create_database_record(conn, db_table, values_dict, field_values, msg_time):
    """
        This routine will attempt to write a record to the passed table with the passed
        list of record names / values.  If successful, the routine will return True, else False.
            Written by DK Fowler ... 10-Jun-2020
    :param conn:            database connection (may exist already, or be set to None)
    :param db_table:        table name to which a record write is attempted
    :param values_dict:     dictionary of field names: datatypes for the record
    :param field_values:    list of field values for the record
    :param msg_time:        datetime when MQTT message received, in UTC
    :return:                True if table created successfully; otherwise, False
    """

    # First create a SQL string for INSERTing the record into the passed table
    sql_insert = construct_insert_table_sql(db_table, values_dict.keys())

    # Get the current date/time in UTC for the record INSERT
    recordWrittenUTC = msg_time

    logger.debug(F"......date written set to: {datetime.strftime(recordWrittenUTC, '%Y-%m-%d %H:%M:%S.%f')}")
    cur = conn.cursor()  # Get a cursor for the db connection
    # Make sure we have a database connection
    if conn is not None:
        logger.debug(F"Attempting record insert...table:  {db_table}")
        try:
            val_list = []
            date_written_str = datetime.strftime(recordWrittenUTC, "%Y-%m-%d %H:%M:%S.%f")
            val_list.insert(0, date_written_str)
            idx = 1
            for db_val in field_values:
                val_list.insert(idx, db_val)
                idx += 1

            # print(F"Values used in INSERT:  {val_list}")
            logger.debug(F"...field values {val_list}")
            cur.execute(sql_insert, val_list)
            logger.debug(F"Record written for sensor {val_list[len(val_list) - 1]}, "
                         F"date: {recordWrittenUTC}, table: {db_table}")
        except sqlite3.Error as e:
            cur.close()
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
            return False
        except Exception as e:
            logger.error(F"Exception occurred during INSERT:  {e}")
            logger.error(F"...SQL INSERT statement:  {sql_insert}")
            logger.error(F"...Values used in INSERT:  {val_list}")
            print(F"Exception occurred during INSERT:  {e}")
            print(F"...SQL INSERT statement:  {sql_insert}")
            print(F"...Values used in INSERT:  {val_list}")
            cur.close()
            return False
    else:
        logger.error(F"No database connection detected while attempting to write new record, table {db_table}")
        print(F"No database connection detected while attempting to write new record, table {db_table}")
        sys.exit(1)

    conn.commit()
    cur.close()
    return True


def get_credentials():
    """
        This routine will attempt to read the MQTT username and password used to connect
        to the broker from the specified external file.
                Written by DK Fowler ... 10-Jun-2020
        :return username:    ECC MQTT broker username read from specified external file
        :return password:    ECC MQTT broker password read from specified external file

    """
    try:
        with open(ECCMQTTIoT_mqtt_credentials, 'r', encoding='utf-8') as f:
            try:
                # Credential file should contain 1 line, in the format of
                # username, password
                creds_line = f.readline()

                # Now parse the line read for the username, password
                creds = creds_line.split(',')
                return creds
            except Exception as e:
                logger.error(F"Error occurred during attempt to read ECC MQTT credentials from file...")
                logger.error(F"...error:  {e}")
                logger.error(F"...aborting...")
                print(F"Error occurred during attempt to read ECC MQTT credentials from file...")
                print(F"...error:  {e}")
                print(F"...aborting...")
                sys.exit(1)
    except Exception as e:
        logger.error(F"Error during attempt to open ECC MQTT credentials file...{e}")
        logger.error(F"...aborting...")
        print(F"Error during attempt to open ECC MQTT credentials file...{e}")
        print(F"...aborting...")
        sys.exit(1)


def get_email_credentials():
    """
        This routine will attempt to read the email originator username and password
        from the specified external file.
                Written by DK Fowler ... 13-Aug-2020
        :return username:    GMail originator username read from specified external file
        :return password:    GMail originator password read from specified external file

    """
    try:
        with open(ECCMQTTIoT_gmail_credentials, 'r', encoding='utf-8') as f:
            try:
                # Credential file should contain 1 line, in the format of
                # username, password
                creds_line = f.readline()

                # Now parse the line read for the username, password
                creds = creds_line.split(',')
                return creds
            except Exception as e:
                logger.error(F"Error occurred during attempt to read ECC GMail credentials from file...")
                logger.error(F"...error:  {e}")
                logger.error(F"...aborting...")
                print(F"Error occurred during attempt to read ECC GMail credentials from file...")
                print(F"...error:  {e}")
                print(F"...aborting...")
                sys.exit(1)
    except Exception as e:
        logger.error(F"Error during attempt to open ECC GMail credentials file...{e}")
        logger.error(F"...aborting...")
        print(F"Error during attempt to open ECC GMail credentials file...{e}")
        print(F"...aborting...")
        sys.exit(1)


def check_database_size():
    """
    This routine will check the existing database size and compare it against the designated
    threshold size.  If it exceeds it, a routine to archive the exiting database will be called.
            Written by DK Fowler ... 13-Jun-2020
    """

    global max_db_file_size_bytes

    # Check if the database file currently exists; if not, simply return without further
    # checking, as the database will be created at first connection if it doesn't exist
    #       Added by DK Fowler ... 09-Aug-2020
    db_exists = os.path.exists(ECCMQTTIoT_database)
    if not db_exists:
        return

    db_size_bytes = os.path.getsize(ECCMQTTIoT_database)

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
                Written by DK Fowler ... 24-Feb-2020
    """

    logger.info(F"Beginning database archival...")
    print(F"Beginning database archival...")

    # Get the creation / last modified date/time of the existing file for use in constructing the archival file name...
    db_modified_time = os.path.getmtime(ECCMQTTIoT_database)
    db_create_time = os.path.getctime(ECCMQTTIoT_database)
    # Convert timestamps to strings in proper form
    db_create_string = datetime.fromtimestamp(db_create_time).strftime('%Y%m%d%H%M')
    db_modified_string = datetime.fromtimestamp(db_modified_time).strftime('%Y%m%d%H%M')
    # Get the filename/ext string of the existing database
    db_basename = os.path.basename(ECCMQTTIoT_database)
    # Split the filename into name/extension components
    fn = os.path.splitext(db_basename)
    db_filename = fn[0]
    db_ext = fn[1]
    # Construct the new archival filename
    archival_db_name = db_filename + "-" + db_create_string + "-" + db_modified_string + db_ext
    print(F"Archival database name:  {archival_db_name}.")

    # Attempt to rename the existing database
    try:
        os.rename(ECCMQTTIoT_database, archival_db_name)
        logger.info(F"Renamed database to: {archival_db_name}.")
        print(F"Renamed database to:  {archival_db_name}.")
    except Error as e:
        logger.error(F"Error attempting to archive (rename) database file: {e}...")
        logger.error(F"...original database name:  {ECCMQTTIoT_database}")
        logger.error(F"...archival database name:  {archival_db_name}")
        print(F"Error attempting to archive (rename) database file: {e}...")
        print(F"...original database name:  {ECCMQTTIoT_database}")
        print(F"...archival database name:  {archival_db_name}")


def cleanup_mqtt(mqttc):
    """
        This is the exit handler for the application, to be called in order to cleanup
        the mqtt client by properly stopping the listening loop.  It will also print a
        summary message for the total number of records written to the database.
                Written by DK Fowler ... 29-Jun-2020
    :param mqttc:   Paho MQTT client object
    :return:        None
    """

    print_exit_summary(mqttc)

    sys.exit(0)


def print_exit_summary(mqttc):
    """
        This routine prints a summary message for the total number of records written to
        the database, and stops the MQTT client loop in preparation for exiting.
                Written by DK Fowler ... 08-Aug-2020
    :param mqttc:   Paho MQTT client object
    :return:        None
    """

    # global end_time
    global recvd_message_cnt
    global database_records_written

    # Stop the mqtt loop, if the mqtt client exists
    if mqttc:
        mqttc.loop_stop()

    print(F"Total MQTT messages received:  {recvd_message_cnt}")
    logger.info(F"Total MQTT messages received:  {recvd_message_cnt}")
    print(F"Total database records written:  {database_records_written}")
    logger.info(F"Total database records written:  {database_records_written}")

    end_time = datetime.now()
    logger.info(f'ECC MQTT IoT Listener total runtime {end_time - start_time}')
    print(f'\nECC MQTT IoT Listener total runtime {end_time - start_time}\n')


def send_mail(mail_origin,
              mail_pass,
              mail_subject,
              mail_from,
              mail_to,
              mail_body):
    """
        This routine will send an e-mail message using the passed parameters.
                Written by DK Fowler ... 12-Aug-2020
    :param mail_origin      e-mail address of the originator
    :param mail_pass        e-mail password for the originator account
    :param mail_subject     e-mail subject string
    :param mail_from        e-mail from string, preceding 'From' e-mail address
    :param mail_to          e-mail 'To' destination address
    :param mail_body        e-mail message body
    :return:                True if successful, else False
    """

    mail_time = datetime.now()
    mail_time_str = mail_time.strftime("%a, %d %b %Y %H:%M:%S")
    # Get timezone offset
    # Append to date/time string; timezone must be specified as a 4-digit value, with leading
    # zeroes, such as '-0500' for EDT.
    mail_time_str = mail_time_str + " -" + f'{(time.timezone / 3600):02.0f}00'

    try:
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465,
                                  local_hostname='epiphanycatholicchurch.org')
        # use the following for ECC...
        # server = smtplib.SMTP_SSL('smtp-relay.gmail.com', 465)
    except smtplib.SMTPException as e:
        print(F"SMTP error occurred during attempt to connect to GMAIL, error:  {e}")
        logger.error(F"SMTP error occurred during attempt to connect to GMAIL, error:  {e}")
        return False
    except Exception as e:
        print(F"Error occurred during attempt to connect to GMAIL, error:  {e}")
        logger.error(F"Error occurred during attempt to connect to GMAIL, error:  {e}")
        return False

    # Instantiate the email message object
    msg = EmailMessage()

    # Set the message contents
    msg['Date'] = mail_time_str
    msg['Subject'] = mail_subject
    msg['From'] = mail_from + ' <' + mail_origin + '>'
    msg['To'] = 'ECC IoT Tech Group <' + mail_to + '>'
    msg.set_content(mail_body)

    try:
        server.login(mail_origin, mail_pass)
    except smtplib.SMTPException as e:
        print(F"SMTP error occurred during attempt to login to GMAIL account, error: {e}")
        logger.error(F"SMTP error occurred during attempt to login to GMAIL account, error: {e}")
        server.quit()
        return False
    except Exception as e:
        print(F"Error occurred during attempt to login to GMAIL account, error: {e}")
        logger.error(F"Error occurred during attempt to login to GMAIL account, error: {e}")
        server.quit()
        return False
    try:
        server.send_message(msg)
        print(F"Notification message successfully sent!\n\n")
        logger.info(F"Notification message successfully sent!")
    except smtplib.SMTPException as e:
        print(F"SMTP error occurred during attempt to send GMAIL message, error:  {e}")
        logger.error(F"SMTP error occurred during attempt to send GMAIL message, error:  {e}")
        return False
    except Exception as e:
        print(F"Error occurred during attempt to send GMAIL message, error:  {e}")
        logger.error(F"Error occurred during attempt to send GMAIL message, error:  {e}")
        return False

    server.quit()
    return True


def save_last_notice(last_notice_datetime):
    """
    This routine will save the date/time of the last notification issued via email to the
    file specified.  It is used to limit new notices within the timeframe specified in
    order to avoid unnecessary / frequent messages that would otherwise be generated.
            Written by DK Fowler ... 13-Aug-2020
    :param:     last_notice_datetime    datetime of last notice generated
    :return:
    """

    try:
        # save the date/time of the last notification as a binary datetime object using
        # pickle
        with open(ECCMQTTIoT_last_notice, 'wb') as ln:
            pickle.Pickler(ln).dump(last_notice_datetime)
    except Exception as e:
        print(F"Error occurred in attempting to save last notification date/time, {e}")
        logger.error(F"Error occurred in attempting to save last notification date/time, {e}")


def get_last_notice():
    """
    This routine will attempt to retrieve the last datetime a notice was sent from the specified
    file.
    :return: last_notice_datetime   Date/time last notice was sent
    """

    # Check if the saved-notification file exists; if not, return 0
    if not os.path.exists(ECCMQTTIoT_last_notice):
        logger.debug(F"Last notification file not found; assuming no prior notices sent.")
        last_notice_datetime = datetime.min
    else:
        try:
            # read the last date/time of notification as a binary datetime object using
            # pickle
            with open(ECCMQTTIoT_last_notice, 'rb') as ln:
                last_notice_datetime = pickle.Unpickler(ln).load()
        except Exception as e:
            print(F"Error occurred in attempting to retrieve last notification date/time, {e}")
            logger.error(F"Error occurred in attempting to retrieve last notification date/time, {e}")

    return last_notice_datetime


if __name__ == '__main__':
    start_time = datetime.now()
    main()
