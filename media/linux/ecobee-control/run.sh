#!/bin/bash

set -euxo pipefail

dir=$HOME/credentials/ecobee

./src/main.py \
   --debug \
   --config data/config.json \
   --google-app-id $dir/google-application-id.json \
   --google-token $dir/google-token.json \
   --ecobee-credentials $dir/ecobee-credentials.json \
   2>&1 | tee out.txt
