import asyncio
import json
import random
from datetime import datetime

from web3.types import TxParams
from fake_useragent import UserAgent
from eth_abi import encode
from eth_abi.packed import encode_packed
from uniswap_universal_router_decoder import RouterCodec, FunctionRecipient

from libs.eth_async.data.models import TokenAmount, RawContract, TxArgs, Network, Networks
from libs.eth_async.exceptions import HTTPException
from libs.eth_async.transactions import Tx
from libs.eth_async.utils.web_requests import async_post
from libs.eth_async.client import Client
from data.models import Contracts, Settings
from tasks.base import Base


class Hemi(Base):
    @staticmethod
    async def create_metadata(token: RawContract, client: Client) -> str:
        headers = {
            'accept': 'application/json, text/plain, */*',
            'accept-language': 'ru,en-US;q=0.9,en;q=0.8',
            'content-type': 'application/json',
            'origin': 'https://app.capsulelabs.xyz',
            'priority': 'u=1, i',
            'referer': 'https://app.capsulelabs.xyz/',
            'user-agent': UserAgent().chrome,
        }

        json_data = {
            'name': f'{token.title[5:]} Transaction',
        }

        response_json = await async_post(
            url='https://app.capsulelabs.xyz/api/create-metadata',
            headers=headers,
            data=json.dumps(json_data),
            proxy=client.proxy
        )
        url = response_json['tokenURI']
        return url

    async def create_capsule(self, token: RawContract | None = None, amount: float | int | None = None):
        token_list = [Contracts.Hemi_DAI, Contracts.Hemi_USDCe, Contracts.Hemi_USDTe]
        if not token:
            token = random.choices(
                population=token_list,
                weights=[1, 1, 1]
            )[0]
        if isinstance(amount, (float, int)):
            amount = TokenAmount(amount=amount, decimals=token.decimals)
        if not amount:
            amount = Base.get_token_amount_for_capsule(token=token)

        failed_text = f'{self.client.account.address} : Failed to create capsule {amount.Ether} {token.title} via Capsule'
        contract = await self.client.contracts.get(contract_address=Contracts.Hemi_Capsule)
        token_balance = await self.client.wallet.balance(token=token)
        if token_balance != 0:
            approve_amount = random.randint(100000, 1000000)
            approved = await self.approve_interface(token_address=token.address,
                                                        spender=Contracts.Hemi_Capsule_Manager.address,
                                                        amount=TokenAmount(amount=approve_amount, wei=False,
                                                                           decimals=token.decimals))
            if not approved:
                return f'Failed token to eth swap | can not approve'
        else:
            return f'{failed_text} | zero balance of {token.title}'

        url = await self.create_metadata(token=token, client=self.client)
        packageContent = [
            [
                encode(['uint256', 'address', 'uint256', 'uint256'],
                   [1, token.address, 0, amount.Wei]), # self.client.w3.to_checksum_address(token.address)
            ],
            url
        ]
        securityInfo = [
            self.client.w3.to_bytes(hexstr='0x0000000000000000000000000000000000000000000000000000000000000000'),
            0,
            self.client.w3.to_bytes(hexstr='0x0000000000000000000000000000000000000000'),
            0
        ]
        args = TxArgs(
            packageContent_=packageContent,
            securityInfo_=securityInfo,
            address=f'{self.client.account.address}'
        )
        tx_params = TxParams(
            to=contract.address,
            data=contract.encodeABI('shipPackage', args=args.tuple()),
            value=int(0.001 * 10 ** 18),
        )

        tx = await self.client.transactions.sign_and_send(tx_params=tx_params)
        ''' this block was used while trying to get gas with wrong approval. Most likely will delete later
        # if tx is None:
        #     try:
        #         # await asyncio.sleep(15)
        #         # tx_params['gas'] = random.randint(600000, 800000)
        #         # print(tx_params)
        #         tx = await self.client.transactions.sign_and_send(tx_params=tx_params)
        #         receipt = await tx.wait_for_receipt(client=self.client, timeout=300)
        #         if receipt:
        #             return f'{self.client.account.address} : {amount.Ether} {token.title} Created capsule: {tx.hash.hex()}'
        #     except AttributeError:
        #         return failed_text
        # elif type(tx) is str:
        #     return f'{failed_text} | {tx}'
        # else:
        '''
        # API doesn't work now so no checking tx
        if isinstance(tx, str):
            return failed_text
        receipt = await tx.wait_for_receipt(client=self.client, timeout=300)
        if receipt:
            return f'{self.client.account.address} : {amount.Ether} {token.title} Created capsule: {tx.hash.hex()}'
        # tx = await self.client.transactions.sign_and_send(tx_params=tx_params)
        # receipt = await tx.wait_for_receipt(client=self.client, timeout=300)
        # check_tx_error = await Base.check_tx(tx.hash)
        # if receipt is True and check_tx_error is False:
        else:
            return f'{failed_text}!' # Error: {check_tx_error.ErrDescription}, Tx_hash: {tx.hash.hex()}'


    async def swap(self, token: RawContract = None, route: str | None = None,
                   amount_eth: int | None = None, amount_token: int | None = None, slippage: float = 15):
        if not token:
            token = random.choices(
                (Contracts.Hemi_DAI, Contracts.Hemi_USDTe, Contracts.Hemi_USDCe),
                (1, 1, 1)
            )[0]
        token_name = token.title

        if not route:
            route = random.choices(
                ('eth_to_token', 'token_to_eth'),
                (1, 1)
            )[0]
        if not amount_eth and route == 'eth_to_token':
            amount_eth = Base.get_eth_amount_for_swap()
        if not amount_token and route == 'token_to_eth':
            amount_token = Base.get_token_amount_for_swap(token=token)

        # token = await self.client.contracts.default_token(contract_address=token.address)
        contract = await self.client.contracts.get(contract_address=Contracts.Hemi_Swap_Router)
        pool_fee_list = [100, 1000, 3000, 10000] # int in path is how much goes to the pool (10000 is 1%)
        if route == 'eth_to_token':
            for pool_fee in pool_fee_list:
                try:
                    commands = '0x0b00'
                    value = amount_eth.Wei
                    amount_out = await Hemi.get_price_to_swap(self.client, route=route,
                                                              token=token, amount_eth=amount_eth)
                    amount_token = amount_out

                    failed_text = (f'{self.client.account.address} Failed to swap {amount_eth.Ether} ETH '
                                   f'for {amount_out.Ether} {token_name} via Swap')
                    bytes_amount = encode(
                        ['uint256', 'uint256'],
                        [2, amount_eth.Wei]
                    )
                    decoded_path = await Hemi.swap_route(route=route, token=token, pool_fee=pool_fee)
                    bytes_path = encode(
                        ['uint256', 'uint256', 'uint256', 'bytes', 'uint256'],
                    [1, amount_eth.Wei, int(amount_out.Wei * 0.8), self.client.w3.to_bytes(hexstr=decoded_path), 0]
                    )
                    inputs = [bytes_amount, bytes_path]
                    args = TxArgs(commands=commands,
                                    inputs=inputs,
                                    deadline=int(datetime.now().timestamp()) + 3 * 60)
                    tx_params = TxParams(to=contract.address,
                                        data=contract.encodeABI('execute', args=args.tuple()),
                                        value=value)
                    tx = await self.client.transactions.sign_and_send(tx_params=tx_params)
                    # print(tx_params)
                    await asyncio.sleep(5)
                    if isinstance(tx, Tx):
                        print(f'{pool_fee} pool fee selected for {route} {token_name}')
                        break # trying to estimate gas until right pool fee is found
                except AttributeError as e:
                    return f'{e}'
            if tx is None:
                return f"{failed_text} | couldn't estimate gas for swap with all tries of pool fees"

        elif route == 'token_to_eth':
            wallet_amount = await self.client.wallet.balance(token=token)
            if wallet_amount != 0:
                allowance_amount = 2 ** 160 - 1  # max/infinite
                approved = await self.approve_interface(token_address=token.address,
                                                        spender=Contracts.Swap_DAI_permit.address,
                                                        amount=TokenAmount(amount=allowance_amount, wei=False,
                                                                           decimals=token.decimals))
                if not approved:
                    return f'Failed token to eth swap | can not approve'

            for pool_fee in pool_fee_list:
                try:
                    amount_out = await Hemi.get_price_to_swap(self.client, route=route,
                                                              token=token, amount_token=amount_token)
                    amount_eth = amount_out
                    failed_text = (f'{self.client.account.address} Failed to swap {amount_token.Ether} {token_name} '
                                   f'for {amount_out.Ether} ETH via Swap')
                    value = 0
                    commands = '0x000c'
                    bytes_empty = encode(
                        ['uint256', 'uint256'],
                        [1, int(amount_out.Wei * 0.9)]
                    )
                    decoded_path = await Hemi.swap_route(route=route, token=token, pool_fee=pool_fee)
                    bytes_path = encode(
                    ['uint256', 'uint256', 'uint256', 'bytes', 'uint256'],
                    [2, amount_token.Wei, int(amount_out.Wei * 0.9), self.client.w3.to_bytes(hexstr=decoded_path), 1]
                    )
                    inputs = [bytes_path, bytes_empty]
                    args = TxArgs(commands=commands,
                                    inputs=inputs,
                                    deadline=int(datetime.now().timestamp()) + 3 * 60)
                    tx_params = TxParams(to=contract.address,
                                        data=contract.encodeABI('execute', args=args.tuple()),
                                        value=value)
                    tx = await self.client.transactions.sign_and_send(tx_params=tx_params)
                    # print(tx_params)
                    await asyncio.sleep(5)
                    if isinstance(tx, Tx):
                        print(f'{pool_fee} pool fee selected for {route} {token_name}')
                        break # trying to estimate gas until right pool fee is found
                except AttributeError as e:
                    return f'{e}'
            if tx is None:
                # trying permit2
                print(f'{self.client.account.address} tx in swap was None. Retrying with permit2 message')
                permit_data, signed_message = await self.client.transactions.get_permit2_data(
                    permit2=Contracts.Swap_DAI_permit, router=Contracts.Hemi_Swap_Router, token=token,
                    permit2_abi=Contracts.Swap_DAI_permit.abi)

                if not permit_data and not signed_message:
                    return f'{failed_text} | Failed just swapping and permit2 allowance > 0 now'

                expiration = permit_data['details']['expiration']
                sigDeadline = permit_data['sigDeadline']
                signature = signed_message.signature
                signature = signature.hex()
                amount_out = await Hemi.get_price_to_swap(self.client, route=route,
                                                          token=token, amount_token=amount_token)
                for pool_fee in pool_fee_list:
                    decoded_path = await Hemi.swap_route(route=route, token=token, pool_fee=pool_fee)
                    # v3_calldata = encode(['address', 'uint256', 'uint256', 'bytes', 'bool'],
                    #                      [to, amount, slippage, path, from_eoa])
                    #
                    # encoded_input = (
                    #     codec
                    #     .encode
                    #     .chain()
                    #     .permit2_permit(permit_data, signed_message)
                    #     .v3_swap_exact_out(
                    #         function_recipient=FunctionRecipient.SENDER,
                    #         # amount_in=amount_token.Wei,
                    #         # amount_out_min=int(amount_eth.Wei * 0.99),
                    #         amount_in_max=amount_token.Wei,
                    #         amount_out=int(amount_eth.Wei * 0.99),
                    #         path=path,
                    #         payer_is_sender=True,
                    #     )
                    #     .build(codec.get_default_deadline())
                    # )
                    ############################### barbaric input ##########################################
                    deadline = self.client.w3.to_bytes(int(datetime.now().timestamp()) + 3 * 60)
                    encoded_input = bytes.fromhex(
                        '3593564c'
                        f'{"60".zfill(64)}'
                        f'{"a0".zfill(64)}'
                        f'{str(deadline.hex()).zfill(64)}'
                        f'{"3".zfill(64)}'
                        f'0a000c0000000000000000000000000000000000000000000000000000000000'
                        f'{"3".zfill(64)}'
                        f'{"60".zfill(64)}'
                        f'{"1e0".zfill(64)}'
                        f'{"300".zfill(64)}'
                        f'{"160".zfill(64)}'
                        f'{token.address[2:].zfill(64)}'
                        f'{"ffffffffffffffffffffffffffffffffffffffff".zfill(64)}'
                        f'{str(hex(expiration))[2:].zfill(64)}'
                        f'{"".zfill(64)}'
                        f'{Contracts.Hemi_Swap_Router.address[2:].zfill(64)}'
                        f'{str(hex(sigDeadline))[2:].zfill(64)}'
                        f'{"e0".zfill(64)}'
                        f'{"41".zfill(64)}'
                        f'{signature[2:]}00000000000000000000000000000000000000000000000000000000000000'
                        f'{"100".zfill(64)}'
                        f'{"2".zfill(64)}'
                        f'{str(hex(amount_token.Wei))[2:].zfill(64)}'
                        f'{str(hex(int(amount_out.Wei * ((100 - slippage) / 100))))[2:].zfill(64)}'
                        f'{"a0".zfill(64)}'
                        f'{"1".zfill(64)}'
                        f'{"2b".zfill(64)}'
                        f'{decoded_path}000000000000000000000000000000000000000000'
                        f'{"40".zfill(64)}'
                        f'{"1".zfill(64)}'
                        f'{str(hex(int(amount_out.Wei * ((100 - slippage) / 100))))[2:].zfill(64)}'
                    )
                    decoded_input = self.client.w3.to_hex(encoded_input)
                    ############################### barbaric input ##########################################
                    tx_params = TxParams(
                        to=contract.address,
                        data=decoded_input,
                        value=value,
                    )
                    tx = await self.client.transactions.sign_and_send(tx_params=tx_params)
                    # print(tx_params)
                    await asyncio.sleep(5)
                    if isinstance(tx, Tx):
                        print(f'{pool_fee} pool fee selected for {route} {token_name}')
                        break
        else:
            return 'Incorrect route for swap'
        # API doesn't work now so no checking tx
        receipt = None
        if isinstance(tx, Tx):
            receipt = await tx.wait_for_receipt(client=self.client, timeout=300)
        else:
            print(route, tx_params)
        # check_tx_error = await Base.check_tx(tx_hash=tx.hash, network=Networks.Hemi_Testnet)
        if receipt:
            if route == 'eth_to_token':
                return f'{amount_eth.Ether} Eth was swapped to {amount_token.Ether} {token_name} : {tx.hash.hex()}'
            if route == 'token_to_eth':
                return f'{amount_token.Ether} {token_name} was swapped to {amount_eth.Ether} Eth : {tx.hash.hex()}'
        else:
            return f'{failed_text} | all attempts failed'

    @staticmethod
    async def swap_route(route: str, token: RawContract, pool_fee: int = 3000) -> str | None:
        codec = RouterCodec()
        if route == 'eth_to_token':
            path = [Contracts.Hemi_WETH.address, pool_fee, token.address]
        elif route == 'token_to_eth':
            path = [token.address, pool_fee, Contracts.Hemi_WETH.address]
        else:
            print('wrong route given to swap_route')
            return None
        encoded_path = codec.encode.v3_path(v3_fn_name='V3_SWAP_EXACT_IN', path_seq=path)
        return encoded_path.hex()


    @staticmethod
    async def get_price_to_swap(client: Client, route: str | None = 'token_to_eth',
                             amount_eth: TokenAmount | None = None,
                             amount_token: TokenAmount | None = None,
                             token: RawContract | None = None,
                             slippage: float = 1) -> TokenAmount | None:
        headers = {
                'accept': '*/*',
                'accept-language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
                'content-type': 'text/plain;charset=UTF-8',
                'origin': 'https://swap.hemi.xyz',
                'priority': 'u=1, i',
                'sec-ch-ua': '"Google Chrome";v="129", "Not=A?Brand";v="8", "Chromium";v="129"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'cross-site',
                'user-agent': UserAgent().chrome,
                'x-request-source': 'uniswap-web',
        }
        try:
            if route == 'token_to_eth':
                amount_token = TokenAmount(amount=amount_token.Ether, wei=False, decimals=token.decimals)
                data = ('{"tokenInChainId":743111,'
                        f'"tokenIn":"{token.address}",'
                        f'"tokenOutChainId":743111,"tokenOut":"ETH","amount":"{amount_token.Wei}",'
                        '"sendPortionEnabled":true,"type":"EXACT_INPUT","intent":"quote","configs":'
                        '[{"protocols":["V2","V3","MIXED"],"enableUniversalRouter":true,"routingType":"CLASSIC",'
                        f'"recipient":"{client.account.address}",'
                        '"enableFeeOnTransferFeeFetching":true}]}')
                response = await async_post(
                    url='https://hgc8sm30t0.execute-api.eu-central-1.amazonaws.com/production/v2/quote',
                    headers=headers, data=data, proxy=client.proxy)
                price = response['allQuotes'][0]['quote']['quote']
                return TokenAmount(amount=int(price), wei=True, decimals=18)
            elif route == 'eth_to_token':
                data = ('{"tokenInChainId":743111,'
                        '"tokenIn":"ETH",'
                        f'"tokenOutChainId":743111,"tokenOut":"{token.address}","amount":"{amount_eth.Wei}",'
                        '"sendPortionEnabled":true,"type":"EXACT_INPUT","intent":"quote","configs":'
                        '[{"protocols":["V2","V3","MIXED"],"enableUniversalRouter":true,"routingType":"CLASSIC",'
                        f'"recipient":"{client.account.address}",'
                        '"enableFeeOnTransferFeeFetching":true}]}')
                response = await async_post(
                    url='https://hgc8sm30t0.execute-api.eu-central-1.amazonaws.com/production/v2/quote',
                    headers=headers, data=data, proxy=client.proxy)
                price = response['allQuotes'][0]['quote']['quote']
                return TokenAmount(amount=int(price), wei=True, decimals=token.decimals)
        except ValueError as e:
            print(f'{e} wrong route given to get_price_to_swap')


    async def create_safe(self):
        failed_text = f'{self.client.account.address} Failed to create safe for {self.client.account.address}'
        contract = await self.client.contracts.get(contract_address=Contracts.Gnosis_Safe)

        singleton = self.client.w3.to_checksum_address('3e5c63644e683549055b9be8653de26e0b4cd36e')
        initializer = bytes.fromhex(
            'b63e800d'
            f'{"100".zfill(64)}'
            f'{"1".zfill(64)}'
            f'{"".zfill(64)}'
            f'{"140".zfill(64)}'
            f'{"f48f2B2d2a534e402487b3ee7C18c33Aec0Fe5e4".zfill(64)}'
            f'{"".zfill(64)}'
            f'{"".zfill(64)}'
            f'{"".zfill(64)}'
            f'{"1".zfill(64)}'
            f'{str(self.client.account.address)[2:].zfill(64)}'
            # f'{"".zfill(56)}'
            f'{"".zfill(64)}'
        )
        saltNonce = 0

        args = TxArgs(
            singleton=singleton,
            initializer=initializer,
            saltNonce=saltNonce
            )
        tx_params = TxParams(
            to=contract.address,
            data=contract.encodeABI('createProxyWithNonce', args=args.tuple()),
            value=0,
        )

        tx = await self.client.transactions.sign_and_send(tx_params=tx_params)
        if tx is None:
            return failed_text
        if type(tx) is str:
            return f'{failed_text} | {tx}'
        if isinstance(tx, Tx):
            receipt = await tx.wait_for_receipt(client=self.client, timeout=300)
        # check_tx_error = await Base.check_tx(tx_hash=tx.hash, network=Networks.Hemi_Testnet)
        if receipt:
            return f'Created safe for {self.client.account.address} : {tx.hash.hex()}'
        else:
            return failed_text


