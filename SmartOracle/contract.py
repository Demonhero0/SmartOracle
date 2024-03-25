import os
import json
from extractTxs import *
from eth_abi import decode
import sys
from storageExtractor.storage import StorageExtractor
from storageExtractor.storageTest import StateVariableExtractor
from web3 import Web3
import math
sys.set_int_max_str_digits(0)

def slotAdd(slot:str, num:int) -> str:
    newSlot = hex(int(slot, 16) + num).replace("0x","")
    newSlot = "0x" + "0" * (64 - len(newSlot)) + newSlot
    return newSlot

def getDynamicSlotValue(slot:str, storageMap:dict, slotValue) -> str:
    # the case that len(string) <= 31 bytes
    
    length = int(slotValue[-2:], 16)
    if length <= 62:
        return slotValue[:length]
    else:
        length = length - 1 # len(string) + 1 = length
        targetSlot = Web3.keccak(int(slot, 16)).hex()
        if targetSlot in storageMap:
            stringValue = ""
            slotNum = math.ceil(length / 64)
            for index in range(slotNum):
                stringSlot = slotAdd(targetSlot, index)
                stringValue += storageMap[stringSlot].replace("0x","")
            var_value = stringValue[:length]
        else:
            var_value = None
    return var_value

def getVarDictBlockTx(e):
    return f'{e["blockNumber"]}_{e["position"]}_{e["index"]}'

def getTxKey(e):
    block, tx = e.split('_')
    return '0'*(8 - len(block)) + block + '_' + tx

def getBlock(block_tx):
    return int(block_tx.split('_')[0])

def getByteNum(var_type):
    if "int" in var_type:
        tmpNum = int(var_type.split("int")[1])
        return int(tmpNum / 8)
    elif "bytes" in var_type and len(var_type) > 5:
        tmpNum = int(var_type.split("bytes")[1])
        return tmpNum
    elif var_type == "address":
        return 20
    elif var_type == 'bool':
        return 1
    elif var_type == "string":
        return 32
    return 32


