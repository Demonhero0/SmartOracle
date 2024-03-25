from multiprocessing import Pool
from main import *

def run_RQ1_util(targetDapp):
    configPath = f"dapps"
    txPathSource = "../invFuzz/hunter/dapps_withCallLocation_new"
    outputPath = "invs_RQ1"
    todo_list = [10, 50]
    todo_list.extend([x * 100 for x in range(1,11)])
    # print(todo_list)
    for train_num in todo_list:
        dapp = Dapp(targetDapp, txPathSource=txPathSource, configPath=configPath, outputPath=outputPath)
        dapp.run(train_num, threshold=1, ignore_exist=True)

if __name__ == "__main__":
    dapp_list = list(dapp_dict)
    # dapp_list = ["20210830_cream_finance"]
    with Pool(12) as p:
        p.map(run_RQ1_util, dapp_list)