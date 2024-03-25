from multiprocessing import Pool
from main import *

def run_RQ2_util(targetDapp):
    configPath = f"dapps"
    txPathSource = "dapps_tx"
    outputPath = "invs_new_0322"
    train_num = 2000
    # for item in range(90,101,2):
    for item in [98]:
        threshold = item / 100
        dapp = Dapp(targetDapp, txPathSource=txPathSource, configPath=configPath, outputPath=outputPath)
        dapp.run(train_num, threshold=threshold)

if __name__ == "__main__":
    dapp_list = list(dapp_dict)
    with Pool(15) as p:
        p.map(run_RQ2_util, dapp_list)