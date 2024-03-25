from inv_miner import InvHunter
from contract import Contract
from rpc import getTxHashByBlockIndex
import time
import argparse
import json
import os
from multiprocessing import Pool

# load givenTxList
# with open("temp/erc20tx.json","r") as f:
#     givenTxList_dict = json.load(f)

def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dapp', dest='dapp', type=str, default="qubit")
    parser.add_argument('--print_violations', dest='print_violations', type=bool, default=False)
    parser.add_argument('--train_num', dest='train_num', type=int, default=2000)
    parser.add_argument('--threshold', dest='threshold', type=float, default=1)
    parser.add_argument('--output_path', dest='output_path', type=str, default="invs_erc20")
    parser.add_argument('-ignore_exist', dest='ignore_exist', action="store_true")
    args = parser.parse_args()
    return args

class Dapp(object):

    def __init__(self, dapp, txPathSource, configPath, outputPath):

        assert os.path.exists(f"{configPath}/{dapp}/config.json"), f"not exising {configPath}/{dapp}/config.json"
        with open(f"{configPath}/{dapp}/config.json", "r") as f:
            config = json.load(f)
        
        if not os.path.exists(f"{outputPath}/{dapp}"):
            os.mkdir(f"{outputPath}/{dapp}")

        self.dapp = dapp
        self.txPathSource = txPathSource
        self.outputPath = outputPath
        self.invHunters = dict()
        for proxyAddr in config:
            contract = Contract(proxyAddr=proxyAddr, contractConfig=config[proxyAddr], sourcePath=f"{configPath}/{dapp}/{proxyAddr}", outputPath=f"{outputPath}/{dapp}/{proxyAddr}")
            self.invHunters[proxyAddr] = InvHunter(contract)

    def run(self, txNum, threshold, ignore_exist=True, dumpTime=False):
        for proxyAddr, hunter in self.invHunters.items():
            outputTargetPath = f"{self.outputPath}/{self.dapp}/{proxyAddr}/result/{txNum}_{threshold}"
            os.makedirs(outputTargetPath, exist_ok=True)

            if os.path.exists(f"{outputTargetPath}/key_inv_dict.json") and ignore_exist:
                continue
            print(f"start analyzing {self.dapp} {proxyAddr}")

            print("start mining")
            benignTxPath = f"{self.txPathSource}/{self.dapp}/txs"
            assert os.path.exists(benignTxPath), f"not existing benignTxPath, {benignTxPath}"
            hunter.contract.var_dict_list = hunter.contract.readVarDict(startBlock=0, endBlock=15000000, txNum=txNum, mode="check", txPath=benignTxPath, dumpBool=True, excludePartialErr=True)
            dtraceList = hunter.contract.extractDtrace(hunter.contract.var_dict_list, True)
            mined_dtraceList, methodAllCountDict = hunter.incrementalAlg(dtraceList, threshold=threshold, lowBar=0)
            print("end mining")
            with open(f"{outputTargetPath}/mine_methodAllCountDict.json", "w") as f:
                json.dump(methodAllCountDict, f)
            hunter.dumpTrace(mined_dtraceList, f"{outputTargetPath}/mine_dtraces.json")
            hunter.dumpInvDict(outputTargetPath)
            # hunter.dumpKeyInvDict(outputTargetPath)
            hunter.dumpKeyInvDict(hunter.keyInvDict, f"{outputTargetPath}/key_inv_dict.json")
            hunter.dumpKeyInvDict(hunter.reservedInvDict, f"{outputTargetPath}/reserved_inv_dict.json")

def run_RQ1_tx_util(targetDapp):
    print(targetDapp)
    outputPath = "invs_erc20_txs_new"
    erc20_path = "erc20"
    # print(todo_list)
    # for item in range(90,101,2):
    # for tx_num in [100, 200, 300, 500, 800, 1000, 2000]:
    # for tx_num in [2500, 3000, 3500, 4000, 4500, 5000]:
    # for tx_num in range(200, 2000, 200):
    for tx_num in [2000]:
        print(targetDapp, tx_num)
        dapp = Dapp(targetDapp, txPathSource=erc20_path, configPath=erc20_path, outputPath=outputPath)
        dapp.run(tx_num, threshold=1, ignore_exist=True, dumpTime=False)

if __name__ == "__main__":
    erc20_path = "erc20"
    # dapp_list = os.listdir(erc20_path)
    dapp_list = [
# "0x14202ad496e7281e5bea4b56b5b7919e64f07c55",
# "0x202f1877e1db1120ca3e9a98c5d505e7f035c249",
# "0x30c8aa625361d62357706a203ff81d96c6d56459",
# "0x31fdd1c6607f47c14a2821f599211c67ac20fa96",
# "0x3301ee63fb29f863f2333bd4466acb46cd8323e6",
# "0xe09fb60e8d6e7e1cebbe821bd5c3fc67a40f86bf",
# "0x6eda39647d9da13f03ed60bae308480e87078d0e",
# "0x537edd52ebcb9f48ff2f8a28c51fcdb9d6a6e0d4",
# "0x89d3c0249307ae570a316030764d12f53bb191fd",
# "0x8fcf83c9ec197585cf9c76648ee0e3dc0924017c",
# "0x9256da34b0ca457bbdf325fb28cdd15b1976d5d9",
# "0x9e8bfe46f9af27c5ea5c9c72b86d71bb86953a0c",
# "0xaebbd7b2eb03f84126f6849753b809755d7532f9",
# "0xbfd815347d024f449886c171f78fa5b8e6790811",
# "0xc53d46fd66edeb5d6f36e53ba22eee4647e2cdb2",
# "0xed40834a13129509a89be39a9be9c0e96a0ddd71",
# "0xf3ae5d769e153ef72b4e3591ac004e89f48107a1"

"0x202f1877e1db1120ca3e9a98c5d505e7f035c249",
"0x3301ee63fb29f863f2333bd4466acb46cd8323e6",
"0xe09fb60e8d6e7e1cebbe821bd5c3fc67a40f86bf",
"0x537edd52ebcb9f48ff2f8a28c51fcdb9d6a6e0d4",
"0xbfd815347d024f449886c171f78fa5b8e6790811",
"0xed40834a13129509a89be39a9be9c0e96a0ddd71",
"0xf3ae5d769e153ef72b4e3591ac004e89f48107a1",
    ]
    with Pool(len(dapp_list)) as p:
        p.map(run_RQ1_tx_util, dapp_list)

# if __name__ == "__main__":
#     args = get_args()
#     targetDapp = args.dapp
#     train_num = args.train_num
#     outputPath = args.output_path
#     threshold = args.threshold
#     ignore_exist = args.ignore_exist
#     erc20_path = "erc20"
#     dapp_list = os.listdir(erc20_path)
#     if targetDapp == "all":
#         for targetDapp in dapp_list:
#             print(f"analyzing {targetDapp}")
#             dapp = Dapp(targetDapp, txPathSource=erc20_path, configPath=erc20_path, outputPath=outputPath)
#             dapp.run(train_num, threshold, ignore_exist)
#     elif targetDapp in dapp_list:
#         print(f"analyzing {targetDapp}")
#         dapp = Dapp(targetDapp, txPathSource=erc20_path, configPath=erc20_path, outputPath=outputPath)
#         dapp.run(train_num, threshold, ignore_exist)
