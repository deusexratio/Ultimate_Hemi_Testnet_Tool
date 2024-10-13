import random
from datetime import datetime, timedelta

from loguru import logger
from sqlalchemy import select, and_, or_

from data.models import Settings
from utils.db_api.wallet_api import db, get_wallet
from utils.db_api.models import Wallet


def update_next_action_time(private_key: str, seconds: int) -> bool:
    try:
        wallet = get_wallet(private_key=private_key)
        wallet.next_action_time = datetime.now() + timedelta(seconds=seconds)
        # print(wallet.next_action_time)
        db.commit()
        return True
    except BaseException:
        return False


def update_today_activity(private_key: str, activity: str | list, key: bool = True) -> bool:
    try:
        wallet = get_wallet(private_key=private_key)
        if 'depositETH' in activity:
            if key is True:
                wallet.today_activity_bridge_eth += 1
            if key is False:
                wallet.today_activity_bridge_eth = 0
        if 'depositERC20' in activity:
            if key is True:
                wallet.today_activity_bridge_erc20 += 1
            if key is False:
                wallet.today_activity_bridge_erc20 = 0
        if 'swaps' in activity:
            if key is True:
                wallet.today_activity_swaps += 1
            if key is False:
                wallet.today_activity_swaps = 0
        if 'capsule' in activity:
            if key is True:
                wallet.twice_weekly_capsule += 1
            if key is False:
                wallet.twice_weekly_capsule = 0
        if 'safe' in activity:
            wallet.safe_created = key
        db.commit()
        return True
    except BaseException as e:
        raise BaseException(f'{e}: Wrong activity given to the update_today_activity')


# def update_expired(initial: bool = False) -> None:
#     now = datetime.now()
#     if initial:
#         stmt = select(Wallet).where(
#             and_(
#                 Wallet.initial_completed.is_(False),
#                 or_(
#                     Wallet.next_initial_action_time <= now,
#                     Wallet.next_initial_action_time.is_(None),
#                 )
#             )
#         )
#     else:
#         stmt = select(Wallet).where(
#             and_(
#                 Wallet.initial_completed.is_(True),
#                 or_(
#                     Wallet.next_activity_action_time <= now,
#                     Wallet.next_activity_action_time.is_(None),
#                 )
#             )
#         )
#
#     expired_wallets: list[Wallet] = db.all(stmt=stmt)
#
#     if not expired_wallets:
#         return
#
#     settings = Settings()
#     for wallet in expired_wallets:
#         if initial:
#             wallet.next_initial_action_time = now + timedelta(
#                 seconds=random.randint(0, int(settings.initial_actions_delay.to_ / 2))
#             )
#             logger.info(
#                 f'{wallet.address}: Action time was re-generated: '
#                 f'{wallet.next_initial_action_time}.'
#             )
#         else:
#             wallet.next_activity_action_time = now + timedelta(
#                 seconds=random.randint(0, int(settings.activity_actions_delay.to_ / 3))
#             )
#             logger.info(
#                 f'{wallet.address}: Action time was re-generated: '
#                 f'{wallet.next_activity_action_time}.'
#             )
#
#     db.commit()




