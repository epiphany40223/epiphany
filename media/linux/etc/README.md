We start several Linux services via the Windows Task Manager:

- ssh daemon
- postfix daemon
- cron daemon

These are created by making an entry in the Windows Task Manager:

Trigger: system startup
Actions:
1. Program: C:\Windows\Systems32\wsl.exe
   Arguments: sudo /etc/init.d/cron start
2. Same as #1, but with postfix
3. Same as #1, but with ssh

This means that we must have passwordless sudo for these commands,
and therefore several entries are added to /etc/sudoers (via
editing the file by "sudo visudo" -- don't just replace the file
manually!).

Don't forget to add pinholes in the Windows firewall for ssh and
postfix (TCP/22 and TCP/25, respectively).

We also do other actions in this same Task Manager entry:

1. Remove the export-PDS-data file lock (if it's still there).
   This is just a failsafe.
