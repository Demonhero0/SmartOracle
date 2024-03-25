from contract import *
from patterns import *
import re

# compare the user-supplied data and contract status
# 1 - tokenBalance
# 2 - user-supplied
# 3 - contract status
ComparabilityDict = {
    "tokenBalance": 1,
    "msg.value": 2,
    "block.timestamp": 2,
    "block.number": 2,

    # address
    "callee": 2,
    "msg.sender": 2,
    "tx.origin": 2,

    # method
    "method": 2,
    # event
    "event": 3,
    # variable
    "variable": 3,
    # change
    "change": 3,
}


def splitPointAndVariable(var_name):
    if var_name.startswith("pre(") or var_name.startswith("post(") or var_name.startswith("subCall"):
        new_var_name = "(".join(var_name.split("(")[1:])[:-1]
        return new_var_name, var_name.split("(")[0]
    return var_name, None

def isComparable(var_name, compared_var_name):
    var_name, var_name_point = splitPointAndVariable(var_name)
    compared_var_name, compared_var_name_point = splitPointAndVariable(compared_var_name)

    comparability = getComparability(var_name)
    compared_comparability = getComparability(compared_var_name)

    # if var_name_point == "pre" and compared_var_name == "pre":
    #     # do not compare in pre
    #     return False
    if comparability == -1 or compared_comparability == -1:
        return False
    elif isinstance(comparability, str) or isinstance(compared_comparability, str):
        # deal with token Balance
        # print(comparability, compared_comparability)
        if var_name_point == compared_var_name_point:
            return False
        else:
            return comparability == compared_comparability
    elif comparability == 3 or compared_comparability == 3:
        return True
    elif comparability == 2 and compared_comparability == 2:
        # do not check the cases that both variables are provided by user
        return False
        # print(comparability, compared_comparability)
    return False

def getComparability(var_name):
    if var_name in ComparabilityDict:
        return ComparabilityDict[var_name]
    elif "-pre(" in var_name and "post(" in var_name:
        return ComparabilityDict["change"]
    else:
        var_type = var_name.split(".")[0]
        # print(var_name, var_type)
        # deal with tokenBalance
        if var_type == "tokenBalance":
            tokenAddresss_user = ".".join(var_name.split('.')[1:])
            return f"{ComparabilityDict[var_type]}_{tokenAddresss_user}"
        else:
            return ComparabilityDict[var_type]

