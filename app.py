import asyncio

from loguru import logger

from functions.create_files import create_files
from functions.Import import Import
from data.models import Settings, Contracts
from functions.activity import (activity, hourly_check_failed_txs, correct_next_action_time,
                        manual_daily_reset_activities, auto_daily_reset_activities, auto_reset_capsule,
                        fill_queue, first_time_launch_db)
from utils.db_api.wallet_api import get_wallets, display_insufficient_wallets


async def start_script(tasks_num: int = 1):
    settings = Settings()
    if not settings.etherscan_api_key:
        logger.error('Specify the API key for explorer!')
        return

    queue = asyncio.Queue(maxsize=tasks_num)
    activity_tasks = [
        # No need for now, something is wrong with responses (str instead of dict)
        # Later if explorer API for Hemi will work I will implement same for swaps and capsule
        # asyncio.create_task(
        # hourly_check_failed_txs(Contracts.Hemi_Bridge_Sepolia,
        #                        function_names=['depositETH', 'depositERC20'],
        #                       network=Networks.Sepolia)),

        # Every 30 minutes check for done wallets that are late and correct their next action time
        asyncio.create_task(correct_next_action_time()),
        # Once in 24 hours reset swaps and bridges in DB
        asyncio.create_task(auto_daily_reset_activities()),
        # Reset capsule status in DB every 2 days
        asyncio.create_task(auto_reset_capsule()),
        # Constantly refill queue with activity tasks
        asyncio.create_task(fill_queue(queue,tasks_num)),
        # Fill in next action time for newly initialized wallets in DB
        asyncio.create_task(first_time_launch_db()),
    ]

    i = 1
    while i <= tasks_num:
        activity_tasks.append(asyncio.create_task(activity(queue, tasks_num)))
        i += 1
    try:
        await asyncio.wait(activity_tasks)
    except asyncio.exceptions.CancelledError:
        print('Keyboard cancelled?')


if __name__ == '__main__':
    create_files()
    print('''  Select the action:
1) Import wallets from the spreadsheet to the DB;
2) Start the script;
3) Display insufficient wallets
4) Manually reset status of daily activities
5) Exit.''')

    try:
        action = int(input('> '))
        if action == 1:
            asyncio.run(Import.wallets())

        elif action == 2:
            tasks_num = int(input('Enter number of concurrent tasks for activities: '))
            asyncio.run(start_script(tasks_num))

        elif action == 3:
            display_insufficient_wallets()

        elif action == 4:
            manual_daily_reset_activities()

    except asyncio.exceptions.CancelledError:
        print('Keyboard cancelled?')

    except KeyboardInterrupt:
        print()

    except ValueError as err:
        logger.error(f'Value error: {err}')

    except BaseException as e:
        logger.error(f'Something went wrong: {e}')

    finally:
        print('Thank you for using this software!')
