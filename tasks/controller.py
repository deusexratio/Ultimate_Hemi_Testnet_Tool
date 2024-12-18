from __future__ import annotations

from libs.eth_async.client import Client
from libs.eth_async.data.models import Networks, RawContract
from data.models import Contracts
from tasks.base import Base
from tasks.hemi_testnet import Sepolia, Hemi, TestnetBridge


class Controller(Base):
    def __init__(self, client: Client):
        super().__init__(client)

        self.base = Base(client=client)
        self.sepolia = Sepolia(client=Client(private_key=client.account.key,
                                             proxy=client.proxy, network=Networks.Sepolia))
        self.hemi = Hemi(client=Client(private_key=client.account.key,
                                       proxy=client.proxy, network=Networks.Hemi_Testnet))
        self.testnet_bridge = TestnetBridge(client=Client(private_key=client.account.key,
                                                          proxy=client.proxy, network=Networks.Optimism))

# Unused for now
    async def made_sepolia_bridge_eth(self) -> bool:
        client = Client(private_key='', network=Networks.Sepolia)
        return bool(await client.transactions.find_txs(
            contract=Contracts.Hemi_Bridge_Sepolia,
            function_name='depositETH',
            address=self.client.account.address,
        ))

    async def made_sepolia_bridge_erc20(self) -> bool:
        client = Client(private_key='', network=Networks.Sepolia)
        return bool(await client.transactions.find_txs(
            contract=Contracts.Hemi_Bridge_Sepolia,
            function_name='depositERC20',
            address=self.client.account.address,
        ))

    async def made_capsule(self) -> bool:
        client = Client(private_key='', network=Networks.Hemi_Testnet)
        return bool(await client.transactions.find_txs(
            contract=Contracts.Hemi_Capsule,
            function_name='shipPackage',
            address=self.client.account.address,
        ))
