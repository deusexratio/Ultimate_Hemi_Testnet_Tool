import asyncio

import aiohttp

from libs.eth_async.client import Client
from libs.eth_async.data.config import ETHERSCAN_API_KEY
from libs.eth_async.data.models import TokenAmount, TxStatus, Networks, Network, APIFunctions, RawContract
from libs.eth_async.blockscan_api import Transaction
from libs.eth_async.transactions import Tx
from libs.eth_async.utils.utils import randfloat

from data.models import Settings, Contracts
from libs.eth_async.utils.web_requests import async_get


class Base:
    def __init__(self, client: Client):
        self.client = client

    @staticmethod
    async def get_token_price(token_symbol='ETH', second_token: str = 'USDT') -> float | None:
        token_symbol, second_token = token_symbol.upper(), second_token.upper()

        if token_symbol.upper() in ('USDC', 'USDT', 'DAI', 'CEBUSD', 'BUSD'):
            return 1
        if token_symbol == 'WETH':
            token_symbol = 'ETH'
        if token_symbol == 'WBTC':
            token_symbol = 'BTC'

        for _ in range(5):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                            f'https://api.binance.com/api/v3/depth?limit=1&symbol={token_symbol}{second_token}') as r:
                        if r.status != 200:
                            return None
                        result_dict = await r.json()
                        if 'asks' not in result_dict:
                            return None
                        return float(result_dict['asks'][0][0])
            except Exception as e:
                await asyncio.sleep(5)
        raise ValueError(f'Can not get {token_symbol + second_token} price from Binance')

    async def approve_interface(self, token_address, spender, amount: TokenAmount | None = None) -> bool:
        balance = await self.client.wallet.balance(token=token_address)
        if balance.Wei <= 0:
            return False

        if not amount: # or amount.Wei > balance.Wei: dunno why this?
            amount = balance

        approved = await self.client.transactions.approved_amount(
            token=token_address,
            spender=spender,
            owner=self.client.account.address
        )

        if amount.Wei <= approved.Wei:
            return True

        tx = await self.client.transactions.approve(
            token=token_address,
            spender=spender,
            amount=amount
        )

        if isinstance(tx, Tx):
            receipt = await tx.wait_for_receipt(client=self.client, timeout=300)
        else:
            return False

        if receipt:
            return True

        return False

    async def get_token_info(self, contract_address):
        contract = await self.client.contracts.default_token(contract_address=contract_address)
        print('name:', await contract.functions.name().call())
        print('symbol:', await contract.functions.symbol().call())
        print('decimals:', await contract.functions.decimals().call())

    @staticmethod
    def parse_params(params: str, has_function: bool = True, has_0x: bool = True):
        # used for inspecting raw input of transactions
        if has_function:
            function_signature = params[:10]
            print('function_signature', function_signature)
            params = params[10:]
        if has_0x and not has_function:
            params = params[2:]
        while params:
            print(params[:64])
            params = params[64:]

    @staticmethod
    def get_eth_amount_for_swap():
        settings = Settings()
        return TokenAmount(
            amount=randfloat(
                from_=settings.eth_amount_for_swap.from_,
                to_=settings.eth_amount_for_swap.to_,
                step=0.0000001
            ), decimals=18
        )

    @staticmethod
    def get_token_amount_for_swap(token: RawContract):
        settings = Settings()
        return TokenAmount(
            amount=randfloat(
                from_=settings.token_amount_for_swap.from_,
                to_=settings.token_amount_for_swap.to_,
                step=0.01
            ),
            decimals=token.decimals
        )

    @staticmethod
    def get_eth_amount_for_bridge():
        settings = Settings()
        return TokenAmount(
            amount=randfloat(
                from_=settings.eth_amount_for_bridge.from_,
                to_=settings.eth_amount_for_bridge.to_,
                step=0.0001), decimals=18
        )

    @staticmethod
    def get_erc20_amount_for_bridge(token: RawContract):
        settings = Settings()
        return TokenAmount(
            amount=randfloat(
                from_=settings.erc20_amount_to_bridge.from_,
                to_=settings.erc20_amount_to_bridge.to_,
                step=0.01),
            decimals=token.decimals
        )

    @staticmethod
    def get_stable_faucet_amount(token: RawContract):
        settings = Settings()
        return TokenAmount(
            amount=randfloat(
                from_=settings.stable_faucet_amount.from_,
                to_=settings.stable_faucet_amount.to_,
                step=0.001),
            decimals=token.decimals
        )

    @staticmethod
    def get_token_amount_for_capsule(token: RawContract):
        settings = Settings()
        return TokenAmount(
            amount=randfloat(
                from_=settings.token_amount_for_capsule.from_,
                to_=settings.token_amount_for_capsule.to_,
                step=0.01),
            decimals=token.decimals
            # там в инпут дате считается все по децималс
        )

    @staticmethod
    async def check_tx(tx_hash: str, network: Network) -> TxStatus:
        url = network.api.url
        if network == Networks.Hemi_Testnet:
            key = None
            api = APIFunctions(key=key, url=url)
            attempts = 0
            while True:
                tx = await api.transaction.getstatus(txhash=tx_hash)
                if tx:
                    break
                attempts += 1
                print('checking attempts: ', attempts)
                await asyncio.sleep(3)
            if tx:
                tx_status = TxStatus(status=tx['result']['isError'], error=tx['result']['errDescription'])
            else:
                tx_status = TxStatus(status='1', error="can't check tx result")
            return tx_status

        if Network == Networks.Sepolia:
            key = ETHERSCAN_API_KEY
            api = APIFunctions(key=key, url=url)
            tx = await api.transaction.getstatus(txhash=tx_hash)
            tx_status = TxStatus(status=tx['result']['isError'], error=tx['result']['errDescription'])
            return tx_status
        # tx = await Transaction.getstatus(txhash=tx_hash, key=key, url=url)
        else:
            return TxStatus(status='0', error='true') # if something is wrong with api an error is returned

    @staticmethod
    async def check_tx_hemi(tx_hash: str):
        ### this function is for v2 api, I don't now know if they will leave v1 or v2
        url = 'https://testnet.explorer.hemi.xyz/api/v2/'
        attempts = 0
        while True:
            tx = await async_get(url=url + 'transactions/' + tx_hash)
            if tx:
                break
            attempts+=1
            print('checking attempts: ', attempts)
            await asyncio.sleep(3)
        if tx:
            tx_result = tx['result']
            if tx_result == 'execution reverted':
                tx_error = TxStatus(status='1', error=tx['revert_reason'])
            else:
                tx_error = TxStatus(status='0', error=None)
        else:
            tx_error = TxStatus(status='1', error="can't check tx result")
        return tx_error
