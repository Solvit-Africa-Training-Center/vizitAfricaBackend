# payments/paypack_client.py
from paypack.client import HttpClient
from paypack.transactions import Transaction
from paypack.oauth2 import Oauth
import os

# Load credentials from environment variables
CLIENT_ID = os.getenv("PAYPACK_CLIENT_ID", "7860b702-00e3-11f1-a169-deadd43720af")
CLIENT_SECRET = os.getenv("PAYPACK_CLIENT_SECRET", "d70805d29c435df9d110e1515b02b204da39a3ee5e6b4b0d3255bfef95601890afd80709")

# Initialize HttpClient
client = HttpClient(client_id=CLIENT_ID, client_secret=CLIENT_SECRET)

# Transaction helper
transaction = Transaction()

# OAuth helper
oauth = Oauth()
