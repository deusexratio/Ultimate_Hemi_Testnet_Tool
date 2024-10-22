from __future__ import annotations

import random
from datetime import datetime
from typing import TYPE_CHECKING, Any

from eth_typing import HexStr
from hexbytes import HexBytes

from web3 import Web3, AsyncWeb3
from web3.contract import AsyncContract
from web3.middleware import geth_poa_middleware
from web3.types import TxReceipt, _Hash32, TxParams, ENS
from web3.exceptions import TimeExhausted
from eth_account.datastructures import SignedTransaction, SignedMessage
from eth_account.messages import encode_defunct
from eth_account.account import Account
from uniswap_universal_router_decoder import RouterCodec


from .data import types
from .exceptions import TransactionException
from .classes import AutoRepr
from .utils.utils import api_key_required
from .data.models import TokenAmount, CommonValues, TxArgs, Networks, RawContract

if TYPE_CHECKING:
    from .client import Client


class Tx(AutoRepr):
    """
    An instance of transaction for easy execution of actions on it.

    Attributes:
        hash (Optional[_Hash32]): a transaction hash.
        params (Optional[dict]): the transaction parameters.
        receipt (Optional[TxReceipt]): a transaction receipt.
        function_identifier (Optional[str]): a function identifier.
        input_data (Optional[Dict[str, Any]]): an input data.

    """
    hash: _Hash32 | None
    params: dict | None
    receipt: TxReceipt | None
    function_identifier: str | None
    input_data: dict[str, Any] | None

    def __init__(self, tx_hash: str | _Hash32 | None = None, params: dict | None = None) -> None:
        """
        Initialize the class.

        Args:
            tx_hash (Optional[Union[str, _Hash32]]): the transaction hash. (None)
            params (Optional[dict]): a dictionary with transaction parameters. (None)

        """
        if not tx_hash and not params:
            raise TransactionException("Specify 'tx_hash' or 'params' argument values!")

        if isinstance(tx_hash, str):
            tx_hash = HexBytes(tx_hash)

        self.hash = tx_hash
        self.params = params
        self.receipt = None
        self.function_identifier = None
        self.input_data = None

    async def parse_params(self, client) -> dict[str, Any]:
        """
        Parse the parameters of a sent transaction.

        Args:
            client (Client): the Client instance.

        Returns:
            Dict[str, Any]: the parameters of a sent transaction.

        """
        tx_data = await client.w3.eth.get_transaction(transaction_hash=self.hash)
        self.params = {
            'chainId': client.network.chain_id,
            'nonce': int(tx_data.get('nonce')),
            'gasPrice': int(tx_data.get('gasPrice')),
            'gas': int(tx_data.get('gas')),
            'from': tx_data.get('from'),
            'to': tx_data.get('to'),
            'data': tx_data.get('input'),
            'value': int(tx_data.get('value'))
        }
        return self.params

    async def wait_for_receipt(
            self, client, timeout: int | float = 120, poll_latency: float = 0.1
    ) -> dict[str, Any]:
        """
        Wait for the transaction receipt.

        Args:
            client (Client): the Client instance.
            timeout (Union[int, float]): the receipt waiting timeout. (120 sec)
            poll_latency (float): the poll latency. (0.1 sec)

        Returns:
            Dict[str, Any]: the transaction receipt.

        """
        self.receipt = await client.transactions.wait_for_receipt(
            w3=client.w3,
            tx_hash=self.hash,
            timeout=timeout,
            poll_latency=poll_latency
        )
        return self.receipt

    async def decode_input_data(self):
        pass

    async def cancel(self, client: Client) -> dict[str, Any] | bool:
        # needs testing
        try:
            cancel_tx_params = {
                'chainId': client.network.chain_id,
                'nonce': self.params['nonce'],
                'gasPrice': self.params['gasPrice'] * 2,  # Увеличиваем цену на газ для приоритета
                'gas': self.params['gas'],
                'from': self.params['from'],
                'to': self.params['from'],  # Отправляем на свой же адрес
                'value': 0,  # Нулевой перевод
            }
            tx = TxParams(cancel_tx_params)
            replacement_tx = await client.transactions.sign_and_send(tx_params=tx)
            receipt = await replacement_tx.wait_for_receipt(client=client, timeout=20)
            return receipt
        except TransactionException as e:
            return False

    async def speed_up(self, client: Client) -> dict[str, Any] | bool:
        # inputs client and Tx (self)
        # needs testing
        try:
            self.params['gasPrice'] = self.params['gasPrice'] * 1.103
            tx_params = TxParams(self.params)
            replacement_tx = await client.transactions.sign_and_send(tx_params=tx_params)
            receipt = await replacement_tx.wait_for_receipt(client=client, timeout=20)
            return receipt
        except TransactionException as e:
            return False


