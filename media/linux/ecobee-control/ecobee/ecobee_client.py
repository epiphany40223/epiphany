"""
File name: ecobee_client.py
Author: Abel Alhussainawi, Cody Gividen, Zach Ballard
Created: 2/29/2025
License: BSD licenses
Description: This file contains functions to authenticate with Ecobee and schedule mode changes
"""

import json
import os
import shelve
from zoneinfo import ZoneInfo
from datetime import datetime
import pytz
from six.moves import input
from pyecobee import *
import requests
import logging
import sys

logger = logging.getLogger(__name__)

class EcobeeClient:
    def __init__(self, thermostat_name="Test1", credentials_file=None, schedule_payload_file=None, db_path=None, config=None):
        """
        Initializes the EcobeeClient, sets up the file paths and starts authentication.
        """
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.credentials_file = credentials_file or os.path.join(self.script_dir, '..', 'ecobee', 'credentials.json')
        self.schedule_payload_file = schedule_payload_file or os.path.join(self.script_dir, '..', 'ecobee', 'schedule_payload.txt')
        self.db_path = db_path or os.path.join(self.script_dir, '..', 'ecobee', 'pyecobee_db')
        self.thermostat_name = thermostat_name
        self.ecobee_service = None
        self.ECOBEE_THERMOSTAT_URL = "https://api.ecobee.com/1/thermostat"
        logger.info(f"Using credentials file: {self.credentials_file}")
        logger.info(f"Using schedule payload file: {self.schedule_payload_file}")
        logger.info(f"Using database path: {self.db_path}")
        self.config = config

        self.authenticate()

    def authenticate(self):
        """
        Authenticates the client with Ecobee, using either stored tokens,
        environment variables, or interactive authorization.
        """
        formatter = logging.Formatter('%(asctime)s %(name)-18s %(levelname)-8s %(message)s')
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)
        logger.setLevel(logging.DEBUG)

        print("Starting authentication process...")
        logger.info("Starting authentication process...")

        # Load application key from credentials.json
        credentials_path = self.credentials_file
        if not os.path.exists(credentials_path):
            error_msg = f"Credentials file not found at {credentials_path}"
            logger.error(error_msg)
            print(error_msg)
            raise FileNotFoundError(error_msg)

        with open(credentials_path, 'r') as f:
            creds_data = json.load(f)
            application_key = creds_data.get('credentials')
            if not application_key:
                error_msg = "No 'credentials' key found in credentials.json"
                logger.error(error_msg)
                print(error_msg)
                raise ValueError(error_msg)

        access_token = os.getenv('ECOBEE_ACCESS_TOKEN')
        refresh_token = os.getenv('ECOBEE_REFRESH_TOKEN')

        if access_token and refresh_token:
            logger.info("Using tokens from environment variables.")
            print("Using tokens from environment variables.")
            self.ecobee_service = EcobeeService(
                thermostat_name=self.thermostat_name,
                application_key=application_key,
                access_token=access_token,
                refresh_token=refresh_token
            )
            logger.debug(f"Initial access_token_expires_on: {self.ecobee_service.access_token_expires_on}")
            try:
                self.refresh_tokens()
                logger.info("Initial token refresh successful.")
                print("Initial token refresh successful.")
            except EcobeeApiException as e:
                logger.error(f"Failed to refresh tokens on init: {e}")
                print(f"Failed to refresh tokens: {e}")
                raise
        else:
            logger.info("Environment variables not set; attempting to load from shelve or authorize interactively.")
            print("Environment variables not set; proceeding to interactive authorization.")
            try:
                with shelve.open(self.db_path, protocol=2) as pyecobee_db:
                    self.ecobee_service = pyecobee_db.get(self.thermostat_name)
            except Exception as e:
                logger.debug(f"Failed to load from shelve: {e}")
                print(f"Failed to load from shelve: {e}")
                self.ecobee_service = EcobeeService(
                    thermostat_name=self.thermostat_name,
                    application_key=application_key
                )

            # Authorize if tokens are missing
            if self.ecobee_service.access_token is None or self.ecobee_service.refresh_token is None:
                self.authorize()
                self.request_tokens()

    def schedule_mode_change(self, dataframe, target_ecobee):
        """
        Applies a weekly schedule from a dataframe to the target Ecobee thermostat.
        Args:
        dataframe (pd.DataFrame): Schedule for each day of the week.
        target_ecobee (str): Thermostat name to update.
        """
        self.refresh_tokens_if_needed()

        schedule_payload_path = self.schedule_payload_file
        if not os.path.exists(schedule_payload_path):
            logger.error(f"Schedule payload file not found at {schedule_payload_path}")
            raise FileNotFoundError(f"Schedule payload file not found at {schedule_payload_path}")

        with open(schedule_payload_path, 'r') as f:
            schedule_payload = json.load(f)

        # Format the weekly schedule
        ordered_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        masked_schedule = [dataframe[day].tolist() for day in ordered_days]
        schedule_payload["thermostat"]["program"]["schedule"] = masked_schedule

        # Mask the climate temperature values with values from the config file if available.

        # Manual mapping between climateRef and config.json keys
        climate_ref_to_config_name = {
            "home": "Occupied",
            "away": "Unoccupied",
            "sleep": "Overnight"
        }

        for climate in schedule_payload["thermostat"]["program"].get("climates", []):
            mode_ref = climate.get("climateRef", "").lower()
            config_key = climate_ref_to_config_name.get(mode_ref)

            if config_key and config_key in self.config["modes"]:
                mode_config = self.config["modes"][config_key]
                climate["coolTemp"] = mode_config["max temperature"] * 10
                climate["heatTemp"] = mode_config["min temperature"] * 10
                logger.info(
                    f"Updated climate '{mode_ref}' (mapped to '{config_key}'): coolTemp={climate['coolTemp']}, heatTemp={climate['heatTemp']}")

        # Find thermostat ID and apply schedule
        thermostat_id = self.get_thermostat_id_by_name(target_ecobee)
        if not thermostat_id:
            logger.error(f"Thermostat {target_ecobee} not found.")
            raise ValueError(f"Thermostat {target_ecobee} not found.")

        schedule_payload['selection']['selectionMatch'] = thermostat_id

        # Send schedule update via Ecobee API
        response = requests.post(
            self.ECOBEE_THERMOSTAT_URL,
            data=json.dumps(schedule_payload, default=str),
            headers={'Authorization': 'Bearer ' + self.ecobee_service.access_token}
        )
        if response.ok:
            logger.info(f'Thermostat {target_ecobee} updated successfully.')
            print(f'Thermostat {target_ecobee} updated.')
            print(response.text)
        else:
            logger.error(f'Failed to update thermostat {target_ecobee}: {response.status_code}')
            print('Failure sending request to thermostat')
            print(response.text)
            raise Exception(f"Thermostat update failed: {response.text}")

    def get_thermostat_id_by_name(self, ecobee_name):
        """
        Given a thermostat name, return its identifier.
        Args:
        ecobee_name (str): Name of the thermostat.
        Returns:
        str: Thermostat identifier or None if not found.
        """

        self.refresh_tokens_if_needed()
        selection = Selection(selection_type=SelectionType.REGISTERED.value, selection_match='')

        try:
            thermostat_response = self.ecobee_service.request_thermostats(selection)
            for tstat in thermostat_response.thermostat_list:
                if tstat.name.lower() == ecobee_name.lower():
                    logger.debug(f"Found thermostat {ecobee_name} with ID {tstat.identifier}")
                    return tstat.identifier
            logger.warning(f"Thermostat {ecobee_name} not found in registered thermostats.")
            return None
        except EcobeeApiException as e:
            logger.error(f"Failed to fetch thermostats: {e}")
            raise

    def format_dt_str(self, dt_val):
        """
        Convert a datetime object or ISO datetime (or date) string to a friendly, readable format.
        """
        return dt_val.strftime("%b %d, %Y %I:%M %p %Z")

    def persist_to_shelf(self, file_name):
        """Persist the EcobeeService object to a shelve database."""
        with shelve.open(file_name, protocol=2) as pyecobee_db:
            pyecobee_db[self.thermostat_name] = self.ecobee_service
            logger.debug(f"Persisted EcobeeService to {file_name}")

    def refresh_tokens(self):
        """Refresh the access and refresh tokens."""
        logger.info("Refreshing tokens...")
        print("Attempting to refresh tokens...")
        try:
            token_response = self.ecobee_service.refresh_tokens()
            logger.debug(f"TokenResponse: {token_response.pretty_format()}")
            print(f"Refreshed access token: {self.ecobee_service.access_token}")
            print(f"New access_token_expires_on: {self.ecobee_service.access_token_expires_on}")
            self.persist_to_shelf(self.db_path)
            logger.info("Tokens refreshed successfully.")
            print("Tokens refreshed successfully.")
        except EcobeeApiException as e:
            logger.error(f"Error refreshing tokens: {e}")
            print(f"Error refreshing tokens: {e}")
            raise

    def request_tokens(self):
        """Request initial tokens after authorization (if you're interactive)."""
        logger.info("Requesting tokens...")
        print("Requesting tokens...")
        try:
            token_response = self.ecobee_service.request_tokens()
            logger.debug(f"TokenResponse: {token_response.pretty_format()}")
            print(f"New Access Token: {self.ecobee_service.access_token}")
            print(f"New Refresh Token: {self.ecobee_service.refresh_token}")
            self.persist_to_shelf(self.db_path)
        except EcobeeApiException as e:
            logger.error(f"Error requesting tokens: {e}")
            print(f"Error requesting tokens: {e}")
            raise

    def authorize(self):
        """Perform interactive authorization by generating a PIN."""
        logger.info("Starting authorization process...")
        print("Starting authorization process...")
        authorize_response = self.ecobee_service.authorize()
        logger.debug(f"AuthorizeResponse: {authorize_response.pretty_format()}")
        logger.info('Please goto ecobee.com, login to the web portal and click on the profile tab. '
                ' click on the My Apps option in the menu on the right. In the '
                'My Apps widget, select Add Application. paste "{0}" and in the textbox labelled "Enter PIN code" and '
                'then click "Validate". The next screen will display any '
                'permissions the app requires and will ask you to click "Authorize" to add the application.\n\n'
                'After completing this step please hit "Enter" to continue.'.format(
        authorize_response.ecobee_pin))

    def refresh_tokens_if_needed(self):
        """Refresh tokens if the access token has expired."""
        now_utc = datetime.now(pytz.utc)
        logger.debug(f"Checking token expiration: now={now_utc}, expires_on={self.ecobee_service.access_token_expires_on}")
        print(f"Checking token expiration: now={now_utc}, expires_on={self.ecobee_service.access_token_expires_on}")
        if (self.ecobee_service.access_token_expires_on is not None and
            now_utc > self.ecobee_service.access_token_expires_on):
            self.refresh_tokens()
