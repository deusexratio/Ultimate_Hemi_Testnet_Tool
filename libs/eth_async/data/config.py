import os
import sys
from pathlib import Path


from dotenv import load_dotenv
# from data.config import ETHERSCAN_API_KEY

load_dotenv()


ETHERSCAN_API_KEY = str(os.getenv('ETHERSCAN_API_KEY'))
SEPOLIA_RPC = str(os.getenv('SEPOLIA_RPC'))
ARBISCAN_API_KEY = str(os.getenv('ARBISCAN_API_KEY'))
OPTIMISTIC_API_KEY = str(os.getenv('OPTIMISTIC_API_KEY'))
ARBITRUM_RPC = str(os.getenv('ARBITRUM_RPC'))
OPTIMISM_RPC = str(os.getenv('OPTIMISM_RPC'))
