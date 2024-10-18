import random
import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy.testing import startswith_
from web3 import Web3
from loguru import logger
from sqlalchemy import select, func, or_, and_


from libs.eth_async.client import Client
from libs.eth_async.data.models import Network, Networks, RawContract

from data.models import Settings, Contracts
from data.config import DELAY_IN_CASE_OF_ERROR
from utils.db_api.wallet_api import db, reset_daily_tasks, get_wallets
from utils.db_api.models import Wallet
from tasks.controller import Controller
from functions.select_random_action import select_random_action
from utils.update_expired import update_next_action_time, update_today_activity

# now it's working only in sepolia
async def hourly_check_failed_txs(contract: RawContract | str,
                                  function_names: str | list[str] | None = None,
                                  network: Network = Networks.Sepolia) -> bool:
    await asyncio.sleep(90) # sleep at start not to interfere with activity logs, mostly for debug
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
                            print(f'failed {key}')
                            update_today_activity(private_key=wallet.private_key, activity=key, key=False)

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
                            print(f'not failed {key}')
                            update_today_activity(private_key=wallet.private_key, activity=key, key=True)

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
                        update_today_activity(private_key=wallet.private_key, activity=function_names, key=False)
                    elif txs_without_error:
                        update_today_activity(private_key=wallet.private_key, activity=function_names, key=True)

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
                          'swaps']  # 'capsule' ,
            if now_utc_hour == reset_hour:
                for wallet in get_wallets():
                    update_today_activity(private_key=wallet.private_key, activity=activities, key=False)
                logger.success(f'Succesfully reset activities at {datetime.now()}')
            await asyncio.sleep(1800)  # wait for next hour to try
        except BaseException:
            logger.error('Something went wrong in auto_daily_reset_activities task')

async def auto_reset_capsule():
    while True:
        try:
            await asyncio.sleep(172800) # sleep for three days
            for wallet in get_wallets():
                activities = 'capsule'
                update_today_activity(private_key=wallet.private_key, activity=activities, key=False)
            logger.info(f'Succesfully reset capsules at {datetime.now()}')
        except BaseException:
            logger.error('Something went wrong in auto_reset_capsule task')

def manual_daily_reset_activities() -> bool:
    try:
        activities = ['depositETH', 'depositERC20',
                      'swaps', 'capsule']
        for wallet in get_wallets():
            update_today_activity(private_key=wallet.private_key, activity=activities, key=False)
        logger.info(f'Succesfully reset all activities except Safe at {datetime.now()}')
        return True
    except BaseException:
        logger.error('Something went wrong in manual_daily_reset_activities task')
        return False

async def fill_queue(queue, tasks_num):
    while True:
        try:
            if queue.full():
                await asyncio.sleep(10) # todo: test
                continue
            while not queue.full():
                q_size = queue.qsize()
                stmt_start = (select(Wallet).where(
                    or_(Wallet.today_activity_swaps < 2,
                        Wallet.twice_weekly_capsule < 2,
                        Wallet.safe_created.is_(False)
                    )
                ).where(Wallet.next_action_time <= datetime.now()
                    ).order_by(Wallet.next_action_time).offset(q_size)  # pick wallet so far from top as q_size
                            )
                wallet: Wallet = db.one(Wallet, stmt=stmt_start)
                q_size = queue.qsize()
                await queue.put(wallet)
        except BaseException:
            logger.error('Something went wrong in fill_queue task')
            return False

async def first_time_launch_db():
    settings = Settings()
    stmt_first = (select(Wallet).filter(Wallet.next_action_time.is_(None)))
    first_time_wallets: Wallet = db.all(Wallet, stmt=stmt_first)
    if isinstance(first_time_wallets, list):
        random.shuffle(first_time_wallets)
        for wallet in first_time_wallets:
            logger.info(f'first time wallet: {wallet}')
            wallet.next_action_time = (datetime.now() +
                                       timedelta(seconds=random.randint(settings.activity_actions_delay.from_,
                                                                        settings.activity_actions_delay.to_)))
            db.insert(wallet)
            logger.success(f'Successfully set first action time {wallet.next_action_time} for {wallet}')


async def correct_next_action_time():
    # Check if next action time is assigned correctly
    # and if not, add 30 minutes to a wallet that has been already done
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


