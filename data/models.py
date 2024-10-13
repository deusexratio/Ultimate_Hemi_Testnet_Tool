import json
from dataclasses import dataclass

from libs.eth_async.utils.files import read_json
from libs.eth_async.classes import AutoRepr, Singleton
from libs.eth_async.data.models import RawContract, DefaultABIs

from data.config import SETTINGS_FILE, ABIS_DIR


@dataclass
class WalletCSV:
    header = ['private_key', 'proxy', 'name']

    def __init__(self, private_key: str,
                 proxy: str = '', name: str = ''):
        self.private_key = private_key
        self.proxy = proxy
        self.name = name


@dataclass
class FromTo:
    from_: int | float
    to_: int | float


# class OkxModel:
#     required_minimum_balance: float
#     withdraw_amount: FromTo
#     delay_between_withdrawals: FromTo
#     credentials: OKXCredentials


class Settings(Singleton, AutoRepr):
    def __init__(self):
        json_data = read_json(path=SETTINGS_FILE)

        self.maximum_gas_price_sepolia: int = json_data['maximum_gas_price_sepolia']
        self.maximum_gas_price_hemi: int = json_data['maximum_gas_price_hemi']
        self.etherscan_api_key: str = json_data['etherscan_api_key']
        self.minimal_balance_sepolia: float = json_data['minimal_balance_sepolia']
        self.use_autorefill: bool = json_data['use_autorefill']
        self.autorefill_amount: FromTo = FromTo(
            from_=json_data['autorefill_amount']['from'], to_=json_data['autorefill_amount']['to']
        )
        self.token_amount_for_capsule: FromTo = FromTo(
            from_=json_data['token_amount_for_capsule']['from'], to_=json_data['token_amount_for_capsule']['to']
        )
        self.token_amount_for_swap: FromTo = FromTo(
            from_=json_data['token_amount_for_swap']['from'], to_=json_data['token_amount_for_swap']['to']
        )
        self.eth_amount_for_swap: FromTo = FromTo(
            from_=json_data['eth_amount_for_swap']['from'], to_=json_data['eth_amount_for_swap']['to']
        )
        self.activity_actions_delay: FromTo = FromTo(
            from_=json_data['activity_actions_delay']['from'], to_=json_data['activity_actions_delay']['to']
        )
        self.eth_amount_for_bridge: FromTo = FromTo(
            from_=json_data['eth_amount_for_bridge']['from'], to_=json_data['eth_amount_for_bridge']['to']
        )
        self.erc20_amount_to_bridge: FromTo = FromTo(
            from_=json_data['erc20_amount_to_bridge']['from'], to_=json_data['erc20_amount_to_bridge']['to']
        )
        # self.stable_faucet_amount: FromTo = FromTo(
        #     from_=json_data['stable_faucet_amount']['from'], to_=json_data['stable_faucet_amount']['to']
        # )




class Contracts(Singleton):
    # Both Arb and Op
    Sepolia_Ether = RawContract(
        title='seth',
        address='0xe71bdfe1df69284f00ee185cf0d95d0c7680c0d4',
        abi=DefaultABIs.Token,
        decimals=18
    )

    # Optimism
    Testnet_Bridge_Optimism = RawContract(
        title='testnet bridge',
        address='0x8352C746839699B1fc631fddc0C3a00d4AC71A17',
        abi=read_json(path=(ABIS_DIR, 'testnet_bridge.json'))
    )

    # Arbitrum
    Testnet_Bridge_Arbitrum = RawContract(
        title='testnet bridge',
        address='0xfcA99F4B5186D4bfBDbd2C542dcA2ecA4906BA45',
        abi=read_json(path=(ABIS_DIR, 'testnet_bridge.json'))
    )

    # Sepolia
    Hemi_Bridge_Sepolia = RawContract(
        title='hemi bridge',
        address='0xc94b1BEe63A3e101FE5F71C80F912b4F4b055925',
        abi=read_json(path=(ABIS_DIR, 'hemi_bridge_sepolia.json'))
    )

    Aave_Faucet = RawContract(
        title='aave faucet',
        address='0xC959483DBa39aa9E78757139af0e9a2EDEb3f42D',
        abi=read_json(path=(ABIS_DIR, 'faucet.json'))
    )

    Sepolia_USDT = RawContract(
        title='sepolia USDT',
        address='0xaA8E23Fb1079EA71e0a56F48a2aA51851D8433D0',
        abi=DefaultABIs.Token,
        decimals=6
    )

    Sepolia_USDC = RawContract(
        title='sepolia USDC',
        address='0x94a9D9AC8a22534E3FaCa9F4e7F2E2cf85d5E4C8',
        abi=DefaultABIs.Token,
        decimals=6
    )

    Sepolia_DAI = RawContract(
        title='sepolia DAI',
        address='0xFF34B3d4Aee8ddCd6F9AFFFB6Fe49bD371b8a357',
        abi=DefaultABIs.Token,
        decimals=18
    )

    # Hemi
    Hemi_USDTe = RawContract(
        title='Hemi USDT.e',
        address='0x3Adf21A6cbc9ce6D5a3ea401E7Bae9499d391298',
        abi=DefaultABIs.Token,
        decimals=6
    )

    Hemi_USDCe = RawContract(
        title='Hemi USDC.e',
        address='0xD47971C7F5B1067d25cd45d30b2c9eb60de96443',
        abi=DefaultABIs.Token,
        decimals=6
    )

    Hemi_DAI = RawContract(
        title='Hemi DAI',
        address='0xec46E0EFB2EA8152da0327a5Eb3FF9a43956F13e',
        abi=DefaultABIs.Token,
        decimals=18
    )

    Hemi_WETH = RawContract(
        title='Hemi WETH',
        address='0x0c8afd1b58aa2a5bad2414b861d8a7ff898edc3a',
        abi=DefaultABIs.Token,
        decimals=18
    )

    Hemi_Capsule = RawContract(
        title='TransparentUpgradeableProxy',
        address='0x1E8db2Fc15Bf1207784763219e00e98D0BA82362',
        abi=read_json(path=(ABIS_DIR, 'capsule.json'))
    )

    Hemi_Swap = RawContract(
        title='Swap',
        address='0xA18019E62f266C2E17e33398448e4105324e0d0F',
        abi=read_json(path=(ABIS_DIR, 'swap.json'))
    )

    Gnosis_Safe = RawContract(
        title='Safe',
        address='0xa6B71E26C5e0845f74c812102Ca7114b6a896AB2',
        abi=read_json(path=(ABIS_DIR, 'safe.json'))
    )
