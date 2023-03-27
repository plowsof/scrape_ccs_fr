from monerorpc.authproxy import AuthServiceProxy, JSONRPCException
import requests
import json
import pprint
from operator import itemgetter

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
            "date_funded": False
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

total=0

overfunded=[]
for x in data:
    if data[x]["raised"] > int(data[x]["target"]):
        atomic_units = data[x]["raised"] - int(data[x]["target"])
        total+=atomic_units
        info = {
        "title":data[x]['title'],
        "amount":atomic_units,
        "address": x
        }
        overfunded.append(info)

print(f"Total xmr overfunded: {formatAmount(total,12)}")

overfunded = sorted(overfunded, reverse=True, key=lambda x: float(x['amount']))

print("| Amount | Title | Address | atomic units |")
print("| --- | --- | --- |")
for x in overfunded:
    print(f"| {formatAmount(x['amount'],12)} | {x['title']} | {x['address']} | {x['amount']} |")
