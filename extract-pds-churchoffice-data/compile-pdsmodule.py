#!/usr/bin/env python3

#
# See compilation instructions in pdsmodule.c
#

import os

from distutils.core import setup, Extension

base_dir = '/Users/jsquyres/bogus'

module1 = Extension('pds',
	            include_dirs = [base_dir + '/include'],
                    libraries = ['px'],
                    library_dirs = [base_dir + '/lib'],
                    sources = ['pdsmodule.c'])

# Sanity check
if (not os.path.exists(base_dir) or
    not os.path.exists(base_dir + '/include/paradox.h')):
    print("Hey Jeff, you need to install pxlib and pxview into $bogus first")
    os.exit(1)

setup (name = 'pds',
       version = '1.0',
       description = 'Trivial PDS module',
       author = 'Jeff Squyres',
       author_email = 'jeff@squyres.com',
       long_description = 'Blah',
       ext_modules = [module1])
