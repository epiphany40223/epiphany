# Setting up a Windows Services for Linux instance

On a Windows machine, create a WSL instance like this:

```
wsl --install --d Ubuntu
```

* Create a user named `coeadmin`
* Assign a reasonable password

Then download the install script and run it:

```
wget https://raw.githubusercontent.com/epiphany40223/epiphany/main/media/linux/wsl/setup-wsl.sh
chmod +x setup-wsl.sh
./setup-wsl.sh
```

In the beginning, it will interactively prompt for several things.
Once it starts Apt updating/installing a whole pile of packages, it
has stopped asking for interactive input and you can walk away (it
will take a few minutes to run).

Once it has finished, the WSL instance will be terminated and you'll
need to re-start it.  Then there's a few more manual steps to run,
which are shown at the bottom of the execution output of this script.