class Transactions:
    def __init__(self, client: Client) -> None:
        self.client = client

    async def gas_price(self) -> TokenAmount:
        """
        Get the current gas price
        :return: gas price
        """
        return TokenAmount(amount=await self.client.w3.eth.gas_price, wei=True, decimals=self.client.network.decimals)

    async def max_priority_fee(self, block: dict | None = None) -> TokenAmount:
        w3 = Web3(provider=Web3.HTTPProvider(endpoint_uri=self.client.network.rpc))
        w3.middleware_onion.inject(geth_poa_middleware, layer=0)

        if not block:
            block = w3.eth.get_block('latest')

        block_number = block['number']
        latest_block_transaction_count = w3.eth.get_block_transaction_count(block_number)
        max_priority_fee_per_gas_lst = []
        for i in range(latest_block_transaction_count):
            try:
                transaction = w3.eth.get_transaction_by_block(block_number, i)
                if 'maxPriorityFeePerGas' in transaction:
                    max_priority_fee_per_gas_lst.append(transaction['maxPriorityFeePerGas'])
            except Exception:
                continue

        if not max_priority_fee_per_gas_lst:
            # max_priority_fee_per_gas = w3.eth.max_priority_fee
            max_priority_fee_per_gas = 0
        else:
            max_priority_fee_per_gas_lst.sort()
            max_priority_fee_per_gas = max_priority_fee_per_gas_lst[len(max_priority_fee_per_gas_lst) // 2]
        return TokenAmount(amount=max_priority_fee_per_gas, wei=True, decimals=self.client.network.decimals)

    async def max_priority_fee_(self) -> TokenAmount:
        """
        Get the current max priority fee.

        Returns:
            Wei: the current max priority fee.

        """
        return TokenAmount(amount=await self.client.w3.eth.max_priority_fee, wei=True,
                           decimals=self.client.network.decimals)

    async def estimate_gas(self, tx_params: TxParams) -> TokenAmount:
        """
        Get the estimate gas limit for a transaction with specified parameters.

        Args:
            tx_params (TxParams): parameters of the transaction.

        Returns:
            Wei: the estimate gas.

        """
        try:
            gas = TokenAmount(
                amount=await self.client.w3.eth.estimate_gas(transaction=tx_params),
                wei=True,
                decimals=self.client.network.decimals
            )
            if type(gas) is not TokenAmount:
                raise AttributeError('gas is not TokenAmount')
            return gas
        except:
            ValueError('max gas reached')

    async def auto_add_params(self, tx_params: TxParams) -> TxParams:
        """
        Add 'chainId', 'nonce', 'from', 'gasPrice' or 'maxFeePerGas' + 'maxPriorityFeePerGas' and 'gas' parameters to
            transaction parameters if they are missing.

        Args:
            tx_params (TxParams): parameters of the transaction.

        Returns:
            TxParams: parameters of the transaction with added values.

        """
        try:
            if 'chainId' not in tx_params:
                tx_params['chainId'] = self.client.network.chain_id

            if not tx_params.get('nonce'):
                tx_params['nonce'] = await self.client.wallet.nonce()

            if 'from' not in tx_params:
                tx_params['from'] = self.client.account.address

            if 'gasPrice' not in tx_params and 'maxFeePerGas' not in tx_params:
                gas_price = (await self.gas_price()).Wei
                if self.client.network.tx_type == 2:
                    tx_params['maxFeePerGas'] = gas_price
                    # todo: check

                else:
                    tx_params['gasPrice'] = gas_price

            elif 'gasPrice' in tx_params and not int(tx_params['gasPrice']):
                tx_params['gasPrice'] = (await self.gas_price()).Wei

            if 'maxFeePerGas' in tx_params and 'maxPriorityFeePerGas' not in tx_params:
                # tx_params['maxFeePerGas'] = await self.client.w3.eth.max_priority_fee + Web3.to_wei(2, "gwei")
                # tx_params['maxPriorityFeePerGas'] = await self.client.w3.eth.max_priority_fee + Web3.to_wei(2, "gwei")
                tx_params['maxPriorityFeePerGas'] = (await self.max_priority_fee()).Wei
                tx_params['maxFeePerGas'] = tx_params['maxFeePerGas'] + tx_params['maxPriorityFeePerGas']
            try:
                if 'gas' not in tx_params or not int(tx_params['gas']):
                    if self.client.network == Networks.Hemi_Testnet:
                        # tx_params['gas'] = random.randint(190000, 200000) # hardcode for hemi testnet
                        tx_params['gas'] = int((await self.estimate_gas(tx_params=tx_params)).Wei * 1.5)
                    else:
                        tx_params['gas'] = (await self.estimate_gas(tx_params=tx_params)).Wei

            except KeyError as e:
                print(tx_params)
                print(f'{e}: got wrong response (need "gas" key in tx_params) probably failed to count gas')

            return tx_params
        except AttributeError as e:
            print(f'{e}:got wrong response (need "gas" key in tx_params) probably failed to count gas')
            # print(tx_params)


    async def sign_transaction(self, tx_params: TxParams) -> SignedTransaction:
        """
        Sign a transaction.

        Args:
            tx_params (TxParams): parameters of the transaction.

        Returns:
            SignedTransaction: the signed transaction.

        """
        return self.client.w3.eth.account.sign_transaction(
            transaction_dict=tx_params, private_key=self.client.account.key
        )

    async def sign_and_send(self, tx_params: TxParams) -> Tx | str |  None:
        """
        Sign and send a transaction. Additionally, add 'chainId', 'nonce', 'from', 'gasPrice' or
            'maxFeePerGas' + 'maxPriorityFeePerGas' and 'gas' parameters to transaction parameters if they are missing.

        Args:
            tx_params (TxParams): parameters of the transaction.

        Returns:
            Tx: the instance of the sent transaction.

        """

        auto_added_params = await self.auto_add_params(tx_params=tx_params)
        if auto_added_params is None:
            return None


        signed_tx = await self.sign_transaction(tx_params)
        try:
            tx_hash = await self.client.w3.eth.send_raw_transaction(transaction=signed_tx.rawTransaction)
        except ValueError as e:
            return f'{self.client.account.address} : {e}'

        return Tx(tx_hash=tx_hash, params=tx_params)

    async def approved_amount(
            self, token: types.Contract, spender: types.Contract, owner: types.Address | None = None
    ) -> TokenAmount:
        """
        Get approved amount of token.

        Args:
            token (Contract): the contract address or instance of token.
            spender (Contract): the spender address, contract address or instance.
            owner (Optional[Address]): the owner address. (imported to client address)

        Returns:
            TokenAmount: the approved amount.

        """
        contract_address, abi = await self.client.contracts.get_contract_attributes(token)
        contract = await self.client.contracts.default_token(contract_address)
        spender, abi = await self.client.contracts.get_contract_attributes(spender)
        if not owner:
            owner = self.client.account.address

        return TokenAmount(
            amount=await contract.functions.allowance(
                Web3.to_checksum_address(owner),
                Web3.to_checksum_address(spender)
            ).call(),
            decimals=await self.client.transactions.get_decimals(contract=contract.address),
            wei=True
        )

    @staticmethod
    async def wait_for_receipt(
            w3: Web3 | AsyncWeb3, tx_hash: str | _Hash32, timeout: int | float = 120, poll_latency: float = 0.1
    ) -> dict[str, Any]:
        """
        Wait for a transaction receipt.

        Args:
            w3: web3 object
            tx_hash (Union[str, _Hash32]): the transaction hash.
            timeout (Union[int, float]): the receipt waiting timeout. (120)
            poll_latency (float): the poll latency. (0.1 sec)

        Returns:
            Dict[str, Any]: the transaction receipt.

        """
        try:
            return dict(await w3.eth.wait_for_transaction_receipt(
                transaction_hash=tx_hash, timeout=timeout, poll_latency=poll_latency
            ))
        except TimeExhausted:
            return {}

    async def approve(
            self, token: types.Contract, spender: types.Address, amount: types.Amount | None = None,
            gas_limit: types.GasLimit | None = None, nonce: int | None = None
    ) -> Tx:
        """
        Approve token spending for specified address.

        Args:
            token (Contract): the contract address or instance of token to approve.
            spender (Address): the spender address, contract address or instance.
            amount (Optional[TokenAmount]): an amount to approve. (infinity)
            gas_limit (Optional[GasLimit]): the gas limit in Wei. (parsed from the network)
            nonce (Optional[int]): a nonce of the sender address. (get it using the 'nonce' function)

        Returns:
            Tx: the instance of the sent transaction.
        """
        spender = Web3.to_checksum_address(spender)
        contract_address, abi = await self.client.contracts.get_contract_attributes(token)
        contract = await self.client.contracts.default_token(contract_address)

        if amount is None:
            amount = CommonValues.InfinityInt
        elif isinstance(amount, (int, float)):
            amount = TokenAmount(
                amount=amount,
                decimals=await self.client.transactions.get_decimals(contract=contract.address)
            ).Wei
        else:
            amount = amount.Wei

        tx_args = TxArgs(
            spender=spender,
            amount=amount
        )

        tx_params = {
            'nonce': nonce,
            'to': contract.address,
            'data': contract.encodeABI('approve', args=tx_args.tuple())
        }

        if gas_limit:
            if isinstance(gas_limit, int):
                gas_limit = TokenAmount(amount=gas_limit, wei=True)
            tx_params['gas'] = gas_limit.Wei

        return await self.sign_and_send(tx_params=tx_params)

    async def get_decimals(self, contract: types.Contract) -> int:
        contract_address, abi = await self.client.contracts.get_contract_attributes(contract)
        contract = await self.client.contracts.default_token(contract_address=contract_address)
        return await contract.functions.decimals().call()

    async def sign_message(self, message: str) -> SignedMessage:
            """
            Sign message

            Args:
            message: str

            Returns:
                SignedMessage
            """

            msghash = encode_defunct(text=message)
            return self.client.w3.eth.account.sign_message(signable_message=msghash,
                                                           private_key=self.client.account.key)

    async def permit2_allowance(self, permit2_address: types.Address,
                                    router_address: types.Address,
                                    token_address: types.Address,
                                    permit2_abi: list) -> tuple[Any, Any, Any]:
        """
        Fetch amount of allowance, expiration timestamp of allowance and permit2 message nonce
        for specified permit2, router and token addresses

        Args:
            permit2_address:
            router_address:
            token_address:
            permit2_abi:

        Returns:
            p2_amount, p2_expiration, p2_nonce
        """
        permit2_contract = self.client.w3.eth.contract(address=permit2_address, abi=permit2_abi)
        p2_amount, p2_expiration, p2_nonce = await permit2_contract.functions.allowance(
            self.client.account.address,
            token_address,
            router_address
        ).call()
        return p2_amount, p2_expiration, p2_nonce

    async def get_permit2_data(self, permit2: types.Contract,
                                    router: types.Contract,
                                    token: types.Contract,
                                    permit2_abi: list) -> tuple[dict, Any] | None:
        """
        Gets permit_data, signed_message via RouterCodec

        Args:
            permit2:
            router:
            token:
            permit2_abi:

        Returns:
            permit_data, signed_message
        """
        if isinstance(permit2, str):
            permit2_address = Web3.to_checksum_address(permit2)
        elif isinstance(permit2, (RawContract, AsyncContract)):
            permit2_address = permit2.address
        else:
            permit2_address = permit2

        if isinstance(router, str):
            router_address = Web3.to_checksum_address(router)
        elif isinstance(router, (RawContract, AsyncContract)):
            router_address = router.address
        else:
            router_address = router

        if isinstance(token, str):
            token_address = Web3.to_checksum_address(token)
        elif isinstance(token, (RawContract, AsyncContract)):
            token_address = token.address
        else:
            token_address = token

        p2_amount, p2_expiration, p2_nonce = await self.permit2_allowance(permit2_address=permit2_address,
                                                                            router_address=router_address,
                                                                            token_address=token_address,
                                                                            permit2_abi=permit2_abi)
        if p2_amount > 0 and p2_expiration > int(datetime.now().timestamp()):
            permit_data = {}
            signed_message = ''
            return permit_data, signed_message
            # todo: убрать костыль?

        codec = RouterCodec()
        allowance_amount = 2 ** 160 - 1  # max/infinite
        permit_data, signable_message = codec.create_permit2_signable_message(
            token_address,
            allowance_amount,
            codec.get_default_expiration(),  # 30 days
            p2_nonce,
            router_address,
            codec.get_default_deadline(),  # 180 seconds
            self.client.network.chain_id,
        )
        signed_message = self.client.w3.eth.account.sign_message(signable_message=signable_message,
                                                           private_key=self.client.account.key)
        return permit_data, signed_message


    @staticmethod
    async def decode_input_data():
        pass

    @api_key_required
    async def find_txs(
            self, contract: types.Contract | list[types.Contract], function_name: str | None = '',
            address: types.Address | None = None, after_timestamp: int = 0, before_timestamp: int = 999_999_999_999,
            is_error: str = '0'
    ) -> dict[str, ...]:
        """
        Find all transactions of interaction with the contract, in addition, you can filter transactions by
            the name of the contract function.

        Args:
            contract (Union[Contract, List[Contract]]): the contract or a list of contracts with which
                the interaction took place.
            function_name (Optional[str]): the function name for sorting. (any)
            address (Optional[Address]): the address to get the transaction list. (imported to client address)
            after_timestamp (int): after what time to filter transactions. (0)
            before_timestamp (int): before what time to filter transactions. (infinity)

        Returns:
            Dict[str, CoinTx]: transactions found.

        """
        contract_addresses = []
        if isinstance(contract, list):
            for contract_ in contract:
                contract_address, abi = await self.client.contracts.get_contract_attributes(contract_)
                contract_addresses.append(contract_address.lower())

        else:
            contract_address, abi = await self.client.contracts.get_contract_attributes(contract)
            contract_addresses.append(contract_address.lower())

        if not address:
            address = self.client.account.address
        try:
            txs = {}
            coin_txs = (await self.client.network.api.functions.account.txlist(address))['result']
            # print(coin_txs)
            for tx in coin_txs:
                if (
                        after_timestamp < int(tx.get('timeStamp')) < before_timestamp and
                        tx.get('isError') == is_error and
                        tx.get('to') in contract_addresses and
                        function_name in tx.get('functionName')
                ):
                    txs[tx.get('hash')] = tx
            return txs

        except AttributeError as e:
            print(f'{address} : find_txs {e}')
            # Сейчас из сеполии почему-то строка возвращается в тх, пока не тестил больше


    @api_key_required
    async def find_tx_by_method_id(self, address: str, to: str, method_id: str):
        txs = {}
        coin_txs = (await self.client.network.api.functions.account.txlist(address))['result']
        for tx in coin_txs:
            # {'blockNumber': '17775679', 'timeStamp': '1690355483', 'hash': '0xce8add3eda0f57419ba41ea999912268f7ed19bda11cc19db098185bfb6c616e', 'nonce': '13', 'blockHash': '0xca8faf70a88f1bbbdb47f0390a050ec1c1c94e28f6cc5d7e793954519c7f739d', 'transactionIndex': '44', 'from': '0x36f302d18dcede1ab1174f47726e62212d1ccead', 'to': '0x32400084c286cf3e17e7b677ea9583e60a000324', 'value': '35703276971597170', 'gas': '124414', 'gasPrice': '18344087912', 'isError': '0', 'txreceipt_status': '1', 'input': '0xeb67241900000000000000000000000036f302d18dcede1ab1174f47726e62212d1ccead000000000000000000000000000000000000000000000000007d82a7600f4e7200000000000000000000000000000000000000000000000000000000000000e000000000000000000000000000000000000000000000000000000000000b73a30000000000000000000000000000000000000000000000000000000000000320000000000000000000000000000000000000000000000000000000000000010000000000000000000000000036f302d18dcede1ab1174f47726e62212d1ccead00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000', 'contractAddress': '', 'cumulativeGasUsed': '5139068', 'gasUsed': '118078', 'confirmations': '1531219', 'methodId': '0xeb672419', 'functionName': 'requestL2Transaction(address _contractL2,uint256 _l2Value,bytes _calldata,uint256 _l2GasLimit,uint256 _gasPricePerPubdata,bytes[] _factoryDeps,address _refundRecipient)'}
            # if tx.get('isError') == '0' and tx.get('to') == to.lower() and method_id in tx.get('methodId'):
            if tx.get('isError') == '0' and tx.get('to') == to.lower() and tx.get('input').startswith(method_id):
                txs[tx.get('hash')] = tx
        return txs
