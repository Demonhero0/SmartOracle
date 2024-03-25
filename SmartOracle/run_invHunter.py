from multiprocessing import Pool
from main import *

def run_RQ1_util(targetDapp):
    print(targetDapp)
    configPath = f"dapps"
    txPathSource = "dapps_tx"
    outputPath = "invs"
    todo_list = [600]
    # print(todo_list)
    for train_num in todo_list:
        dapp = Dapp(targetDapp, txPathSource=txPathSource, configPath=configPath, outputPath=outputPath)
        dapp.run(train_num, threshold=1, ignore_exist=True, dumpTime=False)

if __name__ == "__main__":
    dapp_list = list(dapp_dict)
    with Pool(20) as p:
        p.map(run_RQ1_util, dapp_list)