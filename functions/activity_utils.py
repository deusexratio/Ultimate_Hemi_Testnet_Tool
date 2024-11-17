import random
import asyncio
from datetime import datetime, timedelta, timezone, time

from loguru import logger
from sqlalchemy import select, func, or_, and_


from libs.eth_async.blockscan_api import APIFunctions
from libs.eth_async.client import Client
from libs.eth_async.data.models import Network, Networks, RawContract

from data.models import Settings, Contracts
from utils.db_api.wallet_api import db, get_wallets, get_failed_txs, get_failed_marked_tx
from utils.db_api.models import Wallet, Failed
from utils.update_functions import update_next_action_time, update_today_activity


# now it's working only in sepolia
async def hourly_check_failed_txs(contract: RawContract | str,
                                  function_names: str | list[str] | None = None,
                                  network: Network = Networks.Sepolia) -> bool:
    await asyncio.sleep(90)  # sleep at start not to interfere with activity logs, mostly for debug
    while True:
        try:
            # later delete function_name argument maybe
            if function_names is None:
                function_names = ['depositETH', 'depositERC20']
            wallets = get_wallets()
            now_utc = datetime.now(timezone.utc)
            midnight_utc = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
            after_timestamp = int(midnight_utc.timestamp())
            for wallet in wallets:
                print(f'Checking txs statuses for wallet: {wallet}')
                client = Client(private_key=wallet.private_key, network=network)
                if isinstance(contract, RawContract):
                    contract = contract.address
                error_txs_dict = {}
                non_error_txs_dict = {}
                if isinstance(function_names, list):
                    # Update statuses in db for failed txs
                    for function in function_names:
                        txs_with_error = await client.transactions.find_txs(
                            contract=contract,
                            function_name=function,
                            after_timestamp=after_timestamp,
                            address=wallet.address,
                            is_error='1'
                        )
                        error_txs_dict[function] = txs_with_error
                    for key, value in error_txs_dict.items():
                        # print(key, value)
                        if value:  # check if tx exists, failed to come up with additional checks for now
                            logger.info(f"Found failed tx in sepolia {key}")
                            update_today_activity(private_key=wallet.private_key, activity=key, key='-')

                    # Update statuses in DB for successful txs (needed bc failed txs been marked so for a whole day
                    # which leads to an endless daily activity cycle for a wallet)
                    for function in function_names:
                        txs_without_error = await client.transactions.find_txs(
                            contract=contract,
                            function_name=function,
                            after_timestamp=after_timestamp,
                            address=wallet.address,
                            is_error='0'
                        )
                        non_error_txs_dict[function] = txs_without_error
                    for key, value in non_error_txs_dict.items():
                        # print(key, value)
                        if value:  # check if tx exists, failed to come up with additional checks for now
                            logger.info(f"Found NOT failed tx in sepolia {key}")
                            update_today_activity(private_key=wallet.private_key, activity=key, key='+')

                # STRING NOT TESTED
                elif isinstance(function_names, str):
                    txs_with_error = await client.transactions.find_txs(
                        contract=contract,
                        function_name=function_names,
                        after_timestamp=after_timestamp,
                        address=wallet.address,
                        is_error='1'
                    )
                    txs_without_error = await client.transactions.find_txs(
                        contract=contract,
                        function_name=function_names,
                        after_timestamp=after_timestamp,
                        address=wallet.address,
                        is_error='0'
                    )
                    if txs_with_error:
                        update_today_activity(private_key=wallet.private_key, activity=function_names, key='-')
                    elif txs_without_error:
                        update_today_activity(private_key=wallet.private_key, activity=function_names, key='+')

                else:
                    logger.error(f'Wrong function names given to hourly_check_failed_txs: {function_names}')
                await asyncio.sleep(3)  # sleep to not exceed api request limit

        except BaseException as e:
            logger.exception(f'Something went wrong: {e}')
            return False
        finally:
            await asyncio.sleep(3600)  # sleep to check statuses every hour


