Trivial internet connectivity checker.

It is intended to be launched as a systemd service upon WSL instance
startup (i.e., it assumes WSL starts systemd -- see the wsl/wsl.conf
file).

The ecc-internet-connectivity-checker.service file is a systemd
startup service file that launches the internet-connectivity-checker
upon WSL instance start.  This script runs indefinitely (it sleeps
most of the time).

1. Place a sym link in /etc/systemd/system to
   ecc-internet-connectivity-checker.service
2. Edit the file to reflect the correct directory where the
   internet-connectivity-checker.py is located
3. sudo systemctl enable ecc-internet-connectivity-checker.service

That's it.

You can test the systemd service by shutting down WSL (from a cmd
window):

  wsl --shutdown

And then starting a new WSL instance.  Upon boot, check to see if the
internet-connectivity-checker.py is running.  If it is, then this
systemd service worked properly.

You can also run the following to check its status:

  sudo systemctl status ecc-internet-connectivity-checker

It should show an either obviously happy or sad message about the
status of the service.
