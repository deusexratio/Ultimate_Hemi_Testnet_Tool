from utils.db_api.models import Base, Wallet, Failed
from utils.db_api.db import DB

from data.config import WALLETS_DB


def get_wallets(sqlite_query: bool = False) -> list[Wallet]:
    if sqlite_query:
        return db.execute('SELECT * FROM wallets')
    return db.all(entities=Wallet)

def get_wallet(private_key: str, sqlite_query: bool = False) -> Wallet | None:
    if sqlite_query:
        return db.execute('SELECT * FROM wallets WHERE private_key = ?', (private_key,), True)
    return db.one(Wallet, Wallet.private_key == private_key)

def display_insufficient_wallets():
    count = 0
    for wallet in get_wallets():
        if wallet.insufficient_balance:
            print(f'Found insufficient wallet: {wallet}')
            count+=1
    if count == 0:
        print("Didn't find any insufficient wallets")
    else:
        print(f'Found total {count} insufficient wallets')

def display_current_stats():
    for wallet in get_wallets():
        print(f'{wallet.name} | {wallet.address} | Today swaps done: {wallet.today_activity_swaps} | '
              f'This week capsules created: {wallet.twice_weekly_capsule}')

def reset_daily_tasks():
    return db.execute('UPDATE wallets SET today_activity_eth = ?, ' # todo:  test 
                      'today_activity_erc20 = ?, today_activity_swaps = ?', ('0', '0', '0',), True)

def get_failed_txs(sqlite_query: bool = False) -> list[Failed]:
    if sqlite_query:
        return db.execute('SELECT * FROM failed')
    return db.all(entities=Failed)

def get_failed_tx(tx_hash: str, sqlite_query: bool = False) -> Failed | None:
    if sqlite_query:
        return db.execute('SELECT * FROM failed WHERE tx_hash = ?', (tx_hash,), True)
    return db.one(Failed, Failed.tx_hash == tx_hash)

def get_failed_marked_tx(sqlite_query: bool = False) -> list[Failed]:
    if sqlite_query:
        return db.execute('SELECT * FROM failed WHERE decreased_activity_for_today = ?', (1,), True)
    return db.one(Failed, Failed.decreased_activity_for_today == True)


db = DB(f'sqlite:///{WALLETS_DB}', echo=False, pool_recycle=3600, connect_args={'check_same_thread': False})
db.create_tables(Base)