async def auto_daily_reset_activities():
    while True:
        try:
            reset_hour = 0
            now_utc_hour = int(datetime.now(timezone.utc).time().hour)
            logger.info(f'Current UTC hour: {now_utc_hour}. Will reset activites at {reset_hour} hours.')
            activities = ['depositETH', 'depositERC20',
                          'swaps', 'recheck']  # 'capsule' ,
            if now_utc_hour == reset_hour:
                for wallet in get_wallets():
                    update_today_activity(private_key=wallet.private_key, activity=activities, key='0')
                logger.success(f'Succesfully reset activities at {datetime.now()}')
            await asyncio.sleep(1800)  # wait for next hour to try
        except BaseException:
            logger.error('Something went wrong in auto_daily_reset_activities task')


async def auto_reset_capsule():
    while True:
        try:
            await asyncio.sleep(172800)  # sleep for three days
            for wallet in get_wallets():
                activities = 'capsule'
                update_today_activity(private_key=wallet.private_key, activity=activities, key='0')
            logger.info(f'Succesfully reset capsules at {datetime.now()}')
        except BaseException:
            logger.error('Something went wrong in auto_reset_capsule task')


def manual_daily_reset_activities() -> bool:
    try:
        activities = ['depositETH', 'depositERC20',
                      'swaps', 'capsule']
        for wallet in get_wallets():
            update_today_activity(private_key=wallet.private_key, activity=activities, key='0')
        logger.info(f'Succesfully reset all activities except Safe at {datetime.now()}')
        return True
    except BaseException:
        logger.error('Something went wrong in manual_daily_reset_activities task')
        return False


async def fill_queue(queue, tasks_num):
    while True:
        try:
            if queue.full():
                await asyncio.sleep(10)
                continue
            while not queue.full():
                offset = queue.qsize()
                # check if whole queue is just None objects and flush them
                if all(item is None for item in queue._queue):
                    offset = 0
                stmt_start = (select(Wallet).where(
                    or_(Wallet.today_activity_swaps < 2,
                        Wallet.twice_weekly_capsule < 2,
                        Wallet.safe_created.is_(False)
                        )
                ).where(Wallet.next_action_time <= datetime.now()
                        ).order_by(Wallet.next_action_time).offset(offset)  # pick wallet so far from top as q_size
                              )
                wallet: Wallet = db.one(Wallet, stmt=stmt_start)
                await queue.put(wallet)
        except BaseException:
            logger.error('Something went wrong in fill_queue task')
            return False


async def first_time_launch_db():
    settings = Settings()
    stmt_first = (select(Wallet).filter(Wallet.next_action_time.is_(None)))
    first_time_wallets = db.all(Wallet, stmt=stmt_first)
    if isinstance(first_time_wallets, list):
        random.shuffle(first_time_wallets)
        for wallet in first_time_wallets:
            logger.info(f'first time wallet: {wallet}')
            wallet.next_action_time = (datetime.now() +
                                       timedelta(seconds=random.randint(settings.activity_actions_delay.from_,
                                                                        settings.activity_actions_delay.to_)))
            db.commit()
            logger.success(f'Successfully set first action time {wallet.next_action_time} for {wallet}')
    if isinstance(first_time_wallets, Wallet):
        logger.info(f'first time wallet: {first_time_wallets}')
        first_time_wallets.next_action_time = (datetime.now() +
                                   timedelta(seconds=random.randint(settings.activity_actions_delay.from_,
                                                                    settings.activity_actions_delay.to_)))
        db.commit()
        logger.success(f'Successfully set first action time {first_time_wallets.next_action_time} for {first_time_wallets}')


