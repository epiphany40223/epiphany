# Make a new sandbox.
#
# This script is from Epiphany's github repo in the pds-sandbox
# directory.

import os
import re
import sys
import subprocess

src = r'\\media-o3020\pdschurch\Data'
dest = r'c:\Epiphany\PDSChurchSandbox\Data'

def doit(msg, cmd, shell=False):
    print(f"=== {msg}")
    print(cmd)
    ret = subprocess.run(cmd, shell=shell)
    return ret

_ = doit('Removing old sandbox',
           ['rmdir', dest, '/s', '/q'], shell=True)

# Exclude copying lock files, because those may be opened by other
# network users and therefore xcopy would error if it tried to
# read/copy them.
filename = 'exclude_files.txt'
with open(filename, 'w') as fp:
    fp.write('.lck\n')

out = doit("Copying new sandbox",
           ['xcopy', src, dest,
            '/e', '/i', '/z', '/exclude:'+filename], shell=True)

_ = doit("Removing temp excludes file",
         ['del', filename], shell=True)

if out.returncode == 0:
    # Set the color scheme in the sandbox to be different
    print('=== Changing color scheme to pumpkin')
    file = f"{dest}/PDS.ini"
    with open(file) as fp:
        lines = fp.readlines()

    all = re.sub(r'ColorScheme=.+\.clr', 'ColorScheme=Pumpkin.clr', ''.join(lines))
    with open(file, "w") as fp:
        fp.write(all)

if out.returncode == 0:
    print("=== Sandbox refreshed!")
else:
    print("=== Something went wrong -- see error message above")
    print("=== Sandbox was not fully rerfreshed")

input("=== Hit ENTER to exit: ")
