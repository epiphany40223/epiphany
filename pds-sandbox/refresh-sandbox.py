# Make a new sandbox.

import os
import re
import sys
import subprocess

src = r'\\media-o3020\pdschurch\Data'
dest = r'c:\Epiphany\PDSChurchSandbox\Data'

def doit(msg, cmd, shell=False):
    print(f"=== {msg}")
    print(cmd)
    subprocess.run(cmd, shell=shell)

doit('Removing old sandbox',
     ['rmdir', dest, '/s', '/q'], shell=True)
doit("Copying new sandbox",
     ['xcopy', src, dest, '/e', '/i', '/z'], shell=True)

# Set the color scheme in the sandbox to be different
print('=== Changing color scheme to pumpkin')
file = f"{dest}/PDS.ini"
with open(file) as fp:
    lines = fp.readlines()

all = re.sub(r'ColorScheme=.+\.clr', 'ColorScheme=Pumpkin.clr', ''.join(lines))
with open(file, "w") as fp:
    fp.write(all)

print("=== Sandbox refreshed!")
input("=== Hit ENTER to exit: ")
