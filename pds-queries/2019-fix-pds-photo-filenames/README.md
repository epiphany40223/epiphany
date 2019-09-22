# Fixing PDS picture files

In 2019, we moved the Z drive from \\fileengine to Google Shared
Drives (i.e., G:\Shared Drives\ECC Public(Z)\PICTURES).

Additionally, we consolidated a few picture folders that were in
various places around Z into a single folder structure in the new
Google Shared drive (all under the PICTURES folder, mentioned above).

This resulted in making all the filenames in PDS -- for both Members
and Families -- be stale.

The python code in this directory is definitely not the prettiest code
I've ever written, but it was for one-time use, and it was deemed
"good enough" (e.g., the Member and Family code could certainly have
been combined, and the whole Windows/Mac filesystem translation stuff
could have been done much better / simpler).

The idea was generally this:

* For each Member / Family:
  * If they have a Picture file
    * Check to see if that file actually exists in the new Google
      Shared Drive (i.e., run this on a machine that has the Google
      Shared Drive mounted.  I ran this on a Mac, which made
      things... complicated, because PDS wants Windows-style
      filenames.)
    * If the file exists, save an entry with the MID/FID (and name,
      just for good measure) and the new Windows filename (based on
      G:\Shared Drives\...etc.).

* When done, output a "to-fix.csv" file with rows containing:
  * The MID/FID
  * The name
  * The new filename

Use the PDS "Import..." functionality to import this CSV for Members / Families.  Make sure to select:

* Use Advanced Features
* Update families/members only -- do not create
* Use the MID/FID as the ID
* Then go through and select the MID/FID column as the member/family index
* And select the filename column as the picture filename

Do a pre-import check to make sure it works (it should!).

Then do the import.

The Python also emitted "skipped.csv" to list all the filenames that
it didn't fix.  There was only a dozen or two of these; I went through
and found the ones that had relevant filenames in the Google Shared
Drive and manually updated them in the PDS UI.
