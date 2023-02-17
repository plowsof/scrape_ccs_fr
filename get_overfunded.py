from monerorpc.authproxy import AuthServiceProxy, JSONRPCException
import requests
import json
import pprint
from operator import itemgetter

def order_transfers(get_transfers):
    order = get_transfers
    get_transfers["in"] = sorted(order["in"], key=itemgetter('height'), reverse=False)
    return get_transfers

data = requests.get("https://ccs.getmonero.org/index.php/projects")

the_list = data.json()
data = {}
for proposal in the_list["data"]:
    if proposal["address"]:
        address = proposal["address"]
        data[address] = {
            "title": proposal["title"],
            "target": proposal["target_amount"] * (10 ** 12),
            "raised": 0,
            "date_funded": False
        }

rpc_url = "http://127.0.0.1:18082/json_rpc"
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
for x in data:
    #if not data[x]["date_funded"]:
    if data[x]["raised"] > data[x]["target"]:
        money = data[x]["raised"] - data[x]["target"]
        money *= 10 ** -12
        total+=money
        print(f"{data[x]['title']} over funded by {money}")

print(f"Total xmr overfunded: {total}")
