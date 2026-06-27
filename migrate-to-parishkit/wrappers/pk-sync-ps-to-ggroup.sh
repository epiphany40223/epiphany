#!/usr/bin/env sh
set -eu
exec pk-sync-ps-to-ggroup --config /opt/parishkit/config/pk-sync-ps-to-ggroup.yaml "$@"
