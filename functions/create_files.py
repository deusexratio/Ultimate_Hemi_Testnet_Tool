import os
import csv

from libs.eth_async.utils.utils import update_dict
from libs.eth_async.utils.files import touch, write_json, read_json

from data import config
from data.models import WalletCSV


def create_files():
    touch(path=config.FILES_DIR)
    touch(path=config.LOG_FILE, file=True)
    touch(path=config.ERRORS_FILE, file=True)
    touch(path='.env', file=True)

    if not os.path.exists(config.IMPORT_FILE):
        with open(config.IMPORT_FILE, 'w') as f:
            writer = csv.writer(f)
            writer.writerow(WalletCSV.header)

    try:
        current_settings: dict | None = read_json(path=config.SETTINGS_FILE)
    except Exception:
        current_settings = {}

    settings = {
        'maximum_gas_price_sepolia': 50,
        'maximum_gas_price_hemi': 10,
        'minimal_balance_sepolia': 0.5,
        'minimal_balance_hemi': 0.1,
        'use_autorefill': True,
        'autorefill_amount': {'from': 0.0001, 'to': 0.0002},
        'eth_amount_for_bridge': {'from': 0.1, 'to': 0.5},
        'eth_amount_for_swap': {'from': 0.0001, 'to': 0.0005},
        'token_amount_for_swap': {'from': 10, 'to': 1000},
        # 'stable_faucet_amount': {'from': 9000, 'to': 10000},
        'erc20_amount_to_bridge': {'from': 4000, 'to': 4200},
        'activity_actions_delay': {'from': 100, 'to': 200},
        'token_amount_for_capsule': {'from': 10, 'to': 50},
    }
    write_json(path=config.SETTINGS_FILE, obj=update_dict(modifiable=current_settings, template=settings), indent=2)

create_files()