class Testnet_Bridge(Base):
    @staticmethod
    async def get_price_seth(client: Client,
                             amount_eth: TokenAmount | None = None,
                             slippage: float = 5) -> int | str:
        headers = {
            'accept': '*/*',
            'accept-language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
            'content-type': 'text/plain;charset=UTF-8',
            'origin': 'https://app.uniswap.org',
            'priority': 'u=1, i',
            'referer': 'https://app.uniswap.org/',
            'sec-ch-ua': '"Google Chrome";v="129", "Not=A?Brand";v="8", "Chromium";v="129"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-site',
            'user-agent': UserAgent().chrome,
            'x-request-source': 'uniswap-web',
        }

        data = {
            "tokenInChainId": 10,
            "tokenIn": "ETH",
            "tokenOutChainId": 10,
            "tokenOut": Contracts.Sepolia_Ether.address,
            "amount": str(amount_eth.Wei),
            "sendPortionEnabled": 'true',
            "type": "EXACT_INPUT",
            "intent": "quote",
            "configs": [
                {
                    "enableUniversalRouter": 'true',
                    "protocols": [
                        "V2",
                        "V3",
                        "MIXED"
                    ],
                    "routingType": "CLASSIC",
                    "recipient": client.account.address,
                    "enableFeeOnTransferFeeFetching": 'true'
                }
            ],
            "useUniswapX": 'true',
            "swapper": client.account.address,
            "slippageTolerance": 0.5 # hardcoded because API refused to give quotes with big slippage
        }
        try:
            response = await async_post(url='https://interface.gateway.uniswap.org/v2/quote',
                                    headers=headers, data=data, proxy=client.proxy)
        except HTTPException as e:
            print(e)
            return f"{client.account.address} : couldn't get SETH price"
        seth_price = response['quote']['quoteGasAndPortionAdjusted']
        return int(seth_price) # returns int in wei

    async def bridge(self, # client: Client,
                            # amount_eth: TokenAmount,
                            slippage: float = 5) -> str | None:
        settings = Settings()
        amount_eth = TokenAmount(
            amount=random.uniform(settings.autorefill_amount.from_, settings.autorefill_amount.to_),
            decimals=18)
        seth_amount = await Testnet_Bridge.get_price_seth(client=self.client, amount_eth=amount_eth, slippage=slippage)
        failed_text = f'{self.client.account.address} Failed to bridge {amount_eth.Ether} ETH to Sepolia via Testnet Bridge'
        op_client = Client(private_key=self.client.account.key, network=Networks.Optimism)
        arb_client = Client(private_key=self.client.account.key, network=Networks.Arbitrum)
        op_balance = await op_client.wallet.balance()
        arb_balance = await arb_client.wallet.balance()

        if op_balance.Wei > arb_balance.Wei and op_balance.Ether > settings.autorefill_amount.to_:
            client = op_client
            contract = await self.client.contracts.get(contract_address=Contracts.Testnet_Bridge_Optimism)
            network = 'Optimism'
        elif arb_balance.Wei > op_balance.Wei and arb_balance.Ether > settings.autorefill_amount.to_:
            client = arb_client
            contract = await self.client.contracts.get(contract_address=Contracts.Testnet_Bridge_Arbitrum)
            network = 'Arbitrum'
        else:
            return 'Insufficient balances for refill'

        args = TxArgs(
            amountIn=amount_eth.Wei,
            amountOutMin=int(seth_amount * (100-slippage)/100),
            dstChainId=161,
            to=client.account.address,
            refundAddress=client.account.address,
            zroPaymentAddress='0x0000000000000000000000000000000000000000',
            adapterParams=b'',
        )

        tx_params = TxParams(
            to=contract.address,
            data=contract.encodeABI('swapAndBridge', args=args.tuple()),
            value=int(amount_eth.Wei * 1.07) # added L0 fee, can't count it for now
        )

        tx = await client.transactions.sign_and_send(tx_params=tx_params)
        if tx is None:
            return f'{failed_text}'
        if type(tx) is str:
            return f'{failed_text} | {tx}'
        receipt = await tx.wait_for_receipt(client=client, timeout=500)
        check_tx_error = await Base.check_tx(str(tx.hash))

        if bool(receipt) is True and check_tx_error.Error is False:
            return f'{amount_eth.Ether} ETH was bridged to Sepolia from {network} via Testnet Bridge: {tx.hash.hex()}'
        else:
            print(f'check_tx_error bridge eth: {check_tx_error.Error}')
            return f'{failed_text}! Error: {check_tx_error.ErrDescription}, Tx_hash: {tx.hash.hex()}'


