import random
import asyncio
from datetime import datetime

from web3 import Web3
from loguru import logger
from sqlalchemy import select, func, or_, and_

from libs.eth_async.client import Client
from libs.eth_async.data.models import Networks

from data.models import Settings, Contracts
from data.config import DELAY_IN_CASE_OF_ERROR
from utils.db_api.wallet_api import db
from utils.db_api.models import Wallet
from utils.update_functions import update_next_action_time, update_today_activity
from tasks.controller import Controller
from functions.select_random_action import select_random_action
from functions import activity_utils


async def activity(queue):
    delay = 5
    logger.info('Starting activity task')
    while True:
        try:
            settings = Settings()
            # Fill in next action time for newly initialized wallets in DB
            await activity_utils.first_time_launch_db()

            # Get gas prices
            client_sep = Client(private_key='', network=Networks.Sepolia)
            gas_price_sep = await client_sep.transactions.gas_price()
            client_hemi = Client(private_key='', network=Networks.Hemi_Testnet)
            gas_price_hemi = await client_hemi.transactions.gas_price()

            # Select wallet from DB to do an activity
            wallet = await queue.get()
            if wallet:
                update_next_action_time(private_key=wallet.private_key, seconds=120)  # put a lil bit away from queue
                logger.info(f'{datetime.now().time().replace(microsecond=0)} : wallet: {wallet}')
                client = Client(private_key=wallet.private_key, proxy=wallet.proxy)
                controller = Controller(client=client)
            else:
                await asyncio.sleep(delay)
                logger.info('no wallet selected')
                continue

            # Pick an action for selected wallet
            action = await select_random_action(wallet=wallet, controller=controller)
            # if action:  # debug
            #     print(wallet, action)  # debug

            # Check if gas price is OK
            sepolia_action_list = [
                controller.sepolia.deposit_eth_to_hemi, controller.sepolia.bridge_dai_to_hemi,
                controller.sepolia.bridge_usdt_to_hemi, controller.sepolia.bridge_usdc_to_hemi,
                controller.sepolia.faucet_dai, controller.sepolia.faucet_usdc, controller.sepolia.faucet_usdt
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
                    continue  # after 5 tries try to do another wallet

            hemi_action_list = [controller.hemi.create_capsule, controller.hemi.create_safe, controller.hemi.swap]
            if action in hemi_action_list:
                i = 0
                while float(gas_price_hemi.Wei) > Web3.to_wei(settings.maximum_gas_price_hemi, 'gwei') and i < 5:
                    logger.debug(f'Gas price in Hemi is too high'
                                 f'({Web3.from_wei(gas_price_hemi.Wei, "gwei")} > {settings.maximum_gas_price_hemi})')
                    await asyncio.sleep(60 * 1)
                    gas_price_hemi = await client_hemi.transactions.gas_price()
                    i += 1
                if i == 5:
                    continue  # after 5 tries try to do another wallet

            if not action:
                logger.error(f'{wallet} | select_random_action | can not choose the action')
                update_next_action_time(private_key=wallet.private_key, seconds=DELAY_IN_CASE_OF_ERROR)
                continue

            if action == 'Waiting for incoming ETH deposit in Hemi':
                logger.info(f'{wallet} : waiting for incoming ETH deposit in Hemi')
                update_next_action_time(private_key=wallet.private_key, seconds=DELAY_IN_CASE_OF_ERROR)
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

            elif 'Failed' not in status:
                update_next_action_time(
                    private_key=wallet.private_key,
                    seconds=random.randint(settings.activity_actions_delay.from_,
                                           settings.activity_actions_delay.to_)
                )
                logger.success(f'{wallet}: {status}')

                if 'ETH was bridged to Hemi via official bridge' in status:
                    update_today_activity(private_key=wallet.private_key, activity='depositETH')
                    update_next_action_time(private_key=wallet.private_key, seconds=1000)
                if 'stablecoin was bridged to Hemi via official bridge' in status:
                    update_today_activity(private_key=wallet.private_key, activity='depositERC20')
                if 'swapped' in status:
                    update_today_activity(private_key=wallet.private_key, activity='swaps')
                if 'Created capsule' in status:
                    update_today_activity(private_key=wallet.private_key, activity='capsule')
                if 'Created safe' in status:
                    update_today_activity(private_key=wallet.private_key, activity='safe')
                # this appears if autorefill is enabled but wallet ran out of any Ether
                if 'Insufficient balances for refill' in status:
                    logger.error(f'{wallet}: {action}')
                    update_next_action_time(private_key=wallet.private_key, seconds=DELAY_IN_CASE_OF_ERROR)
                    wallet.insufficient_balance = True
                    db.commit()

                # Display next action time
                stmt = (select(func.min(Wallet.next_action_time)).where(
                    or_(Wallet.today_activity_swaps < 2,
                        Wallet.twice_weekly_capsule < 2,
                        Wallet.safe_created.is_(False)
                        )
                )
                )
                next_action_time = db.one(stmt=stmt)
                if next_action_time:
                    logger.info(f'The next closest activity action will be performed at {next_action_time}')
                else:
                    logger.info(f'Seems like all wallets are done for today')

            else:
                update_next_action_time(private_key=wallet.private_key, seconds=DELAY_IN_CASE_OF_ERROR)
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