async def activity(queue, tasks_num):
    delay = 5
    while True:
        try:
            settings = Settings()  # проверить чтобы настройки обновлялись каждую итерацию, в цикле вроде не работало
            # Fill in next action time for newly initialized wallets in DB
            await first_time_launch_db()

            # Check if gas price is OK
            client_sep = Client(private_key='', network=Networks.Sepolia)
            gas_price_sep = await client_sep.transactions.gas_price()
            client_hemi = Client(private_key='', network=Networks.Hemi_Testnet)
            gas_price_hemi = await client_hemi.transactions.gas_price()
            controller = Controller(client=client_hemi)

            # Select wallet from DB to do an activity
            wallet = await queue.get()
            if wallet:
                update_next_action_time(private_key=wallet.private_key, seconds=120) # put a lil bit away from queue
                logger.info(f'{datetime.now().time().replace(microsecond=0)} : wallet: {wallet}')
            # todo: test (for now it's holding on 120)
            if not wallet:
                await asyncio.sleep(delay)
                logger.info('no wallet selected')
                continue

            # Pick an action for selected wallet
            action = await select_random_action(wallet=wallet)
            # if action:  # debug
            #     print(wallet, action)  # debug

            sepolia_action_list = [
                controller.sepolia.deposit_eth_to_hemi, controller.sepolia.bridge_dai_to_hemi,
                controller.sepolia.bridge_usdt_to_hemi, controller.sepolia.bridge_usdc_to_hemi,
                controller.sepolia.faucet_dai,  controller.sepolia.faucet_usdc,  controller.sepolia.faucet_usdt
            ]
            if action in sepolia_action_list:
                i = 0
                while float(gas_price_sep.Wei) > Web3.to_wei(settings.maximum_gas_price_sepolia, 'gwei') and i < 5:
                    logger.debug(f'Gas price in Sepolia is too high'
                        f'({Web3.from_wei(gas_price_sep.Wei, "gwei")} > {settings.maximum_gas_price_sepolia})')
                    await asyncio.sleep(60 * 1)
                    gas_price_sep = await client_sep.transactions.gas_price()
                    i += 1
                if i == 5:
                    continue # after 5 tries try to do another wallet

            hemi_action_list = [controller.hemi.create_capsule, controller.hemi.create_safe, controller.hemi.swap_dai]
            if action in hemi_action_list:
                i = 0
                while float(gas_price_hemi.Wei) > Web3.to_wei(settings.maximum_gas_price_hemi, 'gwei') and i < 5:
                    logger.debug(f'Gas price in Hemi is too high'
                                 f'({Web3.from_wei(gas_price_hemi.Wei, "gwei")} > {settings.maximum_gas_price_hemi})')
                    await asyncio.sleep(60 * 1)
                    gas_price_hemi = await client_hemi.transactions.gas_price()
                    i += 1
                if i == 5:
                    continue # after 5 tries try to do another wallet

            if not action:
                logger.error(f'{wallet} | select_random_action | can not choose the action')
                update_next_action_time(private_key=wallet.private_key, seconds=DELAY_IN_CASE_OF_ERROR)
                continue

            if action == 'Insufficient balance and out of Ether':
                logger.error(f'{wallet}: {action}')
                update_next_action_time(private_key=wallet.private_key, seconds=DELAY_IN_CASE_OF_ERROR)
                wallet.insufficient_balance = True
                db.commit()
                continue

            if action == 'Insufficient balance and not trying to refill':
                logger.critical(f'{wallet} : {action}')
                update_next_action_time(private_key=wallet.private_key, seconds=DELAY_IN_CASE_OF_ERROR)
                wallet.insufficient_balance = True
                db.commit()
                continue

            # Launch action and process result of action: log what has been done or if action failed
            status = await action()

            if status is None:
                print(f'{action} : returned None')

            if 'Failed' not in status:
                update_next_action_time(
                    private_key=wallet.private_key,
                    seconds=random.randint(settings.activity_actions_delay.from_,
                                           settings.activity_actions_delay.to_)
                )
                logger.success(f'{wallet}: {status}')

                if 'ETH was bridged to Hemi via official bridge' in status:
                    update_today_activity(private_key=wallet.private_key, activity='depositETH')
                if 'stablecoin was bridged to Hemi via official bridge' in status:
                    update_today_activity(private_key=wallet.private_key, activity='depositERC20')
                if 'swapped' in status:
                    update_today_activity(private_key=wallet.private_key, activity='swaps')
                if 'Created capsule' in status:
                    update_today_activity(private_key=wallet.private_key, activity='capsule')
                if 'Created safe' in status:
                    update_today_activity(private_key=wallet.private_key, activity='safe')

                # Display next action time
                stmt = (select(func.min(Wallet.next_action_time)).where(
                    or_(Wallet.today_activity_swaps < 2,
                        Wallet.twice_weekly_capsule < 2,
                        Wallet.safe_created.is_(False)
                        )
                )
                )
                next_action_time = db.one(stmt=stmt)
                logger.info(f'The next closest activity action will be performed at {next_action_time}')

            else:
                update_next_action_time(private_key=wallet.private_key, seconds=DELAY_IN_CASE_OF_ERROR)
                db.commit()
                logger.error(f'{wallet.address}: {status}')

            # end of cycle for wallet, sleep for random designated time
            await asyncio.sleep(random.randint(settings.activity_actions_delay.from_,
                                               settings.activity_actions_delay.to_))


        except BaseException as e:
            logger.exception(f'Something went wrong: {e}')

        except ValueError as err:
            logger.exception(f'Something went wrong: {err}')

        finally:
            await asyncio.sleep(delay)
