#!/usr/bin/env sh
set -eu
exec pk-create-ps-ministry-rosters --config /opt/parishkit/config/pk-create-ps-ministry-rosters.yaml "$@"
