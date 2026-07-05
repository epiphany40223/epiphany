# Migrate to parishkit

This directory contains operator-facing migration notes, non-secret starter
configs, and cron-friendly wrappers for replacing the old scripts with the new
`parishkit` package.

## Install the local package

Build and install from the new repository on the target host:

```sh
cd /path/to/parishkit
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[google,slack]'
```

Use the same virtual environment from cron, or install into a dedicated
system-managed environment.

## Create runtime directories

```sh
sudo mkdir -p /opt/parishkit/{bin,cache,config,credentials,logs,reports,run}
sudo chmod 700 /opt/parishkit/credentials
```

Copy the YAML files from `configs/` to `/opt/parishkit/config/` and edit any
site-specific IDs or addresses before enabling cron.

## Fresh credentials

ParishSoft:

- Store the read-only API key at
  `/opt/parishkit/credentials/parishsoft-api-key.txt`.
- Restrict file permissions to the automation user.
- Validate with `parishkit` smoke test:

```sh
parishkit-parishsoft-connectivity \
  --api-key-file /opt/parishkit/credentials/parishsoft-api-key.txt \
  --send
```

Google:

1. Create a fresh Google Cloud project.
2. Enable Calendar API, Admin SDK API, Groups Settings API, Drive API, and
   Sheets API as needed by the migrated jobs.
3. Create service accounts for automation jobs that support domain-wide
   delegation.
4. Enable domain-wide delegation on each service account and record the client
   ID.
5. In Google Workspace Admin, authorize the client ID for the scopes shown in
   the relevant script README files.
6. Create and store service account JSON keys under
   `/opt/parishkit/credentials/`.
7. For OAuth-user flows, configure the OAuth consent screen and OAuth client,
   then use `scripts/smoke-tests/google-api.py --bootstrap-user-token` from the
   `parishkit` repo to generate token files.
8. Store all generated tokens under `/opt/parishkit/credentials/`.

Constant Contact:

- Create a Constant Contact app/client and store the client JSON at
  `/opt/parishkit/credentials/constant-contact-client.json`.
- Run the documented device OAuth smoke tool from the `parishkit` repo and
  store the token JSON at
  `/opt/parishkit/credentials/constant-contact-token.json`.

Slack:

- Store the Slack bot token at `/opt/parishkit/credentials/slack-token.txt`.
- Configure `slack.token_file`, `slack.channel`, and `slack.level` in any job
  config that should send critical log notifications.

## Credential shortcut

If the old host already has known-good credentials, the operator may copy them
to `/opt/parishkit/credentials/` as a migration shortcut. Do not commit copied
credential files. Run the smoke tests before enabling cron.

## Cron changes

Replace old cron entries that invoke:

- `media/linux/calendar-reservations/run.sh`
- `media/linux/ps-queries/create-ministry-rosters.py`
- `media/linux/ps-queries/sync-google-group.py`
- `media/linux/ps-queries/sync-ps-to-cc.py`

with the wrappers in `wrappers/`. The wrappers call the new `pk-*` commands
and use matching `/opt/parishkit/config/pk-*.yaml` files.

Wrapper and config pairs:

- `pk-cron-runner` uses `/opt/parishkit/config/pk-cron-runner.yaml` to run
  the migrated scheduled jobs with one shared lock and runner log.
- `wrappers/pk-validate-gcalendar-reservations.sh`
  uses `/opt/parishkit/config/pk-validate-gcalendar-reservations.yaml`.
- `wrappers/pk-create-ps-ministry-rosters.sh`
  uses `/opt/parishkit/config/pk-create-ps-ministry-rosters.yaml`.
- `wrappers/pk-sync-ps-to-ggroup.sh`
  uses `/opt/parishkit/config/pk-sync-ps-to-ggroup.yaml`.
- `wrappers/pk-sync-ps-to-cc.sh`
  uses `/opt/parishkit/config/pk-sync-ps-to-cc.yaml`.

Example:

```cron
*/10 * * * * /path/to/old-repo/migrate-to-parishkit/wrappers/pk-validate-gcalendar-reservations.sh
```

Or run the migrated jobs through one runner config. Schedule roster generation
once a day at 2am, and run the sync/validation jobs every 15 minutes on an
offset so the two runner invocations do not start at the same time:

```cron
5,20,35,50 * * * * pk-cron-runner --config /opt/parishkit/config/pk-cron-runner.yaml pk-sync-ps-to-ggroup pk-sync-ps-to-cc pk-validate-gcalendar-reservations
0 2 * * * pk-cron-runner --config /opt/parishkit/config/pk-cron-runner.yaml pk-create-ps-ministry-rosters
```

To run only selected jobs from that config, pass their job names after the
config path:

```sh
pk-cron-runner --config /opt/parishkit/config/pk-cron-runner.yaml \
  pk-create-ps-ministry-rosters \
  pk-sync-ps-to-ggroup \
  pk-sync-ps-to-cc \
  pk-validate-gcalendar-reservations
```

Run each wrapper manually with `--dry-run` first, review logs under
`/opt/parishkit/logs/`, then remove the dry-run override from cron if the job is
expected to write.
