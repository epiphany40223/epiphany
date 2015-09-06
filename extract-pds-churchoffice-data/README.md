This script simple extracts all (well, most) of the data from PDS
Church Office using the pxlib and pxview tools (see
https://github.com/jsquyres/pxlib-and-pxview) and dumps the resulting
data in a MySQL database.

The goal is simply to allow third-party tools read-only access to the
PDS Church Office data.

It's a simple perl script that uses the pxview executable to dump data
from the PDS Church Office "Data" directory into a MySQL database.
What you do with the data from there is up to you.  :-)
