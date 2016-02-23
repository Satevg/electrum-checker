import argparse
import electrum
import json
import os
import re
import requests
import sqlite3
import subprocess

from electrum.wallet import WalletStorage, NewWallet

parser = argparse.ArgumentParser()
parser.add_argument("--generate_address", help="Generate recieving address", type=int)
parser.add_argument("--check_balance", help="Check balance", type=str)
args = parser.parse_args()

storage = WalletStorage('/home/satevg/.electrum/wallets/default_wallet')
w = electrum.wallet.NewWallet(storage)

if not os.path.isfile('murtcele.db'):
    conn = sqlite3.connect('murtcele.db')
    c = conn.cursor()
    c.execute("CREATE TABLE electrum (address text, balanse real)")

    # fill db with wallet addresses
    addresses = subprocess.check_output('electrum listaddresses', shell=True)
    pattern = r'"([A-Za-z0-9_\./\\-]*)"'
    addresses = re.findall(pattern, addresses)

    insert = []
    for i in range(0, len(addresses)):
        print addresses[i]
        balance = subprocess.check_output('electrum getaddressbalance ' + addresses[i], shell=True)
        balance = re.findall(pattern, balance)[1]
        insert.append((addresses[i], balance))

    c.executemany('INSERT INTO electrum VALUES (?,?)', insert)
    conn.commit()
    conn.close()

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

    print json.dumps(addresses) # new addr list

if args.check_balance:
    addresses = subprocess.check_output('electrum listaddresses', shell=True)
    pattern = r'"([A-Za-z0-9_\./\\-]*)"'
    addresses = re.findall(pattern, addresses)
    conn = sqlite3.connect('murtcele.db')
    c = conn.cursor()
    for i in range(0, len(addresses)):
        balance = subprocess.check_output('electrum getaddressbalance ' + addresses[i], shell=True)
        cur_balance = re.findall(pattern, balance)[1]
        c.execute("SELECT balanse from electrum where address=?", (addresses[i],))
        if c.fetchone()[0]:
            if old_balance != cur_balance:
                r = requests.post(args.check_balance, data={'address': addresses[i],
                                                              'last_balance': old_balance,
                                                              'cur_balance': cur_balance})
    conn.close()