class InvHunter(object):
    
    def __init__(self, contract) -> None:
        self.contract = contract

        self.invDict = dict()
        self.invDictPerTx = dict()
        self.keyInvDict = dict()

        self.tracesDict = dict()

    def initContract(self, startBlock, endBlock, txNum, benignTxPath):
        # original txs
        assert os.path.exists(benignTxPath), f"not existing benignTxPath, {benignTxPath}"
        benign_var_dict_list = self.contract.readVarDict(startBlock=startBlock, endBlock=endBlock, txNum=txNum, mode="mine", txPath=benignTxPath, dumpBool=True, excludePartialErr=True)
        # self.contract.slot_var_dict, self.contract.var_slot_dict = self.contract.extractVarInStorage(benign_var_dict_list, jsonPath="benign")
        self.contract.var_dict_list = benign_var_dict_list
        # self.contract.extractDeclAndVarDict(var_dict_list = benign_var_dict_list, jsonPath="benign")
        # self.declInfo_dict = self.getExtractedDeclInfo()

    def dumpKeyInvDict(self, keyInvDict, outputPath):
        dumpDict = dict()
        for methodString in keyInvDict:
            if methodString not in dumpDict:
                dumpDict[methodString] = dict()
            for inv, item in keyInvDict[methodString].items():
                if item['type'] == "normal":
                    dumpDict[methodString][inv] = [item['type'], item['model'].getVars()]
                elif item['type'] == "arithmetic":
                    dumpDict[methodString][inv] = [item['type'], item["model"].dumpModel()]
                elif item['type'] == "inference":
                    dumpDict[methodString][inv] = [item['type'], item["model"].getModel()]
        with open(outputPath, "w") as f:
            json.dump(dumpDict, f)

    def dumpInvDictPerTx(self, outputPath):
        with open(f"{outputPath}/inv_dict_perTx.json", "w") as f:
            json.dump(self.invDictPerTx, f)

    def dumpTrace(self, dtraceList, outputPath):
        with open(outputPath, "w") as f:
            json.dump(dtraceList, f)

    def dumpInvDict(self, outputPath):
        dumpedInvDict = dict()
        for methodString in self.invDict:
            dumpedInvDict[methodString] = dict()
            dumpedInvDict[methodString]["count"] = self.invDict[methodString]["count"]
            dumpedInvDict[methodString]["invs"] = dict()
            # print(sorted(self.invDict[methodString]["invs"].items(), key = lambda kv:(kv[1]["num"], kv[0]), reverse=True))
            for item in sorted(self.invDict[methodString]["invs"].items(), key = lambda kv:(kv[1]["num"], kv[0]), reverse=True):
                dumpedInvDict[methodString]["invs"][item[0]] = {"num":item[1]['num'], "type":item[1]['type']}
        
        with open(f"{outputPath}/inv_dict.json", "w") as f:
            json.dump(dumpedInvDict, f)

    def mineSingleVar(self, var_name, traceDict):
        relation_dict = dict()
        for SingleInv in SingleInvList:
            temp_inv = SingleInv(var_name)
            flag = temp_inv.constructRelation(traceDict[var_name][0])
            if flag:
                relation_dict[str(temp_inv)] = temp_inv
        return relation_dict

    def mineVar(self, var_name, compared_var_name, traceDict):
        relation_dict = dict()
        # do not deal with some cases
        if isComparable(var_name, compared_var_name):
            # if isinstance(traceDict[var_name], tuple) and isinstance(traceDict[compared_var_name], tuple):
            if traceDict[var_name][1] not in ['array','mapping'] and traceDict[compared_var_name][1] not in ['array','mapping']:
                var_type = traceDict[var_name][1]
                # print(var_name, var_type, traceDict[var_name][0])
                var_value = traceDict[var_name][0].lower() if var_type == "address" else traceDict[var_name][0]
                compared_var_type = traceDict[compared_var_name][1]
                compared_var_value = traceDict[compared_var_name][0].lower() if compared_var_type == "address" else traceDict[compared_var_name][0]
                
                for ComparisonRelation in ComparisonRelationList:
                    comparisonRelation = ComparisonRelation(var_name, compared_var_name)
                    flag = comparisonRelation.constructRelation(var_value, compared_var_value)
                    if flag:
                        relation_dict[str(comparisonRelation)] = comparisonRelation

                # deal with bytes
                else:
                    if compared_var_type[:5] == "bytes":
                        membershipBytesRelation = MembershipBytesRelation(var_name, compared_var_name)
                        flag = membershipBytesRelation.constructRelation(var_value, compared_var_value)
                        if flag:
                            relation_dict[str(membershipBytesRelation)] = membershipBytesRelation
                    if var_type[:5] == "bytes":
                        membershipBytesRelation = MembershipBytesRelation(compared_var_name, var_name)
                        flag = membershipBytesRelation.constructRelation(compared_var_value, var_value)
                        if flag:
                            relation_dict[str(membershipBytesRelation)] = membershipBytesRelation
            elif traceDict[var_name][1] == "array" and traceDict[compared_var_name][1] not in ['array','mapping']:
            # elif isinstance(traceDict[var_name], list) and isinstance(traceDict[compared_var_name], tuple):
                var_value = traceDict[var_name] # list
                compared_var_value = traceDict[compared_var_name][0] # tuple
                membershipRelation = MembershipRelation(compared_var_name, var_name)
                flag = membershipRelation.constructRelation(compared_var_value, var_value)
                if flag:
                    relation_dict[str(membershipRelation)] = membershipRelation
            elif traceDict[var_name][1] not in ['array','mapping'] and traceDict[compared_var_name][1] == 'array':
            # elif isinstance(traceDict[var_name], tuple) and isinstance(traceDict[compared_var_name], list):
                var_value = traceDict[var_name][0] # tuple
                compared_var_value = traceDict[compared_var_name] # list
                membershipRelation = MembershipRelation(var_name, compared_var_name)
                flag = membershipRelation.constructRelation(var_value, compared_var_value)
                if flag:
                    relation_dict[str(membershipRelation)] = membershipRelation
            elif traceDict[var_name][1] == "array" and traceDict[compared_var_name][1] == "array":
            # elif isinstance(traceDict[var_name], list) and isinstance(traceDict[compared_var_name], list):
                pass
            else:
                assert False, f"unkonwn type {traceDict[var_name]} and {traceDict[compared_var_name]}"

        return relation_dict

    def mineMethodModel(self, methodIntDict, low_threshold):
        model_dict = dict()
        for var_name in methodIntDict["vars"]:
            assert len(methodIntDict["vars"][var_name]) == methodIntDict["count"], f'unmatched intDict {len(methodIntDict["vars"][var_name])} != {methodIntDict["count"]}'

        for x_name, xList in methodIntDict["vars"].items():
            if len(xList) < low_threshold:
                continue
            for y_name, yList in methodIntDict["vars"].items():
                if x_name == y_name:
                    continue
                x_y_list = []
                for index, x in enumerate(xList):
                    if x != "nonsensical" and x != 0 and yList[index] != "nonsensical" and yList[index] != 0:
                        x_y_list.append([x, yList[index]])
                if len(x_y_list) > low_threshold:
                    # print(x_name, y_name, type(xList[0]), type(yList[0]))
                    # print(len(x_y_list), len(xList), len(yList))
                    for ModelRelation in modelRelationWithTwoVarList:
                        try:
                            modelRelation = ModelRelation(x_name, y_name)
                            flag = modelRelation.constructRelation(x_y_list)
                            if flag:
                                model_dict[str(modelRelation)] = modelRelation
                                # model_dict[methodString][str(modelRelation)]["type"] = "model"
                                # model_dict[methodString][str(modelRelation)]["model"] = modelRelation
                        except:
                            pass
                # deal with three items
                # for z_name, zList in intDict[methodString]["vars"].items():
                #     x_y_z_list = []
                #     if z_name == y_name or z_name == x_name:
                #         continue
                #     for index, _ in enumerate(xList):
                #         if xList[index] != "nonsensical" and xList[index] != 0 and yList[index] != "nonsensical" and yList[index] != 0 and zList[index] != "nonsensical" and zList[index] != 0:
                #             x_y_z_list.append([xList[index], yList[index], zList[index]])
                #     if len(x_y_z_list) >= low_threshold:
                #         for ModelRelation in modelRelationWithTwoVarList:
                #             try:
                #                 modelRelation = ModelRelation(x_name, y_name, z_name)
                #                 flag, _ = modelRelation.constructRelation(x_y_z_list)
                #                 if flag:
                #                     model_dict[methodString][str(modelRelation)] = modelRelation
                #                     # model_dict[methodString][str(modelRelation)]["type"] = "model"
                #                     # model_dict[methodString][str(modelRelation)]["model"] = modelRelation
                #             except:
                #                 pass
    
        return model_dict


    # def recoverAndFlatTraceDict(self, traceDict):
    #     essentialDtrace = dict()
    #     # reserve the normal dtrace
    #     keyList = list(traceDict)
    #     for key in keyList:
    #         if type(traceDict[key]) != dict:
    #             essentialDtrace[key] = traceDict.pop(key)
        
    #     originalDtrace = traceDict

    #     while True:
    #         isStatic = True
    #         newDtraceDict = dict()
    #         for var_name in originalDtrace:
    #             removeKeys = set()
    #             for key in originalDtrace[var_name]:
    #                 for replacement in essentialDtrace:
    #                     if isinstance(essentialDtrace[replacement], tuple):
    #                         var_value = essentialDtrace[replacement][0]
    #                         if var_value == key:
    #                             new_var_name = var_name.replace("[...]", f"[{replacement}]")
    #                             newDtraceDict[new_var_name] = originalDtrace[var_name][key]
    #                             isStatic = False
    #                             removeKeys.add(key)
    #             for key in removeKeys:
    #                 originalDtrace[var_name].pop(key)
                    
    #         for var_name in newDtraceDict:
    #             essentialDtrace.update(self.flatDtrace(var_name, newDtraceDict[var_name]))
    #         if isStatic:
    #             break
        
    #     return essentialDtrace
        
    def inferInvs(self, normal_relation_dict, traceDict):
        new_relation_dict = normal_relation_dict
        oldRelation = set(list(normal_relation_dict.keys()))
        
        while True:
            newRelation = set()
            for inv in oldRelation:
                for var_name, var_value in traceDict.items():
                    if isinstance(var_value, tuple) and type(var_value[0]) == str:
                        var_value = var_value[0]
                        if len(var_value) > 2:
                            inferenceRelation = InferenceRelation(new_relation_dict[inv], var_name)
                            flag = inferenceRelation.constructRelation(var_value)
                            if flag:
                                if str(inferenceRelation) not in new_relation_dict:
                                    new_relation_dict[str(inferenceRelation)] = inferenceRelation
                                    newRelation.add(str(inferenceRelation))
            if len(newRelation) == 0:
                break
            else:
                oldRelation = newRelation
                # for relation in newRelation:
                #     print(relation)
                #     print(new_relation_dict[relation], new_relation_dict[relation].x_replaceFormat, new_relation_dict[relation].y_replaceFormat)
                # print("----------------------------")
                            

        # new_relation_dict = dict()
        # for inv in normal_relation_dict:
        #     for var_name, var_value in traceDict.items():
        #         if isinstance(var_value, tuple):
        #             var_value = var_value[0]
        #             if isinstance(var_value,str) and len(var_value) > 2:
        #                 inferenceRelation = InferenceRelation(normal_relation_dict[inv], var_name)
        #                 flag = inferenceRelation.constructRelation(var_value)
        #                 if flag:
        #                     new_relation_dict[str(inferenceRelation)] = inferenceRelation
        #                     # print(str(normal_relation_dict[inv]), "=>", str(inferenceRelation))
        return new_relation_dict
    
    def getIntDecl(self):
        int_dict = dict()
        for methodString in self.contract.extractedDecl:
            int_dict[methodString] = dict()
            for decl, decl_type in self.contract.extractedDecl[methodString]["decls"].items():
                if "int" in decl_type and "[..]" not in decl:
                    for point in self.contract.extractedDecl[methodString]["points"]:
                        int_dict[methodString][f"{point}({decl})"] = []
        return int_dict

    def selectKeyInvs(self, relationCount, intDict, lowBar = 3):
        
        allZeroVar = set()
        for var_name in intDict:
            if set(intDict[var_name]) == set([0, "nonsensical"]) or set(intDict[var_name]) == set([0]) or set(intDict[var_name]) == set(["nonsensical"]):
                allZeroVar.add(var_name)

        keyInvDict = dict()
        for methodString in relationCount:
            keyInvDict[methodString] = dict()
            for inv, invInfo in relationCount[methodString]["invs"].items():
                if invInfo["num"] < lowBar:
                    continue
                if invInfo["type"] == "normal":
                    # can only check normal invariants, inference can not handle
                    # remove the inv that one of item is all zero
                    allZero = False
                    for var_name in relationCount[methodString]["invs"][inv]["model"].getVars():
                        if var_name in allZeroVar:
                            allZero = True
                            break
                    # collect the invs that satisfy threshold
                    if not allZero:
                        # del invInfo["num"]
                        keyInvDict[methodString][inv] = invInfo
                else:
                    keyInvDict[methodString][inv] = invInfo
        return keyInvDict
    
    def searchInvs(self, methodString, traceDict, relationDict):

        # extract normal relaation
        normal_relation_dict = dict() # map str(relation) => relation
        var_name_list = list(traceDict.keys())
        for index, var_name in enumerate(var_name_list):
            # normal_relation_dict.update(self.mineSingleVar(var_name=var_name, traceDict=traceDict))
            for compared_var_name in var_name_list[index + 1:]:
                # if methodString == "transfer(address,uint256)":
                #     print(var_name, compared_var_name)
                normal_relation_dict.update(self.mineVar(var_name, compared_var_name, traceDict))

        # for relation in normal_relation_dict:
        #     if relation not in relationDict[methodString]["invs"]:
        #         relationDict[methodString]["invs"][relation] = dict()
        #         relationDict[methodString]["invs"][relation]["num"] = 0
        #         relationDict[methodString]["invs"][relation]["type"] = "normal"
        #         relationDict[methodString]["invs"][relation]["model"] = normal_relation_dict[relation]
        #     relationDict[methodString]["invs"][relation]["num"] += 1

        #  extraxt infer relation
        all_relation_dict = self.inferInvs(normal_relation_dict, traceDict)
        for relation in all_relation_dict:
            if relation not in relationDict[methodString]["invs"]:
                relationDict[methodString]["invs"][relation] = dict()
                relationDict[methodString]["invs"][relation]["num"] = 0
                relationDict[methodString]["invs"][relation]["type"] = all_relation_dict[relation].type
                relationDict[methodString]["invs"][relation]["model"] = all_relation_dict[relation]
            relationDict[methodString]["invs"][relation]["num"] += 1

    def incrementalAlg(self, allDtraceList, threshold=1, lowBar=3, max_methodCount=100):
        # allDtraceList = self.contract.extractDtrace(self.contract.var_dict_list)
        print("extract invs from benign, length of dtraceList", len(allDtraceList))

        methodAllCountDict = dict()
        relationDict = dict()

        for dtrace in allDtraceList:
            methodString = dtrace["methodString"]
            if dtrace["methodString"] not in methodAllCountDict:
                methodAllCountDict[methodString] = dict()
                methodAllCountDict[methodString]["num"] = 0
                methodAllCountDict[methodString]["traces"] = dict()
            methodAllCountDict[methodString]['num'] += 1
            for var_name in dtrace["traceDict"]:
                if var_name not in methodAllCountDict[methodString]["traces"]:
                    methodAllCountDict[methodString]["traces"][var_name] = 0
                methodAllCountDict[methodString]["traces"][var_name] += 1

            if methodString not in relationDict:
                relationDict[methodString] = dict()
                relationDict[methodString]["count"] = 0
                relationDict[methodString]["invs"] = dict()

        # removeTraces = dict()
        # for methodString in methodAllCountDict:
        #     removeTraces[methodString] = set()
        #     for trace in methodAllCountDict[methodString]["traces"]:
        #         if methodAllCountDict[methodString]["traces"][trace] < methodAllCountDict[methodString]["num"] * threshold:
        #             removeTraces[methodString].add(trace)

        intDict = dict()
        for dtrace in allDtraceList:
            methodString = dtrace["methodString"]
            traceDict = dtrace["traceDict"]
            points = dtrace["points"]
            # print(dtrace["block_tx_index"])
            # init each methodString

            # remove some traces
            # for trace in removeTraces[methodString]:
            #     if trace in traceDict:
            #         traceDict.pop(trace)

            # start: for collecting int variables
            if methodString not in intDict:
                intDict[methodString] = dict()
                intDict[methodString]["count"] = 0
                intDict[methodString]["vars"] = dict()
            
            # if relationDict[methodString]["count"] > max_methodCount:
            #     continue

            tmpIntDict = dict()
            for var_name in traceDict:
                if isinstance(traceDict[var_name], tuple):
                    var_value = traceDict[var_name][0]
                    if type(var_value) == int:
                        # collect int var
                        if var_name not in intDict[methodString]["vars"]:
                            intDict[methodString]["vars"][var_name] = ["nonsensical"] * intDict[methodString]["count"]
                        tmpIntDict[var_name] = var_value

            for var_name in intDict[methodString]["vars"]:
                if var_name in tmpIntDict:
                    intDict[methodString]["vars"][var_name].append(tmpIntDict[var_name])
                else:
                    intDict[methodString]["vars"][var_name].append("nonsensical")

            intDict[methodString]["count"] += 1
            # end: for collecting int variables

            # start: for mining invariants
            threshold_bar = methodAllCountDict[methodString]["num"] * (1-threshold)
            if relationDict[methodString]["count"] == 0:
                # for initilizing
                relationDict[methodString]["count"] += 1
                self.searchInvs(methodString, traceDict, relationDict)
            else:
                relationDict[methodString]["count"] += 1
                removeRelation = set()
                if relationDict[methodString]["count"] <= threshold_bar:
                    # perform searching
                    self.searchInvs(methodString, traceDict, relationDict)
                elif relationDict[methodString]["count"] > threshold_bar:
                    # perform incremental alg
                    for relation in relationDict[methodString]["invs"]:
                        res = self.checkInv(relation, relationDict[methodString]["invs"][relation], traceDict)
                        if res == "satisfy":
                            relationDict[methodString]["invs"][relation]["num"] += 1
                        # for increasing efficiency
                        if relationDict[methodString]["count"] - relationDict[methodString]["invs"][relation]["num"] > threshold_bar:
                            removeRelation.add(relation)

                # remove the relations that could not satisfy threshold
                for relation in removeRelation:
                    del relationDict[methodString]["invs"][relation]

        self.invDict = relationDict
        self.keyInvDict = self.selectKeyInvs(relationDict, intDict, lowBar=lowBar)

        for methodString in intDict:
            modelInvDict = self.mineMethodModel(intDict[methodString], methodAllCountDict[methodString]["num"] * threshold)
            for modelInv in modelInvDict:
                # print(modelInv)
                self.keyInvDict[methodString][modelInv] = dict()
                self.keyInvDict[methodString][modelInv]['type'] = "arithmetic"
                self.keyInvDict[methodString][modelInv]['model'] = modelInvDict[modelInv]

        self.reservedInvDict = self.removeRedundantInvs(self.keyInvDict)
        return allDtraceList, methodAllCountDict

    # def inferFurtherInvs(self, invDict, )
        

    def removeRedundantInvs(self, invDict):

        reservedInv = dict()
        for methodString, methodStringInvDict in invDict.items():
            reservedInv[methodString] = dict()
            redundantInvs = set()
            for inv1, invInfo1 in methodStringInvDict.items():
                model1 = invInfo1["model"]
                if type(model1) == EqualRelation and "tokenBalance" not in inv1:
                    inv1_x, inv1_y = model1.x_name, model1.y_name
                    for inv2 in methodStringInvDict:
                        if inv1 == inv2:
                            continue
                        if inv1_x in inv2:
                            new_temp_inv = inv2.replace(inv1_x, inv1_y)
                            if new_temp_inv in invDict[methodString]:
                                redundantInvs.add(new_temp_inv)

            for inv in methodStringInvDict:
                if inv not in redundantInvs:
                    reservedInv[methodString][inv] = methodStringInvDict[inv]

        return reservedInv


    def checkInv(self, inv, invInfo, traceDict):
        # assert keyInv in self.keyInvDict[methodString], f"{keyInv} not in self.keyInvDict"
        if invInfo["type"] == "normal":
            return self.checkNormalInv(inv, invInfo, traceDict=traceDict)
        elif invInfo["type"] == "arithmetic":
            return self.checkArithmeticInv(inv, invInfo, traceDict=traceDict)
        elif invInfo['type'] == "inference":
            return self.checkInferedInv(inv, invInfo, traceDict=traceDict)
        
    def getOrinialInv(self, relation, traceDict, variable_list = []):
        if relation.type == "normal":
            return relation, [self.getTraceDictVar(var, traceDict) for var in variable_list]
        else: 
            replacement = relation.replacement
            replacement_value = self.getTraceDictVar(replacement, traceDict)
            var_name_list = relation.getVars()
            if replacement_value != "nonsensical":
                new_variable_names = list()
                for var_name in var_name_list:
                    new_variable_names.append(var_name.replace(replacement, replacement_value))
                # var_name_A, var_name_B = relation.x_name, relation.y_name
                # var_name_A = var_name_A.replace(replacement, replacement_value)
                # var_name_B = var_name_B.replace(replacement, replacement_value)
                return self.getOrinialInv(relation.baseRelation, traceDict, new_variable_names)
            else:
                return None, ["nonsensical"] * len(var_name_list)

    def checkInferedInv(self, inv, invInfo, traceDict):
        relation = invInfo["model"]
        normalRelation, var_value_list = self.getOrinialInv(relation, traceDict, relation.getVars())
        # print(inv)
        # replacement = invInfo["model"].replacement
        # if replacement in traceDict:
        #     replacement_value = traceDict[replacement]
        #     var_name_A, var_name_B = invInfo["model"].getOriginalVarName(replacement_value[0])
        # print(var_name_A, var_name_B)
        # var_value_A = self.getTraceDictVar(var_name_A, traceDict, points)
        # var_value_B = self.getTraceDictVar(var_name_B, traceDict, points)
        if len(var_value_list) == 1:
            return self.checkSingleVarInv(normalRelation, var_value_list[0])
        elif len(var_value_list) == 2:
            return self.checkDoubleVarInv(normalRelation, *var_value_list)
        # if var_value_A != "nonsensical" and var_value_B != "nonsensical":
        #     if normalRelation.checkRelation(var_value_A, var_value_B):
        #         return "satisfy"
        #     else:
        #         return "violate"
        # else:
        #     return "exist_nonsensical"
        # else:
        #     return "exist_nonsensical"

    def checkSingleVarInv(self, relation, var_value):
        if var_value != "nonsensical":
            if relation.checkRelation(var_value):
                return "satisfy"
            else:
                return "violate"
        else:
            return "exist_nonsensical"
        
    def checkDoubleVarInv(self, relation, var_value_A, var_value_B):
        if var_value_A != "nonsensical" and var_value_B != "nonsensical":
            if relation.checkRelation(var_value_A, var_value_B,):
                return "satisfy"
            else:
                return "violate"
        else:
            return "exist_nonsensical"

    def checkNormalInv(self, inv, invInfo, traceDict):
        if type(invInfo['model']) in SingleInvList:
            var_name_A = invInfo['model'].x_name
            var_value_A = self.getTraceDictVar(var_name_A, traceDict)
            return self.checkSingleVarInv(invInfo['model'], var_value_A)

        elif type(invInfo['model']) in ComparisonRelationList:
            var_name_A, var_name_B = invInfo['model'].x_name, invInfo['model'].y_name
            var_value_A = self.getTraceDictVar(var_name_A, traceDict)
            var_value_B = self.getTraceDictVar(var_name_B, traceDict)
            return self.checkDoubleVarInv(invInfo['model'], var_value_A, var_value_B)

    def getTraceDictVar(self, var_name, traceDict):
        if var_name in traceDict:
            var_value = traceDict[var_name]
            if isinstance(var_value, tuple):
                return var_value[0]
            else:
                return var_value
        else:
            var_name, point = splitPointAndVariable(var_name)
            # if point not in points:
            #     return "nonsensical"
            if "change." in var_name:
                return 0
            else:
                return "nonsensical"
    
    def checkArithmeticInv(self, inv, invInfo, traceDict):
        modelRelation = invInfo["model"]
        if isinstance(modelRelation, LinearRelationWithThreeVar):
            # x_name, y_name, z_name = modelRelation.x_name, modelRelation.y_name, modelRelation.z_name
            x_value = self.getTraceDictVar(modelRelation.x_name, traceDict)
            y_value = self.getTraceDictVar(modelRelation.y_name, traceDict)
            z_value = self.getTraceDictVar(modelRelation.z_name, traceDict)
            if x_value != "nonsensical" and y_value != "nonsensical" and z_value != "nonsensical":
                flag = "violate"
                if modelRelation.checkRelation([x_value, y_value, z_value]):
                    flag = "satisfy"
                return flag
            else:
                return "exist_nonsensical"
        else:
            # x_name, y_name = modelRelation.x_name, modelRelation.y_name
            x_value = self.getTraceDictVar(modelRelation.x_name, traceDict)
            y_value = self.getTraceDictVar(modelRelation.y_name, traceDict)
            if x_value != "nonsensical" and y_value != "nonsensical":
                flag = "violate"
                if modelRelation.checkRelation([x_value, y_value]):
                    flag = "satisfy"
                return flag
            else:
                return "exist_nonsensical"

    def checkInvs(self, startBlock, endBlock, txPath):

        var_dict_list = self.contract.readVarDict(startBlock=startBlock, endBlock=endBlock, txNum=1000, mode="check", txPath=txPath, dumpBool=True, excludePartialErr=True)
        print("length of var_dict", len(var_dict_list))
        dtraceList = self.contract.extractDtrace(var_dict_list)
        print("CHECKING: length of dtraceList", len(dtraceList))
        violatedTxs = dict()
        tx_set = set()
        for var_dict in var_dict_list:
        # for dtrace in dtraceList:
            function = var_dict["name"]
            branch = var_dict["branch"]
            methodString = None
            level = None
            
            # is branch
            for level in ["branch", "function", "contract"]:
                # if function +":"+branch in self.keyInvDict:
                if level == "branch":
                    methodString = function +":"+branch
                    # level = "branch"
                # if function in self.keyInvDict:
                elif level == "function":
                    methodString = function
                    # level = "function"
                # if "contract" in self.keyInvDict:
                elif level == "contract":
                    methodString = "contract"
                    # level = "contract"

                # if methodString == None:
                #     continue
                if methodString not in self.keyInvDict:
                    continue

                traceDict = self.contract.extractFuncDtraceInfo(var_dict, level)
                tx_set.add(f"{var_dict['blockNumber']}_{var_dict['position']}")
                label = f"{var_dict['blockNumber']}_{var_dict['position']}_{var_dict['index']}:{level}"

                violation = list()

                # deal with invs
                for inv, invInfo in self.keyInvDict[methodString].items():
                    res = self.checkInv(inv, invInfo, traceDict)
                    if res == "violate":
                        violation.append(inv)
                
                if len(violation) > 0:
                    violatedTxs[label] = dict()
                    violatedTxs[label]["methodString"] = methodString
                    violatedTxs[label]["msg.sender"] = var_dict["from"]
                    violatedTxs[label]["tx.origin"] = var_dict["tx.origin"]
                    violatedTxs[label]["violations"] = list(violation)
                    violatedTxs[label]["level"] = level
                    print(label, methodString)
                    # for vio in violation:
                    #     print(vio)
                    # print(traceDict)
                    # with open(f"{block_tx}_trace_dict.json", "w") as f:
                    #     json.dump(traceDict, f)
                else:
                    # print(block_tx, methodString, "safe")
                    pass

        return dtraceList, len(tx_set), violatedTxs
    
    def loadMinedInvs(self, path):
        with open(f"{path}/key_inv_dict.json", "r") as f:
            j = json.load(f)
            for methodString in j:
                self.keyInvDict[methodString] = dict()
                for inv_type in j[methodString]:
                    if inv_type == "normal":
                        for inv in j[methodString][inv_type]:
                            self.keyInvDict[methodString][inv] = dict()
                            self.keyInvDict[methodString][inv]["type"] = inv_type
                    elif inv_type == "model":
                        for inv_item in j[methodString][inv_type]:
                            inv, modelDict = inv_item
                            self.keyInvDict[methodString][inv] = dict()
                            self.keyInvDict[methodString][inv]["type"] = inv_type
                            self.keyInvDict[methodString][inv]["model"] = loadModel(modelDict)
                    elif inv_type == "infered":
                        for inv_item in j[methodString][inv_type]:
                            inv, replacement = inv_item
                            self.keyInvDict[methodString][inv] = dict()
                            self.keyInvDict[methodString][inv]["type"] = inv_type
                            self.keyInvDict[methodString][inv]["replacement"] = replacement
                    
        with open(f"{path}/extractedDecl.json", "r") as f:
            self.contract.extractedDecl = json.load(f)