async def correct_next_action_time():
    # Check if next action time is assigned correctly
    # and if not, add 30 minutes to a wallet that has been already done

    # I guess this function is not really necessary
    while True:
        try:
            settings = Settings()
            for wallet in get_wallets():
                if wallet.today_activity_swaps >= 2 and wallet.twice_weekly_capsule >= 2 and wallet.safe_created:
                    seconds = random.randint(settings.activity_actions_delay.from_,
                                             settings.activity_actions_delay.to_)
                    update_next_action_time(private_key=wallet.private_key,
                                            seconds=seconds)
                    logger.info(
                        f'Added {seconds} seconds to next action time '
                        f'for already done wallet: {wallet} : {wallet.next_action_time}')
            await asyncio.sleep(1800)
        except BaseException:
            logger.error('Something went wrong in correct_next_action_time task')

async def _past_block(api: APIFunctions):
    # past_utc_midnight_timestamp = int(datetime.combine(datetime.today(), time.min).timestamp())
    past_utc_midnight = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    past_utc_midnight_timestamp = int(past_utc_midnight.timestamp())
    past_utc_midnight_block = await api.block.getblocknobytime(past_utc_midnight_timestamp)
    return int(past_utc_midnight_block['result']['blockNumber']), past_utc_midnight

async def _check():
    api = APIFunctions(key=None, url=Networks.Hemi_Testnet.api.url)
    past_utc_midnight_block, past_utc_midnight = await _past_block(api)
    logger.info(f"Starting to check all today tx statuses past last UTC midnight: {past_utc_midnight}")
    for wallet in get_wallets():
            tx_dict = await api.account.txlist(address=wallet.address, startblock=past_utc_midnight_block)
            tx_list = tx_dict.get('result')
            if tx_list:
                logger.info(f"{wallet} : fetched tx list, searching for failed transactions")
                error_count = 0
                for tx in tx_list:
                    # print(tx)
                    if tx['isError'] == '1':
                        error_count += 1
                        already_done = False
                        for failed_tx in get_failed_txs():
                            if tx['hash'] == failed_tx.tx_hash and failed_tx.decreased_activity_for_today:
                                already_done = True
                                break
                        if already_done:
                            continue
                        else:
                            failed_tx_instance = Failed(
                                tx_hash=tx['hash'],
                                block=int(tx['blockNumber']),
                                wallet_address=tx['from'],
                                contract=tx['to'],
                                decreased_activity_for_today=True
                            )
                            db.insert(failed_tx_instance)
                            if tx['to'] == Contracts.Hemi_Swap_Router.address.lower():
                                logger.info(f"Found failed swap tx by: {wallet} | tx hash: {tx['hash']}")
                                update_today_activity(wallet.private_key, activity='swaps', key='-')
                                update_today_activity(wallet.private_key, activity='recheck')
                            if tx['to'] == Contracts.Hemi_Capsule.address.lower():
                                logger.info(f"Found failed capsule tx by: {wallet} | tx hash: {tx['hash']}")
                                update_today_activity(wallet.private_key, activity='capsule', key='-')
                                update_today_activity(wallet.private_key, activity='recheck')
                if error_count == 0:
                    logger.info(f"{wallet} : didn't find failed transactions for today")
                await asyncio.sleep(.5)  # sleep to not exceed API rate limits. Maybe later will add proxy to APIFunctions
            else:
                logger.error(f"{wallet} | Tx list for today is empty or didn't get response")

async def check_today_tx_status(manual: bool = False):
    while True:
        try:
            if manual:
                await _check()
                return
            now_utc_hour = int(datetime.now(timezone.utc).time().hour)
            logger.info(f'Current UTC hour: {now_utc_hour}. Сheck_today_tx_status is idle.')
            await asyncio.sleep(1800)
            await _check()
        except BaseException:
            logger.error('Something went wrong in check_today_tx_status task')


async def clear_past_failed_txs():
    api = APIFunctions(key=None, url=Networks.Hemi_Testnet.api.url)
    while True:
        past_utc_midnight_block, past_utc_midnight = await _past_block(api)
        for failed_tx in get_failed_txs():
            if failed_tx.block < past_utc_midnight_block:
                db.delete(failed_tx)
        await asyncio.sleep(3600)
