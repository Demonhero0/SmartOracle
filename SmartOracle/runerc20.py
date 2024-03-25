from inv_miner import InvHunter
from contract import Contract
from rpc import getTxHashByBlockIndex
import time
import argparse
import json
import os
from multiprocessing import Pool

# load givenTxList
with open("temp/erc20tx.json","r") as f:
    givenTxList_dict = json.load(f)

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

            if os.path.exists(f"{outputTargetPath}/violatedTxs.json") and ignore_exist:
                continue
            print(f"start analyzing {self.dapp} {proxyAddr}")

            print("start mining")
            benignTxPath = f"{self.txPathSource}/{self.dapp}/txs"
            assert os.path.exists(benignTxPath), f"not existing benignTxPath, {benignTxPath}"
            hunter.contract.var_dict_list = hunter.contract.readVarDict(startBlock=0, endBlock=15000000, txNum=txNum, mode="mine", txPath=benignTxPath, dumpBool=True, excludePartialErr=True, givenTxList=givenTxList_dict[self.dapp])
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


# def run_RQ1_util(targetDapp):
#     print(targetDapp)
#     outputPath = "invs_erc20"
#     erc20_path = "erc20"
#     # print(todo_list)
#     # for item in range(90,101,2):
#     for item in [60,70]:
#         threshold = item / 100
#         dapp = Dapp(targetDapp, txPathSource=erc20_path, configPath=erc20_path, outputPath=outputPath)
#         dapp.run(2000, threshold=threshold, ignore_exist=True, dumpTime=False)

# if __name__ == "__main__":
#     erc20_path = "erc20"
#     dapp_list = os.listdir(erc20_path)
#     with Pool(20) as p:
#         p.map(run_RQ1_util, dapp_list)

if __name__ == "__main__":
    args = get_args()
    targetDapp = args.dapp
    train_num = args.train_num
    outputPath = args.output_path
    threshold = args.threshold
    ignore_exist = args.ignore_exist
    erc20_path = "erc20"
    dapp_list = os.listdir(erc20_path)
    if targetDapp == "all":
        for targetDapp in dapp_list:
            print(f"analyzing {targetDapp}")
            dapp = Dapp(targetDapp, txPathSource=erc20_path, configPath=erc20_path, outputPath=outputPath)
            dapp.run(train_num, threshold, ignore_exist)
    elif targetDapp in dapp_list:
        print(f"analyzing {targetDapp}")
        dapp = Dapp(targetDapp, txPathSource=erc20_path, configPath=erc20_path, outputPath=outputPath)
        dapp.run(train_num, threshold, ignore_exist)
