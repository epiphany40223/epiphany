#!/bin/bash

set -euxo pipefail

cd `dirname $0`
LINUX_TOP=`pwd`

#########################################

# Do a bunch of things that require human input relatively near the
# beginning of the script

if test ! -f $HOME/.ssh/id_rsa; then
    ssh-keygen -t rsa
fi

if test "$SHELL" != "/bin/zsh"; then
    # We have to install zsh before we can chsh to it
    sudo apt install zsh -y
    chsh -s /bin/zsh
fi

if test ! -d $HOME/git; then
    mkdir -p $HOME/git
fi

# If we don't have the Epiphany git tree get it
if test ! -d $HOME/git/epiphany; then
    cd $HOME/git
    git clone https://github.com/epiphany40223/epiphany.git
    cd epiphany

    git remote rm origin
    git remote add origin git@github.com:epiphany40223/epiphany.git
    cd media/linux
    LINUX_TOP=`pwd`
fi

cd $HOME
if test ! -d dotfiles; then
    # run-setup installs data-hacks, and it uses Python distutils,
    # which may not be installed by default.  So apt install pip,
    # which includes something that provides the "distutils" module
    # (i.e., good enough to install the data hacks).
    sudo apt update
    sudo apt install python3-pip -y

    git clone jeff@squyres.com:/home/jeff/git/dotfiles.git
    cd dotfiles
    ./run-setup.pl
fi

#########################################

# Update the Ubuntu packages, and install the additional packages that
# we need (this will take several minutes to run)

sudo apt update
sudo apt upgrade -y
sudo apt install -y \
     git \
     autoconf automake libtool gcc make \
     python3-pip virtualenv \
     openssh-server \
     sqlite3

#########################################

# Install the Linux config files that we want

cd $LINUX_TOP/wsl
sudo cp wsl.conf /etc
sudo cp logrotate.d/epiphany /etc/logrotate.d
sudo sed -ie 's/#Port 22/Port 2222/' /etc/ssh/sshd_config

# No need to restart any services to make these configs take effect,
# because at the bottom of this script, we're going to kill this WSL
# instance so that it can be restarted.

#########################################

# Setup Python virtual environments for our apps

setup_venv() {
    dir=$1
    shift
    rm -rf $dir
    virtualenv --python=python3 $dir
    . ./$dir/bin/activate
    set +u
    while test -n "$1"; do
        pushd $1
        pip install -r requirements.txt
        popd

        shift
    done
    set -u
    deactivate
}

cd $LINUX_TOP
# Make one venv that is the union of a bunch of apps
setup_venv py310 calendar-audit calendar-reservations ricoh pds-sqlite3-queries
# Make another venv just for this one app
setup_venv py310 upload-mp3s-to-google-drive

#########################################

# Make logfile and credential directories

mkdir -p $HOME/logfiles/linux
mkdir -p $HOME/logfiles/linux/calendar-audit
mkdir -p $HOME/logfiles/linux/calendar-reservations
mkdir -p $HOME/logfiles/linux/export-pds-to-sqlite
mkdir -p $HOME/logfiles/linux/google-drive-uploader
mkdir -p $HOME/logfiles/linux/gsheet-driven-google-group
mkdir -p $HOME/logfiles/linux/ministry-roster
mkdir -p $HOME/logfiles/linux/ricoh
mkdir -p $HOME/logfiles/linux/sync-google-group
mkdir -p $HOME/logfiles/linux/training-roster
mkdir -p $HOME/logfiles/linux/training-roster
mkdir -p $HOME/logfiles/linux/upload-mp3s-to-google-drive

mkdir -p $HOME/credentials
mkdir -p $HOME/credentials/calendar-audit
mkdir -p $HOME/credentials/calendar-reservations
mkdir -p $HOME/credentials/google-drive-uploader
mkdir -p $HOME/credentials/gsheet-driven-google-group
mkdir -p $HOME/credentials/pds-sqlite3-queries

#########################################

# Setup a Systemd service to start the internet connectivity checker
# when WSL starts this instance.

cd $LINUX_TOP/internet-connectivity-checker
p=`pwd`
pushd /etc/systemd/system
sudo ln -s $p/ecc-internet-connectivity-checker.service
popd
# JMS This will not work until we restart WSL with systemd
#sudo systemctl enable ecc-internet-connectivity-checker.service

#########################################

# Install pxview so that we can export the PDS database to SQL.

cd $HOME/git
git clone https://github.com/jsquyres/pxlib-and-pxview.git
cd pxlib-and-pxview
./autogen.sh
# Use --disable-shared --enable-static just so that we don't have to
# set LD_LIBRARY_PATH to find libpx.so at run time.
./configure --disable-shared --enable-static
make -j 8
sudo make install

#########################################

# Setup a crontab to run our apps

cd $HOME
file=crontab-file.txt
rm -f $file
cat > $file <<EOF
# Run all the usual Linux-based automation
*/15 * * * * (cd /home/coeadmin/git/epiphany/media/linux && ./run.sh) >/dev/null 2>&1

# Run a "proof of life" script that logs out to Slack once a day.
# NOTE: The Ubuntu "fortune" database contains some non-PC jokes.  So
# I moved the contents of /usr/share/games/fortunes to a subdir and
# downloaded
# https://raw.githubusercontent.com/ruanyf/fortunes/master/data/fortunes,
# and then ran (in that dir) "strfile fortunes".  This seems to have
# re-seeded the fortunes database.
0 12 * * * (cd /home/coeadmin/git/epiphany/slack && ./run.sh) >/dev/null 2>&1

# Check for MP3s that were FTPed to this server; if we find any,
# upload them to Google Drive.
*/5 * * * * (cd /home/coeadmin/git/epiphany/media/linux/upload-mp3s-to-google-drive && ./run.sh) >/dev/null 2>&1
EOF
crontab $file
rm -f $file

#########################################

# Print what is needed next

cat <<EOF

************************************************


You need to restart WSL, and run these commands:

  sudo systemctl enable ecc-internet-connectivity-checker.service
  sudo systemctl start ecc-internet-connectivity-checker.service

If you haven't done so already, add this key to github:

  `cat $HOME/.ssh/id_rsa.pub`

Run this command to terminate this WSL (after you have saved the above
messages!) so that you can start it up again with all the new config
that was just installed:

  wsl.exe --terminate Ubuntu


************************************************

EOF
