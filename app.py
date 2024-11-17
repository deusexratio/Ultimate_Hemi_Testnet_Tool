import asyncio
import time

from loguru import logger

from functions.create_files import create_files
from functions.Import import Import
from data.models import Settings
from functions.activity_utils import (hourly_check_failed_txs, correct_next_action_time,
                                manual_daily_reset_activities, auto_daily_reset_activities, auto_reset_capsule,
                                fill_queue, first_time_launch_db, check_today_tx_status, clear_past_failed_txs)
from functions.activity import activity
from utils.db_api.wallet_api import display_insufficient_wallets, display_current_stats


async def start_script(tasks_num: int = 1):
    settings = Settings()
    if not settings.etherscan_api_key:
        logger.error('Specify the API key for explorer!')
        return
    try:
        activity_tasks = []
        queue = asyncio.Queue(maxsize=tasks_num)
        activity_tasks = [
            # No need for now, something is wrong with responses (str instead of dict)
            # Later if explorer API for Hemi will work I will implement same for swaps and capsule
            # asyncio.create_task(
            # hourly_check_failed_txs(Contracts.Hemi_Bridge_Sepolia,
            #                        function_names=['depositETH', 'depositERC20'],
            #                       network=Networks.Sepolia)),

            # Every 30 minutes check for done wallets that are late and correct their next action time
            # asyncio.create_task(correct_next_action_time()),
            # Once in 24 hours reset swaps and bridges in DB
            asyncio.create_task(auto_daily_reset_activities()),
            # Reset capsule status in DB every 2 days
            asyncio.create_task(auto_reset_capsule()),
            # Constantly refill queue with activity tasks
            asyncio.create_task(fill_queue(queue,tasks_num)),
            # Fill in next action time for newly initialized wallets in DB
            asyncio.create_task(first_time_launch_db()),
            # Recheck at the end of the day transaction statuses
            asyncio.create_task(check_today_tx_status()),
            # Delete yesterday failed txs from DB to not overload it
            asyncio.create_task(clear_past_failed_txs()),
        ]

        for _ in range(0, tasks_num):
            activity_tasks.append(asyncio.create_task(activity(queue)))

        await asyncio.wait(activity_tasks)
    except asyncio.exceptions.CancelledError:
        print('Keyboard cancelled?')
        for task in activity_tasks:
            task.cancel()


if __name__ == '__main__':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    create_files()
    try:
        while True:
            print('''  Select the action:
        1) Import wallets from the spreadsheet to the DB;
        2) Start the script;
        3) Display insufficient wallets
        4) Manually reset status of daily activities
        5) Display current stats
        6) Manually recheck today transactions
        7) Exit.''')
            match int(input('> ')):
                case 1:
                    asyncio.run(Import.wallets())
                    time.sleep(3)
                    continue
                case 2:
                    tasks_num = int(input('Enter number of concurrent tasks for activities: '))
                    asyncio.run(start_script(tasks_num))
                    break
                case 3:
                    display_insufficient_wallets()
                    time.sleep(1)
                    continue
                case 4:
                    manual_daily_reset_activities()
                    time.sleep(1)
                    continue
                case 5:
                    display_current_stats()
                    time.sleep(1)
                    continue
                case 6:
                    asyncio.run(check_today_tx_status(manual=True))
                    time.sleep(1)
                    continue
                case _:
                    break

    except (asyncio.exceptions.CancelledError, KeyboardInterrupt):
        print('Keyboard cancelled?')

    except ValueError as err:
        logger.error(f'Value error: {err}')

    except BaseException as e:
        logger.error(f'Something went wrong: {e}')

    finally:
        print('Thank you for using this software!')
