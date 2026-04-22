from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

flow = InstalledAppFlow.from_client_secrets_file(
    "client_secret.json", SCOPES
)

creds = flow.run_local_server(port=0)

print("\n=== COPY THESE INTO STREAMLIT SECRETS ===\n")
print("client_id:", creds.client_id)
print("client_secret:", creds.client_secret)
print("refresh_token:", creds.refresh_token)