class Contract(object):

    def __init__(self, proxyAddr, contractConfig, sourcePath, outputPath):
        print(contractConfig)
        assert len(contractConfig) <= 1, "len(contractConfig) > 1"

        self.address = proxyAddr
        self.invInput = dict()
        self.var_dict_list = list()
        # self.extractedDecl = dict() # map[methodString] = [decls of the function methodString], record the decl of variable as string, such as tokenBalance.tokenAddress.userAddress
        # self.decl_dict = dict() # record the decl as dict, such as decl_dict[methodString]["token"] => the related token
        self.outputPath = outputPath
        self.storageLayoutDict = dict()
        self.stateVariableExtractor = dict()
        if not os.path.exists(outputPath):
            os.mkdir(outputPath)

        # if not os.path.exists(f"{self.path}/{self.dapp}/trashTxs"):
        #     os.mkdir(f"{self.path}/{self.dapp}/trashTxs")
        abiList = list()
        for abi in os.listdir(f"{sourcePath}/abi"):
            with open(f"{sourcePath}/abi/{abi}", "r") as f:
                abiList.append(json.load(f))
        for logicConfig in contractConfig["logic"]:
            if logicConfig["contractName"] != "":
                if not os.path.exists(f"{sourcePath}/contracts/{logicConfig['address']}/storageLayout.json"):
                    self.storageExtractorDict[proxyAddr] = StorageExtractor(proxyAddr=proxyAddr, logicConfig=logicConfig, source_path=f"{sourcePath}/contracts/{logicConfig['address']}")
                    storageLayoutDict = self.storageExtractorDict[self.address].storageLayout
                else:
                    with open(f"{sourcePath}/contracts/{logicConfig['address']}/storageLayout.json", "r") as f:
                        storageLayoutDict = json.load(f)
                self.stateVariableExtractor[proxyAddr] = StateVariableExtractor(storageLayoutDict)

        self.txExtractor = TxExtractor([self.address], abiList=abiList)

    def readTxToVarDict(self, txPath, excludePartialErr=False):
        var_dict_list = list()
        with open(txPath,'r') as f:
            tx = json.load(f)

        callList = self.txExtractor.extractExTx(tx, excludePartialErr)

        for index, call in enumerate(callList):
            var_dict = dict()
            var_dict["sig"] = call["sig"]
            var_dict["name"] = call["name"]
            var_dict["from"] = call["from"]
            var_dict["to"] = call["to"]
            var_dict["value"] = call["value"]
            var_dict["args"] = call["args"]

            var_dict["timestamp"] = call["timestamp"]
            var_dict["blockNumber"] = call["blockNumber"]
            var_dict["position"] = call["position"]
            var_dict["index"] = index
            var_dict["tx.origin"] = call["tx.origin"]
            var_dict["events"] = []
            # only deal with the event emited by self.address
            for event in call["logs"]:
                if event["address"] == self.address:
                    var_dict["events"].append(event)

            var_dict["points"] = dict()
            
            var_dict["points"]["pre"] = dict()
            var_dict["points"]["post"] = dict()
            var_dict["points"]["pre"]["tokenBalance"] = call["preTokenBalance"]
            var_dict["points"]["post"]["tokenBalance"] = call["postTokenBalance"]
            var_dict["points"]["pre"]["storage"] = call["preAlloc"][self.address]["storage"] if self.address in call["preAlloc"] and "storage" in call["preAlloc"][self.address] else {}
            var_dict["points"]["post"]["storage"] = call["postAlloc"][self.address]["storage"] if self.address in call["postAlloc"] and "storage" in call["postAlloc"][self.address] else {}
            var_dict["branch"] = call["branch"]


            # subCall
            for subCall in call["subCalls"]:
                prePoint = f"subCall_{subCall['callLocation']}_pre"
                var_dict["points"][prePoint] = dict()
                var_dict["points"][prePoint]["tokenBalance"] = subCall["preTokenBalance"]
                var_dict["points"][prePoint]["storage"] = subCall["preAlloc"][self.address]["storage"] if self.address in subCall["preAlloc"] and "storage" in subCall["preAlloc"][self.address] else {}

                postPoint = f"subCall_{subCall['callLocation']}_post"
                var_dict["points"][postPoint] = dict()
                var_dict["points"][postPoint]["tokenBalance"] = subCall["postTokenBalance"]
                var_dict["points"][postPoint]["storage"] = subCall["postAlloc"][self.address]["storage"] if self.address in subCall["postAlloc"] and "storage" in subCall["postAlloc"][self.address] else {}

            # remove the abandunt token and address
            tokenAddrDict = dict()
            tokenDict = dict()
            for point in var_dict["points"]:
                for token in var_dict["points"][point]["tokenBalance"]:
                    if token not in tokenAddrDict:
                        tokenAddrDict[token] = dict()
                    if token not in tokenDict:
                        tokenDict[token] = dict()
                    for addr in var_dict["points"][point]["tokenBalance"][token]:
                        if addr not in tokenAddrDict[token]:
                            tokenAddrDict[token][addr] = False
                        if var_dict["points"][point]["tokenBalance"][token][addr] and var_dict["points"][point]["tokenBalance"][token][addr] > 0:
                            tokenAddrDict[token][addr] = True
                            tokenDict[token] = True

            for point in var_dict["points"]:
                newTokenBalance = dict()
                for token in var_dict["points"][point]["tokenBalance"]:
                    # check if abandunt token
                    if tokenDict[token]:
                        newTokenBalance[token] = dict()
                        for addr in var_dict["points"][point]["tokenBalance"][token]:
                            # check if abandunt address
                            if tokenAddrDict[token][addr]:
                                newTokenBalance[token][addr] = var_dict["points"][point]["tokenBalance"][token][addr]
                var_dict["points"][point]["tokenBalance"] = newTokenBalance

            var_dict_list.append(var_dict)
        
        return var_dict_list
    
    """
    read var_dict
    """
    def readVarDict(self, startBlock, endBlock, txNum, mode, txPath, dumpBool = True, excludePartialErr=False, givenTxList=[]):

        exist_var_dict_list = list()
        var_dict_path = f"{mode}_var_dict.json"
        if os.path.exists(f"{self.outputPath}/{var_dict_path}"):
            print(f"loading {var_dict_path}")
            with open(f"{self.outputPath}/{var_dict_path}", "r") as f:
                exist_var_dict_list = json.load(f)
        
        if len(givenTxList) > 0:
            tx_name_list = givenTxList
        else:
            tx_name_list = ["_".join(x.replace(".json","").split('_')[:2]) for x in os.listdir(txPath)]
        tx_name_list = [x for x in tx_name_list if getBlock(x) >= startBlock and getBlock(x) <= endBlock]

        tx_name_set = set(tx_name_list)
        toRoadTxs = set(tx_name_list)

        return_var_dict_list = list()
        for exist_tx in exist_var_dict_list:
            block_tx = f'{exist_tx["blockNumber"]}_{exist_tx["position"]}'
            if block_tx in tx_name_set:
                return_var_dict_list.append(exist_tx)
                if block_tx in toRoadTxs:
                    toRoadTxs.remove(block_tx)
        
        toRoadTxs = list(toRoadTxs)
        if mode == "mine":
            toRoadTxs.sort(key=getTxKey, reverse=True)
        elif mode == "check":
            toRoadTxs.sort(key=getTxKey)
        if len(toRoadTxs) > 0:
            txCount = len(return_var_dict_list)
            new_var_dict_list = list()
            for tx_name in toRoadTxs:
                var_dict_list = self.readTxToVarDict(f"{txPath}/{tx_name}.json", excludePartialErr=excludePartialErr)
                new_var_dict_list.extend(var_dict_list)
                txCount += int(len(new_var_dict_list) > 0)
                if txCount >= txNum:
                    break
            print(f"Load Txs: {len(new_var_dict_list)}")

            return_var_dict_list.extend(new_var_dict_list)
            if dumpBool and len(new_var_dict_list) > 0:
                print(f"saving {var_dict_path}, add {len(new_var_dict_list)} Txs")
                with open(f"{self.outputPath}/{var_dict_path}", "w") as f:
                    json.dump(return_var_dict_list, f)

        return_var_dict_list.sort(key=getVarDictBlockTx)

        return return_var_dict_list

    def findKeyRole(self, method):
        keyRole = ["tx.origin", "msg.sender", "callee"]
        for arg in method["args"]:
            if arg["type"] == "address":
                keyRole.append(f"method.{arg['name']}")
        for _, event in method["events"].items():
            for arg in event["args"]:
                if arg["type"] == "address":
                    keyRole.append(f"event.{event['name']}.{arg['name']}")
        return keyRole
    
    def getMethodArgDtrace(self, var_type, var_info, var_content):
    
        if var_type == "tuple":
            structDict = dict()
            for component_name, component in var_info["components"].items():
                structDict[component_name] = self.getMethodArgDtrace(component['type'], component, var_content[component_name])
                # newDtrace.update(self.getMethodArgDtrace(f"{var_name}.{component_name}", component['type'], component, var_content[component_name]))
            return (structDict, "struct")
        elif "[]" in var_type or ("[" in var_type and "]" in var_type):
            baseType = var_type.split("[")[0]
            tmpList = list()
            for item in var_content:
                itemDtrace = self.getMethodArgDtrace(baseType, var_info, item)
                tmpList.append(itemDtrace)
                # if baseType == "tuple":
                #     tmpDtrace = dict()
                #     for key, value in itemDtrace.items():
                #         key = key.replace(f"{var_name}[..].","")
                #         tmpDtrace[key] = value
                #     newDtrace[f"{var_name}[..]"].append(tmpDtrace)
                #     tmpList.append(tmpDtrace)
                # else:
                #     newDtrace[f"{var_name}[..]"].append(itemDtrace[f"{var_name}[..]"])
            # newDtrace[f"{var_name}[..]"] = var_content
            # newDtrace[f"{var_name}"] = (tmpList, "array")
            return (tmpList, "array")
        elif isNormalType(var_type):
            # add dtrace
            if var_type == "address":
                var_content = var_content.lower()
            if var_type == "bytes":
                var_content = var_content.replace("0x","")
                # if len(var_content) % 64 == 0:
                    # new_var_content = []
                    # for index in range(0, len(var_content), 64):
                        # tmp_content = var_content[index:index+64]
                        # if tmp_content.startswith("000000000000000000000000"):
                        #     new_var_content.append("0x"+tmp_content[24:])
                        # else:
                        # int_content = int(tmp_content,16)
                        # if int_content > 2**128:
                            # new_var_content.append((tmp_content[24:], "address"))
                        # elif int_content > 1024:
                            # new_var_content.append((int_content, "int"))
                    # newDtrace[f"{var_name}[..]"] = new_var_content
                    # print(var_content, new_var_content)
            # newDtrace[var_name] = (var_content, var_type)
            return (var_content, var_type)
        else:
            assert False, f"unkonwn method type {var_type}"
    
    def getStateVariableType(self, state_variable_type):
        typeDict = self.storageLayoutDict[self.address]["types"]
        if isNormalType(state_variable_type):
            return state_variable_type
        
        elif "mapping" in state_variable_type:
            # return typeDict[state_variable_type]["value"]
            return self.getStateVariableType(typeDict[state_variable_type]["value"])
        elif "[]" in state_variable_type or ("[" in state_variable_type and "]" in state_variable_type):
            # return typeDict[state_variable_type]['base']
            return self.getStateVariableType(typeDict[state_variable_type]['base'])
        elif state_variable_type in typeDict:
            if "members" in typeDict[state_variable_type]:
                tupleDict = dict()
                for memberInfo in typeDict[state_variable_type]["members"]:
                    tupleDict[memberInfo['label']] = self.getStateVariableType(memberInfo["type"])
                return tupleDict
            else:
                return self.getStateVariableType(typeDict[state_variable_type]["label"])
        else:
            # print(f"unknow {state_variable_type}")
            return "bytes32"
        
    def getSlotValue(self, slot, offset, numOfBytes, var_type, storageMap):
        # print(slot, offset, numOfBytes, var_type)
        if slot not in storageMap:
            return None
        slot_value = storageMap[slot]
        value = slot_value[66-2*(offset+numOfBytes):66-2*offset].replace("0x","")
        value = "0" * (64 - len(value)) + value
        # deal with dynamic type
        if var_type == "string":
            var_value = getDynamicSlotValue(slot, storageMap, value)
            if var_value != None:
                var_value = Web3.toText(var_value)
        elif var_type == "bytes":
            var_value = getDynamicSlotValue(slot, storageMap, value)
            if var_value != None:
                var_value = "0x" + var_value
        # deal with normal type
        elif var_type[:3] == "int":
            var_type = var_type[:3] + "256" 
            var_value = decode([var_type], bytes.fromhex(value))[0]
            var_value = normalizeArg(var_value)
        else:
            # print(slot_value, value, offset, numOfBytes, var_type)
            var_value = decode([var_type], bytes.fromhex(value))[0]
            var_value = normalizeArg(var_value)
            # except:
                # print(slot_value, value, offset, numOfBytes, var_type)
                # var_value = None
        return var_value
    
    def getStateVariableDtrace(self, storageMap, var_dict):
        if self.address in self.stateVariableExtractor:
            mappingKeys = self.stateVariableExtractor[self.address].searchKeys(var_dict)
            return self.stateVariableExtractor[self.address].loadStateVariable(storageMap, mappingKeys)
        else:
            return dict()

    def getTokenBalanceDtrace(self, tokenBalanceMap, keyAddrMap, dtraceDict):
        for tokenAddress in tokenBalanceMap:
            if len(tokenBalanceMap[tokenAddress]) == 0:
                continue
            # print(tokenBalanceMap[tokenAddress].values())
            totalBalance = sum(tokenBalanceMap[tokenAddress].values())
            
            for role,addr in keyAddrMap.items():
                if addr in tokenBalanceMap[tokenAddress]:
                    dtraceDict[f"tokenBalance.[{tokenAddress}][{role}]"] = (tokenBalanceMap[tokenAddress][addr], 'uint')
                else:
                    dtraceDict[f"tokenBalance.[{tokenAddress}][{role}]"] = (0, 'uint')

            # for user in tokenBalanceMap[tokenAddress]:
            #     if user in keyAddrMap:
            #         totalBalance += tokenBalanceMap[tokenAddress][user]
            #         for role in keyAddrMap[user]:
            #             # add dtrace
            #             dtraceDict[f"tokenBalance.[{tokenAddress}][{role}]"] = (tokenBalanceMap[tokenAddress][user], 'uint')
            dtraceDict[f"tokenBalance.[{tokenAddress}][all]"] = (totalBalance, 'uint')
            # other_addrs = set(list(tokenBalanceMap[tokenAddress])) - set(list(keyAddrMap.values())) 
            # other_totalBalance = sum([tokenBalanceMap[tokenAddress][addr] for addr in other_addrs])
            # dtraceDict[f"tokenBalance.[{tokenAddress}][others]"] = (other_totalBalance, 'uint')

    
    def flatDtraceUtil(self, var_name, dtrace):
        newDtrace = dict()
        content, t = dtrace
        if isNormalType(t):
            newDtrace[var_name] = (content, t)
        elif t == "mapping":
            for key in content:
                newDtrace.update(self.flatDtraceUtil(f"{var_name}[{key}]", content[key]))
            # check int
            value_list = [x[0] for x in content.values() if "int" in x[1]]
            if len(value_list) > 0:
                newDtrace[f"{var_name}.SUM"] = (sum(value_list), "int")
        elif t == "struct":
            for key in content:
                newDtrace.update(self.flatDtraceUtil(f"{var_name}.{key}", content[key]))
        elif t == "array":
            newDtrace[var_name] = (content, t)
        else:
            print("error in flatDtraceUtil:", t)
        return newDtrace
    
    def flatDtrace(self, traceDict):
        flatedTraceDict = dict()
        for var_name, trace in traceDict.items():
            flatedTraceDict.update(self.flatDtraceUtil(var_name, trace))
        return flatedTraceDict
    
    def addKeyAddrMap(self, keyAddrMap, var_name, var_value):
        if var_value not in keyAddrMap:
            keyAddrMap[var_value] = set()
        keyAddrMap[var_value].add(var_name)

    def getChangeVarDtrace(self, point, postDtraceDict, preDtraceDict):
        newDtraceDict = dict()
        for var_name in postDtraceDict:
            if isinstance(postDtraceDict[var_name], tuple) and type(postDtraceDict[var_name][0]) == int:
                if var_name in preDtraceDict:
                    # add dtrace
                    # dtrace_name = f"{point}({var_name})-pre({var_name})"
                    dtrace_name = f"change.{point}({var_name})"
                    newDtraceDict[dtrace_name] = (postDtraceDict[var_name][0] - preDtraceDict[var_name][0], "int")
                    # newDtraceDict[f'change.{var_name}'] = (postDtraceDict[var_name][0] - preDtraceDict[var_name][0], "int")
        return newDtraceDict

    def extractFuncDtraceInfo(self, var_dict, level):
        sig = var_dict['sig']
        points = list(var_dict["points"]) if level == "branch" else ["pre","post"]
        # print(var_dict["blockNumber"], var_dict["position"])
        pointDtraceDict = dict()
        allTraceDict = dict()
        # allTraceDict["tx.origin"] = (var_dict["tx.origin"], "address")
        allTraceDict["callee"] = (var_dict["to"], "address")
        allTraceDict["msg.sender"] = (var_dict["from"], "address")
        allTraceDict["msg.value"] = (var_dict["value"], "uint")
        allTraceDict["block.timestamp"] = (var_dict["timestamp"],"uint")
        allTraceDict["block.number"] = (var_dict["blockNumber"],"uint")

        # deal with method args
        if level in ["function", "branch"]:
            methodTraceDict = dict()
            for argName, argContent in var_dict["args"].items():
                if argName == "rawbytes":
                    methodTraceDict['method.rawbytes'] = (argContent, "bytes")
                else:
                    var_info = self.txExtractor.functionAbi[sig]["argFormatDict"][argName]
                    methodTraceDict[f"method.{argName}"] = self.getMethodArgDtrace(var_info['type'], var_info, argContent)
                    # methodTraceDict.update(self.getMethodArgDtrace(f'method.{argName}', var_info['type'], var_info, argContent))
            allTraceDict.update(self.flatDtrace(methodTraceDict))

        # deal wit event
        # when exsiting more than one event with the same name, only record the first event
        if level in ["function", "branch"]:
            eventTraceDict = dict()
            for event in var_dict["events"]:
                sig = event['sig']
                for argName, argContent in event["args"].items():
                    var_info = self.txExtractor.eventAbi[sig]["argFormatDict"][argName]
                    eventTraceDict[f'event.{event["name"]}.{argName}'] = self.getMethodArgDtrace(var_info['type'], var_info, argContent)
                    # eventTraceDict.update(self.getMethodArgDtrace(f'event.{event["name"]}.{argName}', var_info['type'], var_info, argContent))
            allTraceDict.update(self.flatDtrace(eventTraceDict))


        # deal with variables
        for point in points:
            stateVariableDtraceDict = self.getStateVariableDtrace(var_dict["points"][point]["storage"], var_dict)
        
            pointDtraceDict[point] = dict()
            varTraceDict = dict()
            # extract traceDict from dtrace
            if stateVariableDtraceDict != None:
                for var_name in stateVariableDtraceDict:
                    varTraceDict.update(self.flatDtraceUtil(f"variable.{var_name}", stateVariableDtraceDict[var_name]))
                for var_name, var_value in varTraceDict.items():
                    pointDtraceDict[point][var_name] = var_value
                    allTraceDict[f"{point}({var_name})"] = var_value
        
        flatedTraceDict = allTraceDict
        # flatedTraceDict = self.recoverAndFlatTraceDict(allTraceDict)
        # deal with token
        keyAddrMap = dict()
        for var_name in flatedTraceDict:
            if isinstance(flatedTraceDict[var_name], tuple) and isinstance(flatedTraceDict[var_name][0],str) and flatedTraceDict[var_name][1] == "address":
                # self.addKeyAddrMap(keyAddrMap, var_name, flatedTraceDict[var_name][0])
                # only selecting these addresses
                if var_name.startswith("event.") or var_name.startswith("method.") or var_name.startswith("pre(variable.") or var_name in ["msg.sender", "callee", "tx.origin"]:
                    keyAddrMap[var_name] = flatedTraceDict[var_name][0]
        
        for point in points:
            tokenDtraceDict = dict()
            self.getTokenBalanceDtrace(var_dict['points'][point]['tokenBalance'], keyAddrMap, tokenDtraceDict)
            pointDtraceDict[point].update(tokenDtraceDict)

            for var_name in tokenDtraceDict:
                flatedTraceDict[f"{point}({var_name})"] = tokenDtraceDict[var_name]

        # deal with change
        for point in pointDtraceDict:
            if point != "pre":
                changeDtraceDict = self.getChangeVarDtrace(point, pointDtraceDict[point], pointDtraceDict['pre'])
                flatedTraceDict.update(changeDtraceDict)
                # for var_name in changeDtraceDict:
                #     flatedTraceDict[f"{point}({var_name})"] = changeDtraceDict[var_name]
    
        return flatedTraceDict
    
    def fillCachedStorage(self, cachedStorage, var_dict):
        for point in var_dict["points"]:
            for slot in cachedStorage:
                if slot not in var_dict["points"][point]["storage"]:
                    var_dict["points"][point]["storage"][slot] = cachedStorage[slot]

            if point == "post":
                for slot in var_dict["points"][point]["storage"]:
                    cachedStorage[slot] = var_dict["points"][point]["storage"][slot]
    
    def extractDtrace(self, var_dict_list, useCachedStorage=False):
        dtraceList = list()
        cachedStorage = dict()
        for var_dict in var_dict_list:
            if useCachedStorage:
                self.fillCachedStorage(cachedStorage, var_dict)
            for level in ["contract","function","branch"]:
                traceDict = self.extractFuncDtraceInfo(var_dict, level)
                if level == "contract":
                    methodString = "contract"
                elif level == "function":
                    methodString = var_dict["name"]
                elif level == "branch":
                    methodString = var_dict["name"] +":"+var_dict["branch"]
                dtraceList.append(
                    {
                        "block_tx_index" : f"{var_dict['blockNumber']}_{var_dict['position']}_{var_dict['index']}",
                        "tx.origin": var_dict['tx.origin'],
                        "msg.sender": var_dict['from'],
                        "methodString": methodString,
                        "level":level,
                        "points": list(var_dict["points"]) if level == "branch" else ["pre","post"],
                        "traceDict": traceDict,
                    }
                )
        return dtraceList
    
