import json
from decimal import Decimal
from dataclasses import dataclass

import requests
from web3 import Web3
from eth_typing import ChecksumAddress


from libs.eth_async import exceptions
from libs.eth_async.data import config
# from data.models import Settings
from libs.eth_async.classes import AutoRepr
from libs.eth_async.blockscan_api import APIFunctions


class TxStatus:
    Error: bool
    ErrDescription: str

    def __init__(self, status: str, error: str | None) -> None:
        if status == '0':
            self.Error: bool = False
        else:
            self.Error: bool = True

        if error:
            self.ErrDescription: str = error
        else:
            self.ErrDescription: None = None

    def __bool__(self):
        return f'{self.Error}'

    def __repr__(self):
        return f'{self.Error}'


class TokenAmount:
    Wei: int
    Ether: Decimal
    decimals: int

    def __init__(self, amount: int | float | str | Decimal, decimals: int = 18, wei: bool = False) -> None:
        if wei:
            self.Wei: int = int(amount)
            self.Ether: Decimal = Decimal(str(amount)) / 10 ** decimals

        else:
            self.Wei: int = int(Decimal(str(amount)) * 10 ** decimals)
            self.Ether: Decimal = Decimal(str(amount))

        self.decimals = decimals

    def __str__(self):
        return f'{self.Wei}'


@dataclass
class DefaultABIs:
    Token = [
        {
            'constant': True,
            'inputs': [],
            'name': 'name',
            'outputs': [{'name': '', 'type': 'string'}],
            'payable': False,
            'stateMutability': 'view',
            'type': 'function'
        },
        {
            'constant': True,
            'inputs': [],
            'name': 'symbol',
            'outputs': [{'name': '', 'type': 'string'}],
            'payable': False,
            'stateMutability': 'view',
            'type': 'function'
        },
        {
            'constant': True,
            'inputs': [],
            'name': 'totalSupply',
            'outputs': [{'name': '', 'type': 'uint256'}],
            'payable': False,
            'stateMutability': 'view',
            'type': 'function'
        },
        {
            'constant': True,
            'inputs': [],
            'name': 'decimals',
            'outputs': [{'name': '', 'type': 'uint256'}],
            'payable': False,
            'stateMutability': 'view',
            'type': 'function'
        },
        {
            'constant': True,
            'inputs': [{'name': 'account', 'type': 'address'}],
            'name': 'balanceOf',
            'outputs': [{'name': '', 'type': 'uint256'}],
            'payable': False,
            'stateMutability': 'view',
            'type': 'function'
        },
        {
            'constant': True,
            'inputs': [{'name': 'owner', 'type': 'address'}, {'name': 'spender', 'type': 'address'}],
            'name': 'allowance',
            'outputs': [{'name': 'remaining', 'type': 'uint256'}],
            'payable': False,
            'stateMutability': 'view',
            'type': 'function'
        },
        {
            'constant': False,
            'inputs': [{'name': 'spender', 'type': 'address'}, {'name': 'value', 'type': 'uint256'}],
            'name': 'approve',
            'outputs': [],
            'payable': False,
            'stateMutability': 'nonpayable',
            'type': 'function'
        },
        {
            'constant': False,
            'inputs': [{'name': 'to', 'type': 'address'}, {'name': 'value', 'type': 'uint256'}],
            'name': 'transfer',
            'outputs': [], 'payable': False,
            'stateMutability': 'nonpayable',
            'type': 'function'
        }]


@dataclass
class API:
    """
    An instance that contains an API related information.

    Attributes:
        key (str): an API-key.
        url (str): an API entrypoint URL.
        docs (str): a docs URL.
        functions (Optional[APIFunctions]): the functions instance.

    """
    url: str
    key: str | None = None
    docs: str | None = None
    functions: APIFunctions | None = None


class Network:
    def __init__(
            self,
            name: str,
            rpc: str,
            decimals: int | None = None,
            chain_id: int | None = None,
            tx_type: int = 0,
            coin_symbol: str | None = None,
            explorer: str | None = None,
            api: API | None = None,
    ) -> None:
        self.name: str = name.lower()
        self.rpc: str = rpc
        self.chain_id: int | None = chain_id
        self.tx_type: int = tx_type
        self.coin_symbol: str | None = coin_symbol
        self.explorer: str | None = explorer
        self.decimals = decimals
        self.api = api

        if not self.chain_id:
            try:
                self.chain_id = Web3(Web3.HTTPProvider(self.rpc)).eth.chain_id
            except Exception as err:
                raise exceptions.WrongChainID(f'Can not get chain id: {err}')

        if not self.coin_symbol or not self.decimals:
            try:
                network = None
                networks_info_response = requests.get('https://chainid.network/chains.json').json()
                for network_ in networks_info_response:
                    if network_['chainId'] == self.chain_id:
                        network = network_
                        break

                if not self.coin_symbol:
                    self.coin_symbol = network['nativeCurrency']['symbol']
                if not self.decimals:
                    self.decimals = int(network['nativeCurrency']['decimals'])

            except Exception as err:
                raise exceptions.WrongCoinSymbol(f'Can not get coin symbol: {err}')

        if self.coin_symbol:
            self.coin_symbol = self.coin_symbol.upper()

        self.set_api_functions()

    def set_api_functions(self) -> None:
        """
        Update API functions after API key change.
        """
        if self.api and self.api.key and self.api.url:
            self.api.functions = APIFunctions(self.api.key, self.api.url)


