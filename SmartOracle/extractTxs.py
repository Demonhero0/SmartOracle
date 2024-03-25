import base64
import sha3
from eth_abi import decode # eth-abi                  3.0.1
import re
import json
from web3 import Web3

def isNormalType(var_type):
    if "[]" in var_type or "mapping" in var_type or ("[" in var_type and "]" in var_type):
        return False
    elif var_type in ["address", "bool", "string"]:
        return True
    elif var_type[:3] == 'int':
        # int
        return True
    elif var_type[:4] == "uint":
        return True
    elif var_type[:5] == "bytes":
        return True
    return False

def normalizeArg(data):
    if type(data) == bytes:
        return "0x"+data.hex()
    else:
        return data

# def parseArgWithFormat(argDict, abiInputInfo):
#     argList = list()
#     for index, inputInfo in enumerate(abiInfo["abi"]["inputs"]):
#         arg = {
#             "name": inputInfo["name"],
#             "type": inputInfo["type"],
#         }
#         argContent = argDict[inputInfo["name"]]
#         if type(argContent) == list:
#             if "tuple" in inputInfo["type"]:
#                 arg["components"] = inputInfo["components"]
#                 tupleList = list()
#                 for tupleItem in argContent:
#                     # componentList = list()
#                     componentDict = dict()
#                     for i, component in enumerate(inputInfo["components"]):
#                         componentDict[component["name"]] = normalizeArg(component["type"], tupleItem[i])
#                         # componentList.append(normalizeArg(component["type"], tupleItem[i]))
#                     tupleList.append(componentDict)
#                 arg["content"] = tupleList
#             else:
#                 arg["content"] = [normalizeArg(argType=inputInfo['type'], data=x) for x in argContent]
#         elif inputInfo["type"] == 'tuple':
#             arg["components"] = inputInfo["components"]
#             # componentList = list()
#             componentDict = dict()
#             for i, component in enumerate(inputInfo["components"]):
#                 # componentList.append(normalizeArg(component["type"], argContent[i]))
#                 componentDict[component["name"]] = normalizeArg(component["type"], argContent[i])
#             arg["content"] = componentDict
#         else:
#             arg["content"] = normalizeArg(inputInfo["type"], argContent)

#         argList.append(arg)
#     return argList

def _getArgFormat(arg_type, inputInfo):

    if arg_type == "tuple":
        # deal with tuple
        argFormatDict = dict()
        argFormatDict['type'] = "tuple"
        argFormatDict['components'] = dict()
        argFormatForDecode = list()
        tmpName = 0
        for component in inputInfo['components']:
            argName = component["name"]
            if argName == "":
                argName = f"tmpArg{tmpName}"
                component["name"] = argName
                tmpName += 1
            argFormatDict['components'][argName], subArgFormatForDecode = _getArgFormat(component['type'], component)
            argFormatForDecode.append(subArgFormatForDecode)
        return argFormatDict, f"({','.join(argFormatForDecode)})"
    elif "[]" in arg_type or ("[" in arg_type and "]" in arg_type):
        # deal with list
        baseType = inputInfo['type'].split("[")[0]
        listType = "[" + inputInfo['type'].split("[")[1]
        subArgFromatDict, subArgFormatForDecode = _getArgFormat(baseType, inputInfo)
        subArgFromatDict['type'] = arg_type
        return subArgFromatDict, subArgFormatForDecode+listType
    elif isNormalType(arg_type):
        return {
            "type": arg_type
        }, arg_type
    else:
        assert False, f"unkonwn method type {arg_type}"


def getFuncSignatureAndFormat(method):
    
    argFormatDict = dict()
    argFormatForDecode = list()
    tmpName = 0
    for inputInfo in method['inputs']:
        argName = inputInfo["name"]
        if argName == "":
            argName = f"tmpArg{tmpName}"
            inputInfo['name'] = argName
            tmpName += 1

        argFormatDict[argName], subArgFormatForDecode = _getArgFormat(inputInfo['type'], inputInfo)
        argFormatForDecode.append(subArgFormatForDecode)

    methodString = f"{method['name']}(" + ",".join([x for x in argFormatForDecode]) + ")"
    k = sha3.keccak_256()
    k.update(methodString.encode('utf-8'))
    sig = k.hexdigest()
    # print(sig, methodString, argFormat)
    return sig, {"methodString":methodString, "argFormatDict": argFormatDict, "argFormatForDecode":argFormatForDecode}

