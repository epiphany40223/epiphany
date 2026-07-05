#!/usr/bin/env sh
set -eu
exec pk-validate-gcalendar-reservations --config /opt/parishkit/config/pk-validate-gcalendar-reservations.yaml "$@"