# not used ------------------------- !!!
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

    # def readDeclDict(self, var_dict_list):
    #     # caller, callee, the addresses in args, the addresses in event
    #     decl_dict = dict()
    #     for var_dict in var_dict_list:
    #         methodString = f'{var_dict["name"]}({",".join([x["type"] for x in var_dict["args"]])})'
    #         if methodString not in decl_dict:
    #             # print("init ", methodString)
    #             # add args
    #             decl_dict[methodString] = dict()

    #             decl_dict[methodString]["args"] = var_dict["args"]
    #             decl_dict[methodString]["events"] = dict()
    #             decl_dict[methodString]["points"] = dict()
    #             decl_dict[methodString]["count"] = 0
    #         # count time
    #         decl_dict[methodString]["count"] += 1

    #         # deal with events
    #         for event in var_dict["events"]:
    #             # only deal with the event emitted by self.address
    #             if event["address"] == self.address:
    #                 event_key = event["name"]
    #                 if event_key not in decl_dict[methodString]["events"]:
    #                     decl_dict[methodString]["events"][event_key] = dict()
    #                     decl_dict[methodString]["events"][event_key]["name"] = event["name"]
    #                     decl_dict[methodString]["events"][event_key]["address"] = event["address"]
    #                     decl_dict[methodString]["events"][event_key]["args"] = event["args"]
            
    #         for point in var_dict["points"]:
    #             if point not in decl_dict[methodString]["points"]:
    #                 decl_dict[methodString]["points"][point] = dict()
    #                 decl_dict[methodString]["points"][point]["tokenBalance"] = dict()
    #                 decl_dict[methodString]["points"][point]["storage"] = dict()
    #             for slot in var_dict["points"][point]["storage"]:
    #                 if slot not in decl_dict[methodString]["points"][point]:
    #                     decl_dict[methodString]["points"][point]["storage"][slot] = 0
    #             for token in var_dict["points"][point]["tokenBalance"]:
    #                 if token not in decl_dict[methodString]["points"][point]["tokenBalance"]:
    #                     decl_dict[methodString]["points"][point]["tokenBalance"][token] = dict()

    #     return decl_dict
    
    # def getStateVariableDecl(self, var_name, var_type):
    #     typeDict = dict()
    #     if self.address in self.storageExtractorDict:
    #         typeDict = self.storageExtractorDict[self.address].storageLayout["types"]

    #     newDecls = dict()
    #     if "mapping" in var_type:
    #         newDecls.update(self.getStateVariableDecl(var_name + "[...]", typeDict[var_type]["value"]))
    #     elif "[]" in var_type or ("[" in var_type and "]" in var_type):
    #         newDecls.update(self.getStateVariableDecl(var_name + "[..]", typeDict[var_type]["base"]))
    #     elif isNormalType(var_type=var_type):
    #         newDecls[var_name] = var_type
    #     else:
    #         # deal with tuple variable
    #         assert var_type in typeDict, f"unknown state variable type {var_type}"
    #         if "members" in typeDict[var_type]:
    #             newDecls[var_name] = dict()
    #             for memberInfo in typeDict[var_type]["members"]:
    #                 tmpDecls = self.getStateVariableDecl(memberInfo['label'], memberInfo["type"])
    #                 for tmpDecl in tmpDecls:
    #                     newDecls[var_name][tmpDecl] = tmpDecls[tmpDecl]
    #     return newDecls
    
    # def getMethodArgDecl(self, var_name, var_info):
    #     newDecls = dict()
    #     var_type = var_info["type"]
    #     if var_type == "tuple":
    #         newDecls[var_name] = dict()
    #         for component in var_info["components"]:
    #             tmpDecls = self.getMethodArgDecl(component['name'], component)
    #             for tmpDecl in tmpDecls:
    #                 newDecls[var_name][tmpDecl] = tmpDecls[tmpDecl]
    #     elif "[]" in var_type or ("[" in var_type and "]" in var_type):
    #         baseType = var_type.split("[")[0]
    #         newDecls.update(self.getMethodArgDecl(f"{var_name}[..]", baseType))
    #     elif isNormalType(var_type):
    #         newDecls[var_name] = var_type
    #     else:
    #         assert False, f"unkonwn method type {var_type}"
    #     return newDecls

    # def extractDeclAndVarDict(self, var_dict_list, jsonPath):
    #     self.var_dict_list = var_dict_list
    #     decl_dict = self.readDeclDict(self.var_dict_list)

    #     self.slot_var_dict, self.var_slot_dict = self.extractVarInStorage(self.var_dict_list, jsonPath)

    #     extracted_decl = dict()
    #     for methodString, method in decl_dict.items():
    #         extracted_decl[methodString] = dict()
    #         # self.decl_dict[methodString] = dict()
    #         # self.decl_dict[methodString]["storage"] = set(list(method["points"]["pre"]["storage"]))

    #         allDecl = dict()
    #         # add

    #         # deal with args in method
    #         addrSet = set()
    #         for arg in method["args"]:
    #             newDecls = self.getMethodArgDecl(f"method.{arg['name']}", arg, addrSet)
    #             allDecl.update(newDecls)

    #         # deal with variables
    #         # self.extractStateVariableDecl(allDecl)
    #         for var_name, item in self.var_slot_dict.items():
    #             newDecls = self.getStateVariableDecl(f"variable.{var_name}", item['type'], addrSet)
    #             allDecl.update(newDecls)

    #         # deal with msg.sender, msg.value, block.timestamp, block.number
    #         for decl, decl_type in initDecl:
    #             allDecl[decl] = decl_type

    #         # find key roles in method, deal with token balance
    #         keyRole = self.findKeyRole(method)
    #         for point in method["points"]:
    #             for token in method["points"][point]["tokenBalance"]:
    #                 for role in keyRole:
    #                     allDecl[f'tokenBalance.{token}.{role}'] = "uint"
    #                     allDecl[f'tokenChange.{token}.{role}'] = "int"

    #         # deal with events, in exit
    #         for eventName, event in method["events"].items():
    #             for arg in event["args"]:
    #                 allDecl[f'event.{eventName}.{arg["name"]}'] = arg["type"]

    #         extracted_decl[methodString] = dict()
    #         extracted_decl[methodString]["decls"] = allDecl
    #         extracted_decl[methodString]["points"] = list(method["points"])

    #     self.extractedDecl = extracted_decl

    #     with open(f"{self.outputPath}/extractedDecl.json", "w") as f:
    #         json.dump(self.extractedDecl, f)

    # def getVariableChangeDtrace(self, methodString, preDtrace, postDtrace):
    #     for key in self.extractedDecl[methodString]["decls"]:
    #         if "variableChange." in key:
    #             var_key = key.replace("variableChange.", "variable.")
    #             if var_key in preDtrace and preDtrace[var_key] != "nonsensical" and var_key in postDtrace and postDtrace[var_key] != "nonsensical":
    #                 postDtrace[key] = postDtrace[var_key] - preDtrace[var_key]
    #             else:
    #                 postDtrace[key] = "nonsensical"
    #             preDtrace[key] = "nonsensical"

    # def getTokenChangeDtrace(self, preTokenBalanceMap, postTokenBalanceMap, preDtrace, postDtrace, keyAddrMap, methodString):
    #     for key in self.extractedDecl[methodString]["decls"]:
    #         if "tokenChange" in key:
    #             token = key.split('.')[1] # get the token address
    #             preDtrace[f"tokenChange.{token}.others"] = "nonsensical"
    #             postDtrace[f"tokenChange.{token}.others"] = 0
    #             for addr, role in keyAddrMap.items():
    #                 postDtrace[f"tokenChange.{token}.{role}"] = 0
    #             if token in preTokenBalanceMap:
    #                 for addr in preTokenBalanceMap[token]:
    #                     preTokenBalance = preTokenBalanceMap[token][addr]
    #                     postTokenBalance = postTokenBalanceMap[token][addr]
    #                     if preTokenBalance != None and postTokenBalance != None:
    #                         changeValue = postTokenBalance - preTokenBalance
    #                         if addr in keyAddrMap:
    #                             preDtrace[f"tokenChange.{token}.{keyAddrMap[addr]}"] = "nonsensical"
    #                             # remove the cases that zero to zero
    #                             if preTokenBalance == 0 and changeValue == 0:
    #                                 preDtrace[f"tokenBalance.{token}.{keyAddrMap[addr]}"] = "nonsensical"
    #                                 postDtrace[f"tokenBalance.{token}.{keyAddrMap[addr]}"] = "nonsensical"
    #                                 postDtrace[f"tokenChange.{token}.{keyAddrMap[addr]}"] = "nonsensical"
    #                             else:
    #                                 postDtrace[f"tokenChange.{token}.{keyAddrMap[addr]}"] = changeValue
    #                         else:
    #                             postDtrace[f"tokenChange.{token}.others"] += changeValue

    # def extractVarInStoragePerTx(self, var_dict):

    #     slot_var_dict = self.slot_var_dict
    #     lackSlot = set(list(var_dict["points"]["pre"]["storage"])) - set(list(self.slot_var_dict))
    #     if len(lackSlot) > 0:
    #         # print(var_dict["blockNumber"], var_dict["position"], "need mining slot_var_dict")
    #         if self.address in self.storageExtractorDict:
    #             slot_var_dict.update(self.storageExtractorDict[self.address].readTxStorage(var_dict))

    #     return slot_var_dict

    # def extractVarInStorage(self, var_dict_list, jsonPath):
    #     slot_dict_path = f"{jsonPath}_slot_var_dict.json"
    #     slot_dict = dict()
    #     if os.path.exists(f"{self.outputPath}/{slot_dict_path}"):
    #         with open(f"{self.outputPath}/{slot_dict_path}", "r") as f:
    #             slot_dict = json.load(f)
    #     else:
    #         print("generating slot_dict")
    #         for var_dict in var_dict_list:
    #             if self.address in self.storageExtractorDict:
    #                 slot_dict.update(self.storageExtractorDict[self.address].readTxStorage(var_dict))
    #         with open(f"{self.outputPath}/{slot_dict_path}", "w") as f:
    #             json.dump(slot_dict, f)

    #     var_slot_dict = dict()
    #     for slot, item in slot_dict.items():
    #         if item["name"] not in var_slot_dict:
    #             var_slot_dict[item["name"]] = dict()
    #             var_slot_dict[item["name"]]["type"] = item["type"]
    #             var_slot_dict[item["name"]]["slots"] = dict()
    #         var_slot_dict[item["name"]]["slots"][slot] = dict(offset=item["offset"],numOfBytes=item["numOfBytes"])

    #     with open(f"{self.outputPath}/{jsonPath}_var_slot_dict.json", "w") as f:
    #         json.dump(var_slot_dict, f)
    #     return slot_dict, var_slot_dict

    # def getStateVariableDtrace(self, storageMap, dtrace, slot_var_dict):
        
    #     usedSlot = set()
    #     for slot in storageMap:
    #         if slot in slot_var_dict and slot not in usedSlot:
    #             slotInfo = slot_var_dict[slot]
    #             var_key = "variable." + slotInfo["name"]
    #             # newDtrace = self.getStateVariableFromSlot(storageMap, slot, slotInfo, usedSlot)
    #             # if isinstance(newDtrace, list):
    #             #     var_key = var_key + "[..]"
    #             #     if var_key not in dtrace:
    #             #         dtrace[var_key] = list()
    #             #     dtrace[var_key].extend(newDtrace)
    #             # elif isinstance(newDtrace, dict):
    #             #     if "mapping" in slotInfo["type"]:
    #             #         var_key = var_key + "[...]"
    #             #         if var_key not in dtrace:
    #             #             dtrace[var_key] = dict()
    #             #         dtrace[var_key].update(newDtrace)
    #             # elif isinstance(newDtrace, tuple):
    #             #     dtrace[var_key] = newDtrace
                

    #             if "mapping" in slotInfo["type"]:
    #                 var_key = var_key + "[...]"
    #                 if var_key not in dtrace:
    #                     dtrace[var_key] = dict() 
    #                 dtrace[var_key][slotInfo["key"]] = self.getStateVariableFromSlot(storageMap, slot, slotInfo, self.getStateVariableType(slotInfo['type']), usedSlot)
    #             elif "[]" in slotInfo["type"] or ('[' in slotInfo["type"] and ']' in slotInfo["type"]):
    #                 var_key = var_key + "[..]"
    #                 if var_key not in dtrace:
    #                     dtrace[var_key] = list()
    #                 dtrace[var_key].append(self.getStateVariableFromSlot(storageMap, slot, slotInfo, self.getStateVariableType(slotInfo['type']), usedSlot))
    #             else:
    #                 dtrace[var_key] = self.getStateVariableFromSlot(storageMap, slot, slotInfo, self.getStateVariableType(slotInfo['type']), usedSlot)

    # def getStateVariableFromSlot(self, storageMap, slot, slotInfo, declType, usedSlot):
    #     newDtrace = dict()

    #     # mapping, return {"key": value}
    #     # struct, return  {"component_name": component_value}
    #     if type(declType) == dict:
    #         state_variable_name = slotInfo["name"]
    #         state_variable_info = self.storageLayoutDict[self.address]["storage"][state_variable_name]
    #         startSlot = Web3.soliditySha3(["uint256", "uint256"], [slotInfo["key"], state_variable_info['slot']]).hex()

    #         # load tupe
    #         loadedByteInSlot = 0
    #         # just for convience
    #         thisSlot = hex(int(startSlot, 16) - 1).replace("0x","")
    #         componentDict = dict() #
    #         for index, component_name in enumerate(declType):
    #             # check if all slots in storageMap
    #             if not isinstance(declType[component_name],dict):
    #                 targetType = self.getStateVariableType(declType[component_name])
    #                 byteNum = getByteNum(targetType)

    #                 if loadedByteInSlot + byteNum >= 32:
    #                     loadedByteInSlot = 0
    #                     thisSlot = slotAdd(thisSlot, 1)

    #                 componentDict[component_name] = [thisSlot, loadedByteInSlot, byteNum, targetType]

    #                 loadedByteInSlot += byteNum
    #             else:
    #                 loadedByteInSlot = 0
    #                 thisSlot = slotAdd(thisSlot, 1)
    #                 componentDict[component_name] = [thisSlot, loadedByteInSlot, 32, declType[component_name]]

    #         for component_name, component in componentDict.items():
    #             print(component_name, component)
    #             targetSlot, offset, numberOfBytes, targetType = component
    #             var_value = self.getSlotValue(targetSlot, offset, numberOfBytes, targetType, storageMap)
    #             if var_value != None:
    #                 newDtrace[component_name] = (var_value, targetType)
    #             usedSlot.add(targetSlot)

    #     elif isNormalType(declType):
    #         # load normal type
    #             var_value = self.getSlotValue(slot, storageMap, slotInfo["offset"], slotInfo["numOfBytes"], declType)
    #             if var_value != None:
    #                 newDtrace = (var_value, declType)

    #     else:
    #         print(f"unkonwn declType {declType}")
    #     return newDtrace

dapp_dict = {
    "qubit": [13806875, 13806876, 14090170], # TP
    "bzx_usdc": [10847340, 10847341, 10849165], # TP
    # "visor": [15000000, 0, 15000000],
    "visor": [13849006, 13849007, 15000000], # TP
    "meter_io": [15000000, 0, 15000000],
    "umbrella": [15000000, 0, 15000000],
    # "umbrella": [14421983, 14421984, 15000000],
    "formation_v2": [15000000, 0, 15000000],
    "cover" : [15000000, 0, 15000000]
}

if __name__ == "__main__":
    dapp = "formation_v2"
    path = "/home/pc/disk1/sujzh3/invFuzz/invFuzz/hunter"
    outputPath = f"invs/{dapp}"
    contract = Contract(dapp, path, outputPath)
    # contract.setDealingMethod(["transfer(address,uint256)"])
    contract.extractDeclAndVarDict(0, dapp_dict[dapp], "benign")
    # print(list(contract.extractedDecl))
    contract.writeDaikonDeclAndDtrace(outputPath)
    # contract.writeDaikonDtracePerTx(f"{outputPath}/perTxs")
    