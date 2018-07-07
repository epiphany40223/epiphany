#!/usr/bin/env python3

'''

Helper for apps that use PDS databases (that were imported into
SQLite3 databases)

'''

import sqlite3
import os

##############################################################################

def connect(filename):
    if not os.path.exists(filename):
        print("PDS SQLite3 database does not exist: {f}".format(f=filename))
        exit(1)

    conn = sqlite3.connect(filename)
    cur = conn.cursor()

    return cur

##############################################################################

def _get_column_names(cur, name, log):
    # Temporarily set the "sqlite3.Row" row factory so that we can get
    # the column names
    orig = cur.connection.row_factory
    cur.connection.row_factory = sqlite3.Row
    tmp_cur = cur.connection.cursor()

    result = tmp_cur.execute("SELECT * FROM {table} WHERE rowid=1"
                             .format(table=name))
    row = result.fetchone()

    names = row.keys()

    if log:
        log.debug("Table {table} columns: {names}"
                  .format(table=name, names=names))

    # Set the original row factory back
    cur.connection.row_factory = orig

    return names

#-----------------------------------------------------------------------------

def read_table(cur, name, index_column, columns=None, where=None, log=None):
    # Get all the column names
    all_column_names = _get_column_names(cur, name, log)

    # Sanity checks
    if index_column not in all_column_names:
        raise Exception("Index column \"{index}\" is not in table \"{table}\""
                        .format(index=index_column, table=name))

    if columns:
        for col in columns:
            if col not in all_column_names:
                raise Exception("Column \"{col}\" not in table \"{table}\""
                                .format(col=col, table=name))

    # Which columns do we want?
    if not columns:
        columns = all_column_names

    # Make sure that the index column is first
    # First, remove it if it's in the list already
    try:
        columns.remove(index_column)
    except:
        pass
    # Now put it back as the first item
    columns.insert(0, index_column)

    # Form the query string
    query = "SELECT "
    if columns:
        query += ','.join(columns)
        query += ' '
    query += "FROM {table} ".format(table=name)
    if where:
        query += 'WHERE {where}'.format(where=where)

    if log:
        log.debug("SQL: {query}".format(query=query))

    # Run the query
    table = dict()
    results = cur.execute(query)
    for result in results.fetchall():
        row = dict()
        for i, col in enumerate(columns):
            row[col] = result[i]

        # We know that the 0th item is the index column
        table[result[0]] = row

    return table
