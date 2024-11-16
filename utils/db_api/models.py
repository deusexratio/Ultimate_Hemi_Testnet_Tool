from datetime import datetime

from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Wallet(Base):
    __tablename__ = 'wallets'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    address: Mapped[str]
    today_activity_swaps: Mapped[int] = mapped_column(default=0)
    twice_weekly_capsule: Mapped[int] = mapped_column(default=0)
    safe_created: Mapped[bool] = mapped_column(default=False, server_default='0')
    next_action_time: Mapped[datetime | None] = mapped_column(default=None)
    today_activity_bridge_eth: Mapped[int] = mapped_column(default=0)
    today_activity_bridge_erc20: Mapped[int] = mapped_column(default=0)
    insufficient_balance: Mapped[bool] = mapped_column(default=False, server_default='0')
    private_key: Mapped[str] = mapped_column(unique=True, index=True)
    proxy: Mapped[str]
    # todo: test order in table

    # bridges_eth_to_hemi: Mapped[int | None] = mapped_column(default=None)
    # bridges_eth_from_hemi: Mapped[int | None] = mapped_column(default=None)

    def __repr__(self):
        return f'{self.name}: {self.address}'


class Failed(Base):
    __tablename__ = 'failed'

    id: Mapped[int] = mapped_column(primary_key=True)
    tx_hash: Mapped[str]
    block: Mapped[int]
    wallet_address: Mapped[str]
    contract: Mapped[str]
    decreased_activity_for_today: Mapped[bool] = mapped_column(default=False, server_default='0')

    def __repr__(self):
        return f'{self.wallet_address}: {self.tx_hash} | Contract : {self.contract}'
