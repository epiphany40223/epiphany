This is a quick-n-dirty way to process the 2021 pictorial directory
PDS Family pictures.

It takes the input tab-separated-values file (!) from the photo
vendor, parses it (the format is specific to this vendor -- it's not
any kind of standard format), and extracts out the values that it
wants.  The vendor provided first and last name.  If we can match
exactly one Member first and last name somewhere, then we found the
corresponding Family.  If not, do a few heuristics to see if we can
find a corresponding Family.

The output is a CSV of FID/envelope ID + Family photo location in a
specific location in the "ECC Public (Z)" Google Shared drive, as
mapped to a G: drive.  This CSV was imported into PDS.

Again, this was a somewhat quick-n-dirty import.  The exact code will
likely not be useful in future efforts, but the technique may be
helpful someday.  So we're putting it in the repo in case someone
finds it helpful down the line.