class Sepolia(Base):
    async def deposit_eth_to_hemi(self, amount: TokenAmount | None = None) -> str:
        failed_text = f'{self.client.account.address} Failed to bridge {amount} ETH to Hemi via Official Bridge'
        if not amount:
            amount = Base.get_eth_amount_for_bridge()
        contract = await self.client.contracts.get(contract_address=Contracts.Hemi_Bridge_Sepolia)
        args = TxArgs(
            _minGasLimit=200000,
            _extraData=b''
        )

        tx_params = TxParams(
            to=contract.address,
            data=contract.encodeABI('depositETH', args=args.tuple()),
            value=amount.Wei
        )

        tx = await self.client.transactions.sign_and_send(tx_params=tx_params)
        if tx is None:
            return f'{failed_text}'
        if type(tx) is str:
            return f'{failed_text} | {tx}'
        receipt = await tx.wait_for_receipt(client=self.client, timeout=500)
        check_tx_error = await Base.check_tx(str(tx.hash))

        if bool(receipt) is True and check_tx_error.Error is False:
            return f'{amount.Ether} ETH was bridged to Hemi via official bridge: {tx.hash.hex()}'
        else:
            print(f'check_tx_error bridge eth: {check_tx_error.Error}')
            return f'{failed_text}! Error: {check_tx_error.ErrDescription}, Tx_hash: {tx.hash.hex()}'

    async def _deposit_erc20_to_hemi(self, token: RawContract, amount: TokenAmount | None = None) -> str:
        if not amount:
            amount = Base.get_erc20_amount_for_bridge(token)
        from_token = await self.client.contracts.default_token(contract_address=token.address)
        from_token_name = await from_token.functions.symbol().call()

        failed_text = f'{self.client.account.address} Failed to bridge {amount.Ether} {from_token_name} to Hemi via Official Bridge'
        contract = await self.client.contracts.get(contract_address=Contracts.Hemi_Bridge_Sepolia)

        wallet_amount = await self.client.wallet.balance(token=from_token)

        if wallet_amount != 0:
            approve_amount = TokenAmount(amount=random.randint(10000, 1000000), decimals=token.decimals)
            await self.approve_interface(token_address=token.address,
                                         spender=contract.address,
                                         amount=approve_amount)
            await asyncio.sleep(random.randint(10, 15))
            # print(f'{self.client.account.address} approved {from_token_name} for bridge')
        else:
            return f'{failed_text} | can not approve'

        to_token = ''
        if from_token == Contracts.Sepolia_USDT:
            to_token = Contracts.Hemi_USDTe
        elif from_token == Contracts.Sepolia_USDC:
            to_token = Contracts.Hemi_USDCe
        elif from_token == Contracts.Sepolia_DAI:
            to_token = Contracts.Hemi_DAI
        else:
            return 'wrong token'

        args = TxArgs(
            _l1Token=f'{from_token.address}',
            _l2Token=f'{to_token.address}',
            _amount=amount.Wei,
            _minGasLimit=200000,
            _extraData=b''
        )

        tx_params = TxParams(
            to=contract.address,
            data=contract.encodeABI('depositERC20', args=args.tuple()),
            value=0
        )

        tx = await self.client.transactions.sign_and_send(tx_params=tx_params)
        if tx is None:
            return f'{failed_text}'
        if type(tx) is str:
            return f'{failed_text} | {tx}'
        receipt = await tx.wait_for_receipt(client=self.client, timeout=500)
        check_tx_error = await Base.check_tx(tx.hash.hex())

        if bool(receipt) is True and check_tx_error.Error is False:
            return f'{amount.Ether} {from_token_name} stablecoin was bridged to Hemi via official bridge: {tx.hash.hex()}'
        else:
            print(f'check_tx_error bridge erc20: {check_tx_error.Error}')
            return f'{failed_text}! Error: {check_tx_error.ErrDescription}, Tx_hash: {tx.hash.hex()}'

    async def bridge_usdc_to_hemi(self) -> str:
        return await self._deposit_erc20_to_hemi(token=Contracts.Sepolia_USDC)

    async def bridge_usdt_to_hemi(self) -> str:
        return await self._deposit_erc20_to_hemi(token=Contracts.Sepolia_USDT)

    async def bridge_dai_to_hemi(self) -> str:
        return await self._deposit_erc20_to_hemi(token=Contracts.Sepolia_DAI)

    async def _faucet(self, token: RawContract, amount: int | None = None):
        if not amount:
            # amount = Base.get_stable_faucet_amount() # for now custom amount doesn't work in contract
            amount = 10000
        amount = TokenAmount(amount=amount, decimals=token.decimals)

        contract = await self.client.contracts.get(contract_address=Contracts.Aave_Faucet)
        # get_token = await self.client.contracts.default_token(contract_address=token.address)
        from_token = await self.client.contracts.default_token(contract_address=token.address)
        from_token_name = await from_token.functions.symbol().call()
        failed_text = f'{self.client.account.address} Failed to faucet {amount.Ether} {from_token_name} via Aave Faucet'

        args = TxArgs(
            token=from_token.address,
            to=self.client.account.address,
            amount=amount.Wei,
        )

        tx_params = TxParams(
            to=contract.address,
            data=contract.encodeABI('mint', args=args.tuple()),
            value=0
        )

        tx = await self.client.transactions.sign_and_send(tx_params=tx_params)
        if tx is None:
            return f'{failed_text}'
        if type(tx) is str:
            return f'{failed_text} | {tx}'
        receipt = await tx.wait_for_receipt(client=self.client, timeout=500)
        await asyncio.sleep(15)
        check_tx_error = await Base.check_tx(str(tx.hash))
        if bool(receipt) is True and check_tx_error.Error is False:
            return f'{amount.Ether} {from_token_name} was minted via Aave: {tx.hash.hex()}'
        else:
            print(f'check_tx_error faucet: {check_tx_error.Error}')
            return f'{failed_text}! Error: {check_tx_error.ErrDescription}, Tx_hash: {tx.hash.hex()}'

    async def faucet_usdc(self) -> str:
        return await self._faucet(token=Contracts.Sepolia_USDC)

    async def faucet_usdt(self) -> str:
        return await self._faucet(token=Contracts.Sepolia_USDT)

    async def faucet_dai(self) -> str:
        return await self._faucet(token=Contracts.Sepolia_DAI)

