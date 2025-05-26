#test 1 ecobee plus on
#test 2 ecobee plus off

from src.ecobee.ecobee_client import EcobeeClient
from datetime import datetime, timedelta
import json
import requests

ECOBEE_THERMOSTAT_URL = "https://api.ecobee.com/1/thermostat"

# Set up the Ecobee Client and authenticate
ecobee_client = EcobeeClient()
ecobee_client.authenticate()


with open('schedule_payload.txt', 'r') as f:
    schedule_payload = json.load(f)
target_ecobee = "Test1"
thermostat_id = ecobee_client.get_thermostat_id_by_name(target_ecobee)
schedule_payload['selection']['selectionMatch'] = thermostat_id
response = requests.post(ECOBEE_THERMOSTAT_URL, data=json.dumps(schedule_payload, default=str),
                         headers={'Authorization': 'Bearer ' + ecobee_client.ecobee_service.access_token})

if response.ok:
    print('Thermostat updated.')
    print(response.text)
else:
    print('Failure sending request to thermostat')
    print(response.text)