class Networks:
    Arbitrum = Network(
        name='arbitrum',
        rpc='https://rpc.ankr.com/arbitrum/',
        chain_id=42161,
        tx_type=2,
        coin_symbol='ETH',
        decimals=18,
        explorer='https://arbiscan.io/',
        api=API(
            key=..., url='https://api.arbiscan.io/api', # config.ARBISCAN_API_KEY
            docs='https://docs.arbiscan.io'
        )
    )

    Optimism = Network(
        name='optimism',
        rpc='https://rpc.ankr.com/optimism/',
        chain_id=10,
        tx_type=2,
        coin_symbol='ETH',
        decimals=18,
        explorer='https://optimistic.etherscan.io/',
        api=API(
            key=..., url='https://api-optimistic.etherscan.io/api', # config.OPTIMISTIC_API_KEY
            docs='https://docs.optimistic.etherscan.io/'
        )
    )
    # Testnets
    Sepolia = Network(
        name='sepolia',
        rpc='https://sepolia.infura.io/v3/25641334b82b45889bcc941d4df6c75a',
        chain_id=11155111,
        tx_type=2,
        coin_symbol='ETH',
        decimals=18,
        explorer='https://sepolia.etherscan.io',
        api=API(
            key=config.ETHERSCAN_API_KEY, url='https://api-sepolia.etherscan.io/api',
            docs='https://docs.etherscan.io/v/sepolia-etherscan/'
        )
    )

    Hemi_Testnet = Network(
        name='hemi testnet',
        rpc='https://testnet.rpc.hemi.network/rpc',
        chain_id=743111,
        tx_type=2,  # по сканеру 2, но многие транзы уходят с 0
        coin_symbol='ETH',
        decimals=18,
        explorer='https://testnet.explorer.hemi.xyz',
        api=API(
            key=..., url='https://testnet.explorer.hemi.xyz/api/v2/',
            docs='https://testnet.explorer.hemi.xyz/api-docs'
        )
    )


class RawContract(AutoRepr):
    """
    An instance of a raw contract.

    Attributes:
        title str: a contract title.
        address (ChecksumAddress): a contract address.
        abi list[dict[str, Any]] | str: an ABI of the contract.

    """
    title: str
    address: ChecksumAddress
    abi: list[dict[str, ...]]
    decimals: int

    def __init__(self, address: str, abi: list[dict[str, ...]] | str | None = None,
                 title: str = '',
                 decimals: int = 18) -> None:
        """
        Initialize the class.

        Args:
            title (str): a contract title.
            address (str): a contract address.
            abi (Union[List[Dict[str, Any]], str]): an ABI of the contract.
            decimals (int): token decimals, by default 18
        """
        self.title = title
        self.address = Web3.to_checksum_address(address)
        self.abi = json.loads(abi) if isinstance(abi, str) else abi
        self.decimals = decimals

    def __eq__(self, other) -> bool:
        if self.address == other.address and self.abi == other.abi:
            return True
        return False


@dataclass
class CommonValues:
    """
    An instance with common values used in transactions.
    """
    Null: str = '0x0000000000000000000000000000000000000000000000000000000000000000'
    InfinityStr: str = '0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff'
    InfinityInt: int = int('0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff', 16)


class TxArgs(AutoRepr):
    """
    An instance for named transaction arguments.
    """

    def __init__(self, **kwargs) -> None:
        """
        Initialize the class.

        Args:
            **kwargs: named arguments of a contract transaction.

        """
        self.__dict__.update(kwargs)

    def list(self) -> list[...]:
        """
        Get list of transaction arguments.

        Returns:
            List[Any]: list of transaction arguments.

        """
        return list(self.__dict__.values())

    def tuple(self) -> tuple[str, ...]:
        """
        Get tuple of transaction arguments.

        Returns:
            Tuple[Any]: tuple of transaction arguments.

        """
        return tuple(self.__dict__.values())