def _convertArgsDict(argType, argFormatDict, argContent):
    if argType == "tuple":
        newDict = dict()
        for index, name in enumerate(argFormatDict["components"]):
            newDict[name] = _convertArgsDict(argFormatDict["components"][name]['type'], argFormatDict["components"][name], argContent[index])
        return newDict
    elif "[]" in argType or ("[" in argType and "]" in argType):
        newList = list()
        baseType = argType.split("[")[0]
        for item in argContent:
            newList.append(_convertArgsDict(baseType, argFormatDict, item))
        return newList
    elif isNormalType(argType):
        if argType == "address":
            argContent = argContent.lower()
        return normalizeArg(argContent)
    else:
        assert False, f"unkonwn method type {argType} in convertArgsDict"

"""
attach name to args and convert bytes to hex
"""
def convertArgsDict(argsDict, argFormatDict):
    newDict = dict()
    for name, argInfo in argFormatDict.items():
        if name in argsDict:
            newDict[name] = _convertArgsDict(argInfo['type'], argInfo, argsDict[name])
    return newDict

def genBranch(jumpList):
    branchString = "-".join([f"{x['pc']}-{x['destination']}" for x in jumpList])
    return branchString

class TxExtractor(object):

    def __init__(self, addrs, abiList):
        self.addresses = addrs
        self.functionAbi = dict()
        self.eventAbi = dict()
        
        self.initABI(abiList)

    def initABI(self, abiList):
        for abi_json in abiList:
            for method in abi_json:
                if 'name' in method:
                    sig, argInfoDict = getFuncSignatureAndFormat(method=method)
                    if method["type"] == "function":
                        sig = sig[:8]
                        if "stateMutability" in method:
                            argInfoDict["stateMutability"] = method["stateMutability"]
                        else:
                            argInfoDict["stateMutability"] = "None"
                        argInfoDict['abi'] = method
                        self.functionAbi[sig] = argInfoDict
                    elif method["type"] == "event":
                        topicFormat = []
                        dataArgFromatForDecode = []
                        dataArgNames = []
                        for index, x in enumerate(method["inputs"]):
                            if x["indexed"] == False:
                                dataArgFromatForDecode.append(argInfoDict["argFormatForDecode"][index])
                                dataArgNames.append(x['name'])
                            else:
                                topicFormat.append({
                                    "name": x["name"],
                                    "type": x["type"]
                                })
                        argInfoDict["dataArgFromatForDecode"] = dataArgFromatForDecode
                        argInfoDict["dataArgNames"] = dataArgNames
                        argInfoDict['topicFormats'] = topicFormat
                        self.eventAbi[sig] = argInfoDict
                    else:
                        print(method)
                    # print(sig, argInfoDict["methodString"])
        w3 = Web3()
        # only for decode function input
        self.contract = w3.eth.contract(address="0x0000000000000000000000000000000000000000", abi=[x["abi"] for x in self.functionAbi.values()])

    def extractExTx(self, transaction, excludePartialErr=False):
        callList = list()
        # print(transaction["blockNumber"], transaction["position"])
        self.extractcall(transaction["call"], callList, excludePartialErr)
        for call in callList:
            call["blockNumber"] = transaction["blockNumber"]
            call["position"] = transaction["position"]
            call["timestamp"] = transaction["timestamp"]
            call["tx.origin"] = transaction["call"]["from"]
        return callList

    def extractcall(self, call, callList, excludePartialErr):
        
        if excludePartialErr and call["err"] != "":
            return list(), list(), True
        
        includeErr = False
        isTargetFunction = False
        eventList = list()

        tmpCall = {
            "from" : call["from"],
            "to" : call["to"],
            "value" : call["value"] if call["type"] in ["CALL","CREATE"] and call["value"] > 0 else 0,
            "args" : list(),
        }
        if call["to"] in self.addresses and call["type"] in ["CALL","CREATE"] and call["input"] != None:
            sig = base64.b64decode(call["input"]).hex()[:8]
            # print(self.defi_info["abi"])
            if sig in self.functionAbi:
                if self.functionAbi[sig]["stateMutability"] != "view":
                    isTargetFunction = True
                    tmpCall["sig"] = sig
                    tmpCall["name"] = self.functionAbi[sig]["methodString"]
                    # deal with the case when len(call["input"][4:]%32) != 0, fill 00 to fix
                    tmpInput = base64.b64decode(call["input"]).hex()
                    try:
                        _, argsDict = self.contract.decode_function_input(tmpInput)
                        tmpCall["args"] = convertArgsDict(argsDict, self.functionAbi[sig]["argFormatDict"])
                    except:
                        # print(self.functionAbi[sig]["methodString"], tmpInput)
                        # if len(tmpInput[8:]) % 64 != 0:
                        #     tmpInput = tmpInput + "0" * (64 - len(tmpInput[8:]) % 64)
                        # _, argsDict = self.contract.decode_function_input(tmpInput)
                        tmpCall['args'] = {
                            "rawbytes": "0x" + base64.b64decode(call["input"]).hex()[8:]
                        }
            else:
                # print(sig)
                # assert False, "error in extractTxs"
                isTargetFunction = True
                if call['type'] == "CALL":
                    tmpCall["name"] = sig
                    tmpCall['sig'] = sig
                    tmpCall['args'] = {
                        "rawbytes": "0x" + base64.b64decode(call["input"]).hex()[8:]
                    }
                elif call["type"] == "CREATE":
                    tmpCall["name"] = "constructor"
                    tmpCall["sig"] = sig
                    tmpCall['args'] = {"rawbytes":"0x"}

        tmpCall["subCalls"] = list()
        subCallList = list()
        if call["calls"] != None:
            for tx in call["calls"]:
                inEventList, inCalls, isErr = self.extractcall(tx, callList, excludePartialErr)
                subCallList.extend(inCalls)
                eventList.extend(inEventList)
                if isTargetFunction and tx["type"] in ["CALL", "DELEGATECALL"]:
                    tmpCall["subCalls"].extend(inCalls)
                # deal with partical err
                if isErr:
                    includeErr = True

        if call["logs"]:
            for e in call["logs"]:
                tmpEvent = self.extractEvent(e)
                if tmpEvent != None:
                    eventList.append(tmpEvent)

        tmpCallList = list()
        if call["type"] in ["CALL", "CREATE"] and (isTargetFunction or call['from'] in self.addresses) and call['isState']:
            tmpCall["callLocation"] = call["callLocation"]
            tmpCall["preAlloc"] = call["preState"]
            tmpCall["postAlloc"] = call["postState"]
            tmpCall["preTokenBalance"] = call.get("preTokenBalance", dict())
            tmpCall["postTokenBalance"] = call.get("postTokenBalance", dict())
            # tmpCallList.append(tmpCall)
            if isTargetFunction:
                tmpCall["branch"] = genBranch(call["branch"]) if "branch" in call else ""
            if isTargetFunction and not includeErr:
                tmpCall["logs"] = eventList
                callList.append(tmpCall)
                eventList = list()
            
        # deal with call, when call is call, return one itself
        # deal with delegateCall, when call is delegate return its subcalls
        if call["type"] == "DELEGATECALL":
            return eventList, subCallList, False
        else:
            return eventList, tmpCallList, False
        

    def extractEvent(self, event):
        sig = event["topics"][0][2:]
        if sig in self.eventAbi and event["address"] in self.addresses:
            # deal with topics
            tmpEvent = {
                "name": self.eventAbi[sig]["methodString"].split('(')[0],
                "address": event["address"],
                "sig": sig,
            }
            argsDict = dict()
            # print(self.eventAbi[sig]["methodString"], self.eventAbi[sig]["topicFormats"])
            # for i, topic in enumerate(event["Topics"][1:]):
            for i, topicFormat in enumerate(self.eventAbi[sig]["topicFormats"]):
                topic = event["topics"][1:][i]
                if topicFormat["type"] == "string":
                    args = [topic]
                elif "byte" in topicFormat["type"]:
                    args = [topic]
                else:
                    argFormat = [topicFormat["type"]]
                    args = decode(argFormat, bytes.fromhex(topic[2:]))
                # only one arg
                assert len(args) == 1, "error in parsing topics"
                argsDict[topicFormat["name"]] = normalizeArg(args[0])

            # deal with data
            if event["data"]:
                argFormatForDecode = self.eventAbi[sig]["dataArgFromatForDecode"]
                args = decode(argFormatForDecode, bytes.fromhex(base64.b64decode(event["data"]).hex()))
                for index, arg in enumerate(args):
                    argsDict[self.eventAbi[sig]['dataArgNames'][index]] = arg

            # print(self.eventAbi[sig]["argFormatDict"], argsDict)
            tmpEvent["args"] = convertArgsDict(argsDict, self.eventAbi[sig]["argFormatDict"])
            return tmpEvent
        return None

if __name__ == "__main__":
    txExtractor = TxExtractor(["0x73fc3038b4cd8ffd07482b92a52ea806505e5748"], [])
    with open("../invFuzz/hunter/dapps_withCallLocation/20201112_akropolis/0x73fc3038b4cd8ffd07482b92a52ea806505e5748/11012250_16.json", "r") as f:
        j = json.load(f)
        callList = txExtractor.extractExTx(j["ExTx"])

        for call in callList:
            print([x["to"] for x in call["subCalls"]])

