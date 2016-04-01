from electrum.wallet import WalletStorage, NewWallet
from datetime import datetime, timedelta

import argparse
import electrum
import json
import os
import pexpect
import re
import requests
import sys
import sqlite3
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument("-cb", "--check_balance", metavar='CALLBACK_URL',
                    help='''Check balance for all addresses.
                            If balance different from value in DB then POST request sent to CALLBACK_URL''', type=str)
parser.add_argument("-pt", "--pay_to", metavar='PAYTO_ADDRESS', type=str)
parser.add_argument("-a", "--amount", metavar='AMOUNT', type=float)
parser.add_argument("-pw", "--root_password", metavar='WALLET PASSWORD', type=str)
parser.add_argument("wallet_path", metavar='WALLET_PATH', type=str, nargs='+', help='Electrum wallet path')

args = parser.parse_args()
exec_path = os.path.dirname(os.path.realpath(__file__)) + '/'

# test electrum daemon
try:
    pid = subprocess.check_output('pgrep electrum', shell=True)
except subprocess.CalledProcessError:
    # start daemon
    f = subprocess.call(['electrum', 'daemon', 'start'])


if os.path.isfile(args.wallet_path[0]):
    storage = WalletStorage(args.wallet_path[0])
    w = electrum.wallet.NewWallet(storage)
else:
    print('Wrong Wallet Path!')
    sys.exit()


if not os.path.isfile(exec_path + 'murtcele.db'):
    conn = sqlite3.connect(exec_path + 'murtcele.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE electrum (id integer primary key autoincrement ,address text not null,
                                        balance real not null, t datetime not null default CURRENT_TIMESTAMP)''')

    # fill db with wallet addresses
    addresses = subprocess.check_output('electrum listaddresses', shell=True)
    pattern = r'"([A-Za-z0-9_\./\\-]*)"'
    addresses = re.findall(pattern, addresses)

    insert = []
    for i in range(0, len(addresses)):
        print(addresses[i])
        balance = subprocess.check_output('electrum getaddressbalance ' + addresses[i], shell=True)
        balance = re.findall(pattern, balance)[1]
        insert.append((None, addresses[i], balance, datetime.now()))
    c.executemany('INSERT INTO electrum VALUES (?,?,?,?)', insert)
    conn.commit()
    conn.close()
    print('db created, ' + str(len(addresses)) + ' items')
    sys.exit()


if args.check_balance:
    addresses = subprocess.check_output('electrum listaddresses', shell=True)
    pattern = r'"([A-Za-z0-9_\./\\-]*)"'
    addresses = re.findall(pattern, addresses)
    conn = sqlite3.connect(exec_path + 'murtcele.db')
    c = conn.cursor()
    counter = 0
    for i in range(0, len(addresses)):
        entry = c.execute("SELECT * FROM electrum WHERE address=?", (addresses[i],)).fetchone()
        if not entry:
            # insert new one
            c.execute("INSERT INTO electrum VALUES (?, ?, ?, ?)", (None, addresses[i], 0, datetime.now()))
            conn.commit()
            continue
        else:
            # check if entry is not too old
            date_added = datetime.strptime(entry[3], "%Y-%m-%d %H:%M:%S.%f")
            delta = datetime.now() - date_added
            if delta.days > 5:
                # skip this address
                continue

        balance = subprocess.check_output('electrum getaddressbalance ' + addresses[i], shell=True)
        cur_balance = re.findall(pattern, balance)[1]
        c.execute("SELECT balance FROM electrum WHERE address=?", (addresses[i],))
        old_balance = c.fetchone()[0]
        # print(str(old_balance) + '----' + addresses[i])
        if isinstance(old_balance, float):
            if old_balance != float(cur_balance):
                counter += 1
                r = requests.post(args.check_balance, data={
                    'address': addresses[i],
                    'prev_balance': old_balance,
                    'cur_balance': cur_balance})
                c.execute("UPDATE electrum SET balance = ? WHERE address =?", (cur_balance, addresses[i]))
                conn.commit()

    conn.close()
    print(str(counter) + ' balance changes found')


if args.pay_to and args.amount and args.root_password:
    if subprocess.check_output('electrum validateaddress ' + args.pay_to, shell=True).strip() == 'false':
        print('Wrong address!')
        sys.exit()

    balance = subprocess.check_output('electrum getbalance', shell=True)
    pattern = r'"([A-Za-z0-9_\./\\-]*)"'
    account_balance = float(re.findall(pattern, balance)[1])
    if account_balance < args.amount:
        print('Not enough BTC\'s')

    # payto and broadcast transaction
    # pzdc below, see https://github.com/spesmilo/electrum/issues/1742
    c = pexpect.spawn('electrum payto ' + args.pay_to + ' ' + str(args.amount))
    c.expect('Password:')
    c.sendline(args.root_password)
    c.expect(pexpect.EOF)
    hs = c.before
    hex_string = re.findall(pattern, hs)[2]
    r = requests.post('https://blockchain.info/pushtx', data={'tx': hex_string})
    if r.status_code == 200:
        print('Transaction submitted')
    else:
        print('Error. Transaction was not submitted')

    sys.exit()
