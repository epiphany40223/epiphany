import requests
import json

# Path to the credentials file
CREDENTIALS_FILE = "ecobee_credentials.json"

# URLs for Ecobee API
ECOBEE_API_URL = "https://api.ecobee.com/authorize"
ECOBEE_TOKEN_URL = "https://api.ecobee.com/token"

def load_application_key(credentials_file):
    """Load the application key from the given credentials file."""
    try:
        with open(credentials_file, "r") as file:
            creds_data = json.load(file)
            application_key = creds_data.get("credentials")
            if not application_key:
                raise ValueError("No 'credentials' key found in ecobee_credentials.json")
            return application_key
    except FileNotFoundError:
        print(f"Error: Credentials file '{credentials_file}' not found.")
        return None
    except json.JSONDecodeError:
        print("Error: Failed to parse JSON from the credentials file.")
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None

def get_authorization_pin(application_key):
    """Get the authorization PIN from Ecobee."""
    url = f"{ECOBEE_API_URL}?response_type=ecobeePin&client_id={application_key}"

    try:
        response = requests.get(url)
        response.raise_for_status()

        pin_data = response.json()
        if "ecobeePin" in pin_data and "code" in pin_data:
            pin = pin_data["ecobeePin"]
            auth_code = pin_data["code"]
            print(f"Please visit: https://www.ecobee.com/consumerportal/index.html#authorizeApp")
            print(f"Enter this PIN: {pin}")
            return auth_code
        else:
            print("Error: Could not retrieve PIN.")
            print(pin_data)
            return None
    except requests.RequestException as e:
        print(f"Error: Failed to get PIN - {e}")
        return None

def get_tokens(application_key, auth_code):
    """Use the authorization code to obtain access and refresh tokens."""
    data = {
        "code": auth_code,
        "client_id": application_key,
        "grant_type": "ecobeePin"
    }

    try:
        response = requests.post(ECOBEE_TOKEN_URL, data=data)
        response.raise_for_status()

        token_data = response.json()
        if "access_token" in token_data and "refresh_token" in token_data:
            return token_data["access_token"], token_data["refresh_token"]
        else:
            print("Error: Failed to obtain valid tokens.")
            print(token_data)
            return None, None
    except requests.RequestException as e:
        print(f"Error: Failed to obtain tokens - {e}")
        return None, None

def main():
    # Step 1: Load application key from ecobee_credentials.json
    application_key = load_application_key(CREDENTIALS_FILE)
    if not application_key:
        print("Cannot proceed without application key.")
        return

    # Step 2: Get authorization PIN
    auth_code = get_authorization_pin(application_key)
    if not auth_code:
        print("Cannot proceed without authorization code.")
        return

    # Step 3: Wait for user to authorize
    print("\nPlease authorize the app on Ecobee's website using the PIN.")
    input("Press Enter once you've authorized the app...")

    # Step 4: Get the access and refresh tokens
    access_token, refresh_token = get_tokens(application_key, auth_code)

    if access_token and refresh_token:
        print("\nSuccess! Here are your tokens:")
        print(f"Access Token: {access_token}")
        print(f"Refresh Token: {refresh_token}")
    else:
        print("Failed to obtain tokens.")

if __name__ == "__main__":
    main()
