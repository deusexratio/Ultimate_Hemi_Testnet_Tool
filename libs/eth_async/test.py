from tasks.controller import Controller
from data.models import Contracts

Controller.hourly_check_txs(Contracts.Hemi_Bridge_Sepolia)
# from data.config import SETTINGS_FILE
#
# print(SETTINGS_FILE)