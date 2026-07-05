#!/usr/bin/env sh
set -eu
exec pk-sync-ps-to-cc --config /opt/parishkit/config/pk-sync-ps-to-cc.yaml "$@"
