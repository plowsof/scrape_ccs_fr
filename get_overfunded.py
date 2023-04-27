from monerorpc.authproxy import AuthServiceProxy, JSONRPCException
import requests
import json
import pprint
from operator import itemgetter
import subprocess
import sys
import time
import datetime

node_address = "http://node2.monerodevs.org:18089"
local_rpc = "http://localhost:18084"
def start_monero_rpc():
    global node_address, local_rpc
    rpc_args = [ 
        "./monero-wallet-rpc", 
        "--wallet-file", "ccs",
        "--rpc-bind-port", "18084",
        "--disable-rpc-login",
        "--password", "",
        "--daemon-address", node_address,
        "--log-level", "0",
        "--no-initial-sync"
    ]
    #start monero-wallet-rpc
    monero_daemon = subprocess.Popen(rpc_args,stdout=subprocess.PIPE)
    for line in iter(monero_daemon.stdout.readline,''):
        if b"Error" in line.rstrip() or b"Failed" in line.rstrip():
            sys.exit(1)
        if b"Starting wallet RPC server" in line.rstrip():
            break

    #make connections to local/remote
    local_rpc = local_rpc + "/json_rpc"
    node_address = node_address + "/json_rpc"
    remote_rpc_connection = AuthServiceProxy(service_url=node_address)
    local_rpc_connection = AuthServiceProxy(service_url=local_rpc)

    current_height = 0
    target_height= 1
    while current_height != target_height:
        try:
            response = requests.post(
                'http://127.0.0.1:18084/json_rpc',
                json={'jsonrpc': '2.0', 'id': '0', 'method': 'get_height'}
            )
            current_height = response.json()['result']['height']
            target_height = remote_rpc_connection.get_info()["height"]
            print(f"Current height:{current_height}")
            print(f"Target height:{target_height}")
            time.sleep(1)
        except JSONRPCException as e:
            print(f"Failed to get height from RPC: {str(e)}")
            sys.exit(1)
    print("we are fully synced")
    
def order_transfers(get_transfers):
    order = get_transfers
    get_transfers["in"] = sorted(order["in"], key=itemgetter('height'), reverse=False)
    return get_transfers

def formatAmount(amount,units):
    """decode cryptonote amount format to user friendly format.
    Based on C++ code:
    https://github.com/monero-project/bitmonero/blob/master/src/cryptonote_core/cryptonote_format_utils.cpp#L751
    """
    CRYPTONOTE_DISPLAY_DECIMAL_POINT = int(units)
    s = str(amount)
    if len(s) < CRYPTONOTE_DISPLAY_DECIMAL_POINT + 1:
        # add some trailing zeros, if needed, to have constant width
        s = '0' * (CRYPTONOTE_DISPLAY_DECIMAL_POINT + 1 - len(s)) + s
    idx = len(s) - CRYPTONOTE_DISPLAY_DECIMAL_POINT
    s = s[0:idx] + "." + s[idx:]

    #my own hack to remove trailing 0's, and to fix the 1.1e-5 etc
    trailing = 0
    while trailing == 0:
        if s[-1:] == "0":
            s = s[:-1]
        else:
            trailing = 1
    return s

def main():
    data = requests.get("https://ccs.getmonero.org/index.php/projects")

    the_list = data.json()
    data = {}
    for proposal in the_list["data"]:
        if proposal["address"]:
            address = proposal["address"]
            if "." in str(proposal["target_amount"]):
                part = str(proposal["target_amount"]).split(".")
                whole = part[0]
                dec = part[1]
                dec = int(dec) * (10 ** (12-len(dec)))
                whole = int(whole) * (10 ** 12)
                total = dec + whole
                proposal["target_amount"] = dec + whole
            else:
                proposal["target_amount"] *= (10 ** 12)
            data[address] = {
                "title": proposal["title"],
                "target": str(proposal["target_amount"]).replace(".0",""),
                "raised": 0,
                "date_funded": False,
                "donations": 0,
                "ids": []
            }

    rpc_url = "http://127.0.0.1:18084/json_rpc"
    rpc_connection = AuthServiceProxy(service_url=rpc_url)
    # get list of all used addresses
    all_add = rpc_connection.get_address()

    for a in all_add["addresses"]:
        address = a["address"]
        index = a["address_index"]
        # address is listed in the projects json
        if address in data:
            params={
                    "index": {
                    "major": 0,
                    "minor": index,
                    },
                    "label": data[address]["title"]
                    }
            # set label for subaddress
            info = rpc_connection.label_address(params)

    for a in all_add["addresses"]:
        address = a["address"]
        index = a["address_index"]
        title = a["label"]
        if not a["used"]:
            continue

        if address not in data:
            continue

        params = {
            "in": True,
            "account_index": 0,
            "subaddr_indices": [index]
        }
        info = rpc_connection.get_transfers(params)
        info = order_transfers(info)
        msg = 0
        for tx in info["in"]:
            data[address]["raised"] += tx["amount"]
            data[address]["donations"] += 1
            data[address]["ids"].append(tx["txid"])

    total=0

    overfunded=[]
    for x in data:
        title=data[x]["title"]
        raised=data[x]["raised"]
        donations=data[x]["donations"]
        txids=data[x]["ids"]
        if data[x]["raised"] > int(data[x]["target"]):
            atomic_units = data[x]["raised"] - int(data[x]["target"])
            total+=atomic_units
            info = {
            "title":data[x]['title'],
            "amount":atomic_units,
            "address": x
            }
            overfunded.append(info)

    overfunded = sorted(overfunded, reverse=True, key=lambda x: float(x['amount']))
    return overfunded, total

def edit_readme():
    overfunded, total = main()
    # Open README.md file in read mode
    with open('README.md', 'r') as file:
        # Read all the lines in the file
        lines = file.readlines()

    # Open README.md file in write mode
    with open('README.md', 'w') as file:
        # Set a flag to track if the previous line was '---'
        previous_line_dash = False
        # Loop through each line in the lines list
        for line in lines:
            # Check if the previous line was '---'
            if previous_line_dash:
                file.write(f"\nTotal overfunding: {formatAmount(total, 12)}    \n")
                current_date = datetime.datetime.now().strftime("%Y-%m-%d")
                file.write(f"Last Updated: {current_date}    \n")
                file.write("| Amount | Title | Address | atomic units |\n")
                file.write("| --- | --- | --- | --- |\n")
                for x in overfunded:
                    file.write(f"| {formatAmount(x['amount'],12)} | {x['title'].replace('|','/')} | {x['address']} | {x['amount']} |\n")
                break
            # Check if the current line is '---'
            if line.strip() == '---':
                print("INIT")
                # Set the flag for the next iteration
                previous_line_dash = True
            # Write the line to the file
            file.write(line)



start_monero_rpc()
edit_readme()

local_rpc_connection = AuthServiceProxy(service_url="http://localhost:18084/json_rpc")
local_rpc_connection.stop_wallet()
