import argparse
import electrum
import json
import os
import re
import requests
import sys
import sqlite3
import subprocess

from electrum.wallet import WalletStorage, NewWallet

parser = argparse.ArgumentParser()
parser.add_argument("-ga", "--generate_address", help="Generate NUMBER receiving addresses.", type=int, metavar='NUMBER')
parser.add_argument("-cb", "--check_balance", metavar='CALLBACK_URL',
                    help='''Check balance for all addresses.
                            If balance different from value in DB then POST request sent to CALLBACK_URL''', type=str)
parser.add_argument("wallet_path", metavar='WALLET_PATH', type=str, nargs='+', help='Electrum wallet path')
args = parser.parse_args()

if os.path.isfile(args.wallet_path[0]):
    storage = WalletStorage(args.wallet_path[0])
    w = electrum.wallet.NewWallet(storage)
else:
    print('Wrong Wallet Path!')
    sys.exit()

if not os.path.isfile('/root/elctrm-chkr/murtcele.db'):
    conn = sqlite3.connect('/root/elctrm-chkr/murtcele.db')
    c = conn.cursor()
    c.execute("CREATE TABLE electrum (address text, balance real)")

    # fill db with wallet addresses
    addresses = subprocess.check_output('electrum listaddresses', shell=True)
    pattern = r'"([A-Za-z0-9_\./\\-]*)"'
    addresses = re.findall(pattern, addresses)

    insert = []
    for i in range(0, len(addresses)):
        balance = subprocess.check_output('electrum getaddressbalance ' + addresses[i], shell=True)
        balance = re.findall(pattern, balance)[1]
        insert.append((addresses[i], balance))

    c.executemany('INSERT INTO electrum VALUES (?,?)', insert)
    conn.commit()
    conn.close()
    print('db created, ' + str(len(addresses)) + ' items')

if args.generate_address:
    addresses = []
    for i in range(0, args.generate_address):
        addr = w.create_new_address()
        addresses.append(addr)
        conn = sqlite3.connect('murtcele.db')
        c = conn.cursor()
        c.execute("INSERT INTO electrum VALUES (?, 0)", (addr,))
        conn.commit()
        conn.close()
    print('Generated:')
    print(json.dumps(addresses))  # new addr list

if args.check_balance:
    addresses = subprocess.check_output('electrum listaddresses', shell=True)
    pattern = r'"([A-Za-z0-9_\./\\-]*)"'
    addresses = re.findall(pattern, addresses)
    conn = sqlite3.connect('/root/elctrm-chkr/murtcele.db')
    c = conn.cursor()
    counter = 0
    for i in range(0, len(addresses)):
        balance = subprocess.check_output('electrum getaddressbalance ' + addresses[i], shell=True)
        cur_balance = re.findall(pattern, balance)[1]

        if not c.execute("SELECT * FROM electrum WHERE address=?", (addresses[i],)).fetchone():
            c.execute("INSERT INTO electrum VALUES (?, 0)", (addresses[i],))
            conn.commit()
            continue

        c.execute("SELECT balance FROM electrum WHERE address=?", (addresses[i],))
        old_balance = c.fetchone()[0]
        print(str(old_balance) + '----' + addresses[i])
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
