# payments/paypack_client.py
from paypack.client import HttpClient
from paypack.transactions import Transaction
from paypack.oauth2 import Oauth
import os
# from dotenv import load_dotenv

# load_dotenv()  # loads .env into environment

CLIENT_ID = os.getenv("PAYPACK_CLIENT_ID")
CLIENT_SECRET = os.getenv("PAYPACK_CLIENT_SECRET")

# Initialize HttpClient
client = HttpClient(client_id=CLIENT_ID, client_secret=CLIENT_SECRET)

# Transaction helper
transaction = Transaction()

# OAuth helper
oauth = Oauth()
