from inv_miner import InvHunter
from contract import Contract
import time
import argparse
import json
import os

def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dapp', dest='dapp', type=str, default="qubit")
    parser.add_argument('--txPathSource', dest='txPathSource', type=str, default="../dapps_tx")
    parser.add_argument('--print_violations', dest='print_violations', type=bool, default=False)
    parser.add_argument('--train_num', dest='train_num', type=int, default=600)
    parser.add_argument('--threshold', dest='threshold', type=float, default=1)
    parser.add_argument('--output_path', dest='output_path', type=str, default="invs")
    parser.add_argument('-ignore_exist', dest='ignore_exist', action="store_true")
    args = parser.parse_args()
    return args

dapp_dict = {

    "20200215_bzx": [0, 9484687, 9484688, 9485000],
    "20200419_lendf_me": [0, 9899735, 9899736, 10000000],
    "20200420_uniswap": [0, 9894248, 9894249, 10000000],
    "20200618_bancor":[0, 10287616, 10287617, 11000000],
    "20200628_balancer":[0, 10355806, 10355807, 11000000],
    "20200701_veth":[0, 10368559, 10368560, 11000000],
    "20200804_opyn":[0, 10592395, 10592396, 11000000],
    # "20200914_bzx_dai":[0, 10849993, 10849994, 10860000],
    # "20200914_bzx_eth":[0, 10852721, 10852722, 10860000],
    "20200914_bzx_usdc":[0, 10847340, 10847341, 10860000],
    # "20200914_bzx_usdc":[0, 10847340, 0, 10847340],
    "20200929_eminence":[0, 10954410, 10954411, 11000000],
    "20201026_harvest_finance":[0, 11129473, 11129474, 11500000],
    "20201102_axion_network":[0, 11176740, 11176741, 11500000],
    "20201106_cheese_bank":[0, 11205647, 11205648, 11500000],
    "20201112_akropolis":[0, 11242697, 11242698, 11242698],
    "20201114_value_defi":[0, 11256672, 11256673, 11500000],
    "20201117_ousd":[0, 11272254, 11272255, 11500000],
    "20201118_88mph":[0, 11278386, 11278387, 11500000],
    "20201122_pickle_finance":[0, 11303122, 11303123, 11500000],
    "20201218_warp_finance_dai":[0, 11473329, 11473330, 11500000],
    "20201218_warp_finance_usdc":[0, 11473329, 11473330, 11500000],
    "20201229_cover":[0, 11540721, 11540722, 12000000],
    # "20210120_saddle_finance":[0, 11686742, 11686743, 12000000],
    "20210205_yearn_finance":[0, 11792350, 11792351, 12000000],
    "20210208_bt_finance":[0, 11817851, 11817852, 12000000],
    "20210213_alpha_finance":[0, 11846489, 11846490, 12000000],
    "20210222_primitive_finance":[0, 11903782, 11903783, 12000000],
    "20210227_furucombo":[0, 11940499, 11940500, 12000000],
    "20210227_yeld_finance":[0, 11929816, 11929817, 12000000],
    "20210308_dodo":[0, 12000164, 12000165, 12500000],
    "20210404_force_dao":[0, 12168995, 12168996, 12500000],
    "20210508_rari_capital":[0, 12394009, 12394010, 12500000],
    "20210512_xtoken":[0, 12419917, 12419918, 12500000],
    "20210616_alchemix":[0, 12645421, 12645422, 13000000],
    "20210628_thorchain":[0, 12723673, 12723674, 12800000],
    # "20210628_thorchain":[0, 12723673, 0, 12723673],
    "20210710_anyswap":[0, 12801738, 12801739, 13000000],
    "20210710_chainswap":[0, 12801460, 12801461, 13000000],
    "20210713_defipie":[0, 12815734, 12815735, 13000000], 
    "20210715_thorchain":[0, 12833113, 12833114, 13000000],
    "20210718_array_finance":[0, 12849786, 12849787, 13000000],
    "20210720_sanshu_inu":[0, 12865333, 12865334, 13000000],
    # "20210722_thorchain":[0, 12878652, 12878653, 12900000],
    "20210803_posicle_finance":[0, 12955062, 12955063, 13000000],
    "20210810_punk_protocol_dai":[0, 12995894, 12995895, 13000000],
    "20210810_punk_protocol_usdc":[0, 12995894, 12995895, 13000000],
    "20210810_punk_protocol_usdt":[0, 12995894, 12995895, 13000000],
    "20210811_poly_network":[0, 12996842, 12996843, 13000000],
    "20210829_xtoken":[0, 13118319, 13118320, 13500000],
    "20210830_cream_finance":[0, 13124590, 13124591, 13130000],
    "20210903_daomaker":[0, 13155320, 13155321, 13500000],
    # "20210909_dydx":[0, 13649856, 13649857, 14000000], # abonormal to normal
    "20210915_nowswap":[0, 13229000, 13229001, 13500000],
    "20211014_indexed_finance":[0, 13417948, 13417949, 13500000],
    "20211027_cream_finance":[0, 13499797, 13499798, 13500000],
    "20211102_vesper_finance":[0, 13537921, 13537922, 14000000],
    "20211121_formation_fi":[0, 13669660, 13669661, 14000000],
    "20211123_olympusdao":[0, 13668712, 13668713, 14000000],
    "20211127_dydx":[0,13695969, 13695970, 14000000],
    "20211128_monox":[0, 13715025, 13715026, 14000000],
    "20211211_sorbet_finance":[0, 13786401, 13786402, 14000000],
    "20211221_visor_finance":[0, 13849006, 13849007, 14000000],
    "20211230_sashimiswap":[0, 13905777, 13905778, 14000000],
    "20220127_qubit_finance":[0, 13806875, 13806876, 14500000],
    # "20220127_qubit_finance":[0, 14090169, 14090170, 14300000],
    "20220205_meter_io":[0, 14146529, 14146530, 14500000],
    # "20220205_meter_io2":[0, 14146529, 14146530, 14500000],
    "20220220_donationstaking":[0, 14245221, 14245222, 14500000],
    "20220305_bacon_protocol":[0, 14326931, 14326932, 14400000],
    "20220320_li_finance":[0, 14420686, 14420687, 14500000],
    "20220320_umbrella_network":[0, 14421983, 14421984, 14500000],
    "20220326_revest_finance":[0, 14465356, 14465357, 14500000],
    "20220402_inverse_finance":[0, 14506358, 14506359, 15000000],
    "20220417_beanstalk":[0, 14602789, 14602790, 14618821],
    "20220430_fei_rari_fuse":[0, 14684813, 14684814, 15000000],
    "20220430_saddle_finance":[0, 14684306, 14684307, 15000000],
    "20220516_feg":[0, 14789162, 14789163, 15000000],
    # "20220616_inverse_finance":[0, 14972418, 14972419, 15000000],
    "20220618_snood":[0, 14983663, 14983664, 15000000],
    # "20220725_audius":[0, 15201798, 15201799, 15500000],
    # "20220801_nomad_bridge":[0, 15259100, 15259101, 15500000],
}

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

            # if not os.path.exists(f"{self.outputPath}/{self.dapp}/{proxyAddr}"):
            #     os.mkdir(f"{self.outputPath}/{self.dapp}/{proxyAddr}")
            # if not os.path.exists(outputTargetPath):
            #     os.mkdir(outputTargetPath)
            os.makedirs(outputTargetPath, exist_ok=True)

            if os.path.exists(f"{outputTargetPath}/violatedTxs.json") and ignore_exist:
                # os.remove(f"{self.outputPath}/{self.dapp}/{proxyAddr}/violatedTxs.json")
                continue
            print(f"start analyzing {self.dapp} {proxyAddr}")

            print("start mining")
            mining_start_time = time.time()
            benignTxPath=f"{self.txPathSource}/{self.dapp}/{proxyAddr}"
            hunter.contract.var_dict_list = hunter.contract.readVarDict(startBlock=dapp_dict[self.dapp][0], endBlock=dapp_dict[self.dapp][1], txNum=txNum, mode="mine", txPath=benignTxPath, dumpBool=True, excludePartialErr=True)
            dtraceList = hunter.contract.extractDtrace(hunter.contract.var_dict_list, useCachedStorage=False)
            mined_dtraceList, methodAllCountDict = hunter.incrementalAlg(dtraceList,threshold=threshold, lowBar=0, max_methodCount=100)
            mining_end_time = time.time()
            print("end mining")
            with open(f"{outputTargetPath}/mine_methodAllCountDict.json", "w") as f:
                json.dump(methodAllCountDict, f)
            hunter.dumpTrace(mined_dtraceList, f"{outputTargetPath}/mine_dtraces.json")
            hunter.dumpInvDict(outputTargetPath)
            hunter.dumpKeyInvDict(hunter.keyInvDict, f"{outputTargetPath}/key_inv_dict.json")
            hunter.dumpKeyInvDict(hunter.reservedInvDict, f"{outputTargetPath}/reserved_inv_dict.json")

            print("start checking")
            checking_start_time = time.time()
            checked_dtraceList, checked_txs_num, violatedTxs = hunter.checkInvs(startBlock=dapp_dict[self.dapp][2], endBlock=dapp_dict[self.dapp][3], txPath=f"{self.txPathSource}/{self.dapp}/{proxyAddr}")
            checking_end_time = time.time()
            hunter.dumpTrace(checked_dtraceList, f"{outputTargetPath}/checked_dtraces.json")

            print("mining time: %.3f, number of txs: %d" % (mining_end_time - mining_start_time, len(mined_dtraceList)))
            print("checking time %.3f, number of txs: %d" % (checking_end_time - checking_start_time, checked_txs_num))
            print(f"Checked Txs {checked_txs_num}, violated Txs {len(violatedTxs)}")
            
            with open(f"{outputTargetPath}/violatedTxs.json", "w") as f:
                json.dump(violatedTxs, f)
            if dumpTime:
                with open(f"{outputTargetPath}/time.json","w") as f:
                    j = {
                        "mining_time" : mining_end_time - mining_start_time,
                        "mined_txs" : len(mined_dtraceList),
                        "checking_time" : checking_end_time - checking_start_time,
                        "checked_txs" : checked_txs_num,
                    }
                    json.dump(j, f)
if __name__ == "__main__":
    args = get_args()
    targetDapp = args.dapp
    train_num = args.train_num
    outputPath = args.output_path
    threshold = args.threshold
    ignore_exist = args.ignore_exist
    ignore_exist = False
    configPath = f"../dapps"
    txPathSource = "../dapps_tx"
    if targetDapp == "all":
        for targetDapp in dapp_dict:
            print(f"analyzing {targetDapp}")
            dapp = Dapp(targetDapp, txPathSource=txPathSource, configPath=configPath, outputPath=outputPath)
            dapp.run(train_num, threshold, ignore_exist)
    elif targetDapp in dapp_dict:
        print(f"analyzing {targetDapp}")
        dapp = Dapp(targetDapp, txPathSource=txPathSource, configPath=configPath, outputPath=outputPath)
        dapp.run(train_num, threshold, ignore_exist)
    else:
        print(f"not existing {targetDapp}")