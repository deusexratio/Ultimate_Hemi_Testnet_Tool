import random

from libs.eth_async.client import Client
from tasks.controller import Controller
from data.models import Settings, Contracts
from libs.eth_async.data.models import Networks
from utils.db_api.models import Wallet


async def select_random_action(wallet: Wallet, controller: Controller | None = None):
    settings = Settings()
    possible_actions = []
    weights = []
    # Create Client instances for selected wallet for checking balances
    client_sepolia = Client(private_key=wallet.private_key, network=Networks.Sepolia, proxy=wallet.proxy)
    client_hemi = Client(private_key=wallet.private_key, network=Networks.Hemi_Testnet, proxy=wallet.proxy)
    # in testnet bridge function clients for arb and op specified manually

    eth_balance_sepolia = await client_sepolia.wallet.balance()
    sufficient_balance_eth_sepolia = float(eth_balance_sepolia.Ether) > float(settings.minimal_balance_sepolia)

    eth_balance_hemi = await client_hemi.wallet.balance()
    sufficient_balance_eth_hemi = float(eth_balance_hemi.Ether) > float(settings.minimal_balance_hemi)
    if wallet.today_activity_bridge_eth:
        if not sufficient_balance_eth_hemi:
            return 'Waiting for incoming ETH deposit in Hemi'
        # sufficient_balance_eth_hemi = True
        # kind of hardcode because bridged funds take too much time to get to Hemi

    usdc_balance_sepolia = await client_sepolia.wallet.balance(token=Contracts.Sepolia_USDC)
    dai_balance_sepolia = await client_sepolia.wallet.balance(token=Contracts.Sepolia_DAI)
    usdt_balance_sepolia = await client_sepolia.wallet.balance(token=Contracts.Sepolia_USDT)

    usdc_balance_hemi = await client_hemi.wallet.balance(token=Contracts.Hemi_USDCe)
    dai_balance_hemi = await client_hemi.wallet.balance(token=Contracts.Hemi_DAI)
    usdt_balance_hemi = await client_hemi.wallet.balance(token=Contracts.Hemi_USDTe)

    print(f'{wallet}: '
    f'Balances in Hemi: eth: {eth_balance_hemi.Ether}; usdc: {"{:.2f}".format(float(usdc_balance_hemi.Ether))}; '
    f'dai: {"{:.2f}".format(float(dai_balance_hemi.Ether))}; usdt: {"{:.2f}".format(float(usdt_balance_hemi.Ether))} ||| '
    f'Balances in Sepolia: eth: {eth_balance_sepolia.Ether}; usdc: {"{:.2f}".format(float(usdc_balance_sepolia.Ether))}; '
    f'dai: {"{:.2f}".format(float(dai_balance_sepolia.Ether))}; usdt: {"{:.2f}".format(float(usdt_balance_sepolia.Ether))}')

    if not sufficient_balance_eth_sepolia and not sufficient_balance_eth_hemi:
        if settings.use_autorefill is True:
            action = controller.testnet_bridge.bridge
            return action
        if settings.use_autorefill is False:
            return 'Insufficient balance and not trying to refill'

    # make first faucets random but with probability to bridge eth
    if (usdc_balance_sepolia.Ether < 10000 and usdt_balance_sepolia.Ether < 10000
            and dai_balance_sepolia.Ether < 10000 and not sufficient_balance_eth_hemi):
        possible_actions = [
                controller.sepolia.faucet_usdc,
                controller.sepolia.faucet_usdt,
                controller.sepolia.faucet_dai,
                controller.sepolia.deposit_eth_to_hemi
        ]
        weights = [1, 1, 1, 2]
        action = random.choices(possible_actions, weights=weights)[0]
        return action

    # make first faucets random
    if usdc_balance_sepolia.Ether < 10000 and usdt_balance_sepolia.Ether < 10000 and dai_balance_sepolia.Ether < 10000:
        possible_actions = [
            controller.sepolia.faucet_usdc,
            controller.sepolia.faucet_usdt,
            controller.sepolia.faucet_dai,
        ]
        weights = [1, 1, 1]
        action = random.choices(possible_actions, weights=weights)[0]
        return action


    # make first erc20 bridges to hemi random but with probability to bridge eth
    if (usdc_balance_hemi.Ether < 1000 and usdt_balance_hemi.Ether < 1000
            and dai_balance_hemi.Ether < 1000 and not sufficient_balance_eth_hemi):
        possible_actions = [
            controller.sepolia.bridge_usdc_to_hemi,
            controller.sepolia.bridge_usdt_to_hemi,
            controller.sepolia.bridge_dai_to_hemi,
            controller.sepolia.deposit_eth_to_hemi
        ]
        weights = [1, 1, 1, 2]
        action = random.choices(possible_actions, weights=weights)[0]
        return action

    # make first erc20 bridges to hemi random
    if usdc_balance_hemi.Ether < 1000 and usdt_balance_hemi.Ether < 1000 and dai_balance_hemi.Ether < 1000:
        possible_actions = [
            controller.sepolia.bridge_usdc_to_hemi,
            controller.sepolia.bridge_usdt_to_hemi,
            controller.sepolia.bridge_dai_to_hemi,
        ]
        weights = [1, 1, 1]
        action = random.choices(possible_actions, weights=weights)[0]
        return action

    # refill balances when used
    if usdc_balance_sepolia.Ether < settings.erc20_amount_to_bridge.to_:
        action = controller.sepolia.faucet_usdc
        return action
    if usdt_balance_sepolia.Ether < settings.erc20_amount_to_bridge.to_:
        action = controller.sepolia.faucet_usdt
        return action
    if dai_balance_sepolia.Ether < settings.erc20_amount_to_bridge.to_:
        action = controller.sepolia.faucet_dai
        return action

    # refill balances when used
    if (usdc_balance_hemi.Ether < settings.token_amount_for_swap.to_ or
        usdc_balance_hemi.Ether < settings.token_amount_for_capsule.to_):
        action = controller.sepolia.bridge_usdc_to_hemi
        return action
    if (usdt_balance_hemi.Ether < settings.token_amount_for_swap.to_ or
            usdt_balance_hemi.Ether < settings.token_amount_for_capsule.to_):
        action = controller.sepolia.bridge_usdt_to_hemi
        return action
    if (dai_balance_hemi.Ether < settings.token_amount_for_swap.to_ or
            dai_balance_hemi.Ether < settings.token_amount_for_capsule.to_):
        action = controller.sepolia.bridge_dai_to_hemi
        return action

    # strict refill eth to Hemi
    if not sufficient_balance_eth_hemi:
        action = controller.sepolia.deposit_eth_to_hemi
        return action

    # if nothing is done for today select any action in Hemi
    if wallet.today_activity_swaps < 2 and wallet.twice_weekly_capsule < 2 and wallet.safe_created is False:
        possible_actions = [
            controller.hemi.create_capsule,
            controller.hemi.swap,
            controller.hemi.create_safe
        ]
        weights = [1, 1, 1]
        action = random.choices(possible_actions, weights=weights)[0]
        return action

    if wallet.today_activity_swaps < 2 and wallet.safe_created is False:
        possible_actions = [
            controller.hemi.swap,
            controller.hemi.create_safe
        ]
        weights = [1, 1]
        action = random.choices(possible_actions, weights=weights)[0]
        return action

    if wallet.twice_weekly_capsule < 2 and wallet.safe_created is False:
        possible_actions = [
            controller.hemi.create_capsule,
            controller.hemi.create_safe
        ]
        weights = [1, 1]
        action = random.choices(possible_actions, weights=weights)[0]
        return action

    # same but without safe
    if wallet.today_activity_swaps < 2 and wallet.twice_weekly_capsule < 2:
        possible_actions = [
            controller.hemi.create_capsule,
            controller.hemi.swap,
        ]
        weights = [1, 1]
        action = random.choices(possible_actions, weights=weights)[0]
        return action

    # strict when only one activity left
    if wallet.today_activity_swaps < 2:
        action = controller.hemi.swap
        return action
    if wallet.twice_weekly_capsule < 2:
        action = controller.hemi.create_capsule
        return action
    if wallet.safe_created is False:
        action = controller.hemi.create_safe
        return action

    if possible_actions:
        action = None
        while not action:
            action = random.choices(possible_actions, weights=weights)[0]
        else:
            return action

    return None
