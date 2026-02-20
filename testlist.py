import requests

url = "https://www.binance.com/bapi/defi/v1/public/wallet-direct/buw/wallet/cex/alpha/all/token/list"

resp = requests.get(url)
data = resp.json()

# 提取 contractAddress 列表
contract_list = [
    item["contractAddress"]
    for item in data["data"]
    # if item.get("contractAddress") and 
    if item.get("chainName") == "BSC"
]

contract_list = contract_list[:100]

with open("testlist.txt", "w", encoding="utf-8") as f:
    for addr in contract_list:
        f.write(addr + "\n")

print(f"wrote {len(contract_list)} addresses to testlist.txt")
