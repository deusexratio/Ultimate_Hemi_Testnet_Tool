from datetime import datetime, timedelta

from utils.db_api.wallet_api import db, get_wallet


def update_next_action_time(private_key: str, seconds: int) -> bool:
    try:
        wallet = get_wallet(private_key=private_key)
        wallet.next_action_time = datetime.now() + timedelta(seconds=seconds)
        db.commit()
        return True
    except BaseException:
        return False


def update_today_activity(private_key: str, activity: str | list, key: str = '+') -> bool:
    try:
        wallet = get_wallet(private_key=private_key)
        if 'depositETH' in activity:
            if key == '+':
                wallet.today_activity_bridge_eth += 1
            if key == '0':
                wallet.today_activity_bridge_eth = 0
            if key == '-':
                wallet.today_activity_bridge_eth -= 1
        if 'depositERC20' in activity:
            if key == '+':
                wallet.today_activity_bridge_erc20 += 1
            if key == '0':
                wallet.today_activity_bridge_erc20 = 0
            if key == '-':
                wallet.today_activity_bridge_erc20 -= 1
        if 'swaps' in activity:
            if key == '+':
                wallet.today_activity_swaps += 1
            if key == '0':
                wallet.today_activity_swaps = 0
            if key == '-':
                wallet.today_activity_swaps -= 1
        if 'capsule' in activity:
            if key == '+':
                wallet.twice_weekly_capsule += 1
            if key == '0':
                wallet.twice_weekly_capsule = 0
            if key == '-':
                wallet.twice_weekly_capsule -= 1
        if 'safe' in activity:
            wallet.safe_created = True
        if 'recheck' in activity:
            wallet.rechecked_txs_today = True
        db.commit()
        return True
    except BaseException as e:
        raise BaseException(f'{e}: Wrong activity given to the update_today_activity')
