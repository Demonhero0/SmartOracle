from web3 import Web3
from functools import lru_cache
from eth_abi import decode
import json
import math

# for mapping
@lru_cache
def soliditySha3(key:int, slot:int):
    return Web3.soliditySha3(["uint256", "uint256"], [key, slot])
        
def normalizeArg(data):
    if type(data) == bytes:
        return "0x"+data.hex()
    else:
        return data

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

def calMappingKey(key, slot):
    try:
        if isinstance(key, str):
            key = int(key, 16)
        slot = int(slot, 16)
        return soliditySha3(key, slot).hex()
    except:
        return None

def travelArg(arg, keySet):
    if isinstance(arg, dict):
        for component in arg.values():
            travelArg(component, keySet)
    elif isinstance(arg, list):
        for item in arg:
            travelArg(item, keySet)
    else:
        if type(arg) == str and len(arg) <= 66:
            keySet.add(arg.lower())
        if type(arg) == int:
            keySet.add(arg)

class StateVariableExtractor(object):

    def __init__(self, storageLayout) -> None:
        self.storage = storageLayout['storage']
        self.types = storageLayout['types']

    def searchKeys(self, var_dict):
        keySet = set()
        keySet.add(0)
        keySet.add(var_dict["from"].lower())
        keySet.add(var_dict["to"].lower())
        for arg in var_dict["args"].values():
            travelArg(arg, keySet)
        for event in var_dict["events"]:
            for arg in event["args"].values():
                travelArg(arg, keySet)
        # for point in var_dict["points"]:
        #     for slot in var_dict["points"][point]["storage"]:
        #         keySet.add(var_dict["points"][point]["storage"][slot])
        # print(keySet)
        if "0x" in keySet:
            keySet.remove("0x")
        return keySet

    def loadStateVariable(self, storageMap, mappingKeys):
        self.newMappingKeys = set()
        stateVariableDict = dict()
        mappingStateVariable = []
        for storageInfo in self.storage:
            if "mapping" in storageInfo["type"]:
                mappingStateVariable.append(storageInfo)
                continue
            stateVariableInfo = self.getStateVariableInfo(storageInfo['type'])
            tmpSlot = hex(int(storageInfo["slot"])).replace("0x", "")
            slot = "0x" + "0" * (64 - len(tmpSlot)) + tmpSlot
            tmpValue = self.getStateVariable(slot, storageInfo['type'], storageInfo["offset"], stateVariableInfo["numberOfBytes"], storageMap, mappingKeys)
            if tmpValue != None:
                var_key = storageInfo["label"]
                stateVariableDict[var_key] = tmpValue

        for storageInfo in mappingStateVariable:
            stateVariableInfo = self.getStateVariableInfo(storageInfo['type'])
            tmpSlot = hex(int(storageInfo["slot"])).replace("0x", "")
            slot = "0x" + "0" * (64 - len(tmpSlot)) + tmpSlot
            tmpValue = self.getStateVariable(slot, storageInfo['type'], storageInfo["offset"], stateVariableInfo["numberOfBytes"], storageMap, mappingKeys.union(self.newMappingKeys))
            if tmpValue != None:
                var_key = storageInfo["label"]
                stateVariableDict[var_key] = tmpValue

        return stateVariableDict

    def getStateVariableInfo(self, var_type):
        if var_type in self.types:
            stateVariableInfo = self.types[var_type].copy()
            numberOfBytes = stateVariableInfo["numberOfBytes"]
            if isinstance(numberOfBytes, str):
                numberOfBytes = int(numberOfBytes)
            elif isinstance(numberOfBytes, int):
                numberOfBytes = math.ceil(numberOfBytes/2)
            stateVariableInfo["numberOfBytes"] = numberOfBytes
            return stateVariableInfo
        elif var_type[:4] == "uint":
            intNum = int(var_type[4:])
            numberOfBytes = math.ceil(intNum / 8)
            return {
                "encoding" : "inplace",
                "label" : var_type,
                "numberOfBytes": numberOfBytes
            }
        else:
            return {
                "encoding" : "inplace",
                "label" : "bytes32",
                "numberOfBytes": 32
            }        

    def getStateVariable(self, slot, stateVariableType, offset, numberOfBytes, storageMap, mappingKeys):
        # stateVariableInfo = self.types[stateVariableType]
        stateVariableInfo = self.getStateVariableInfo(stateVariableType)
        if stateVariableInfo["encoding"] == "dynamic_array":
            tmpList = list()
            if slot in storageMap:
                length = int(storageMap[slot], 16)
                targetSlot = Web3.keccak(int(slot, 16)).hex()
                element_type = stateVariableInfo["base"]
                numberOfBytes = stateVariableInfo["numberOfBytes"]
                loadedByteInSlot = 0

                # just for convience
                thisSlot = targetSlot
                if length > 0 and targetSlot in storageMap:
                    for index in range(length):
                        if loadedByteInSlot + numberOfBytes > 32:
                            loadedByteInSlot = 0
                            thisSlot = slotAdd(thisSlot, 1)
                        offset = loadedByteInSlot
                        tmpValue = self.getStateVariable(targetSlot, element_type, offset, numberOfBytes, storageMap, mappingKeys)

                        loadedByteInSlot += numberOfBytes
                        if tmpValue != None:
                            tmpList.append(tmpValue)
            if len(tmpList) > 0:
                return (tmpList, "array")
            return None
        elif stateVariableInfo["encoding"] == "mapping":
            # print(stateVariableInfo["label"], stateVariableInfo["value"])
            mappingDict = dict()
            touchedSlot = set()
            for key in mappingKeys:
                targetSlot = calMappingKey(key, slot)
                # if targetSlot != None and targetSlot in storageMap:
                if targetSlot != None and targetSlot not in touchedSlot:
                    touchedSlot.add(targetSlot)
                    tmpValue = self.getStateVariable(targetSlot, stateVariableInfo['value'], 0, 32, storageMap, mappingKeys)
                    if tmpValue != None:
                        mappingDict[key] = tmpValue
            if len(mappingDict) > 0:
                return (mappingDict, "mapping")
            return None
        elif stateVariableInfo["encoding"] == "inplace" and "members" in stateVariableInfo:
            # for structure
            loadedByteInSlot = 0
            # just for convience
            # thisSlot = hex(int(slot, 16) - 1).replace("0x","")
            thisSlot = slot
            structDict = dict()
            for member in stateVariableInfo["members"]:
                memberType = member["type"]
                # memberTypeInfo = self.types[member_type]
                memberTypeInfo = self.getStateVariableInfo(memberType)

                numberOfBytes = memberTypeInfo["numberOfBytes"]
                if loadedByteInSlot + numberOfBytes > 32:
                    loadedByteInSlot = 0
                    thisSlot = slotAdd(thisSlot, 1)

                offset = loadedByteInSlot
                # member_value = self.getSlotValue(thisSlot, offset, numberOfBytes, member_type, storageMap)
                member_value = self.getStateVariable(thisSlot, memberType, offset, numberOfBytes, storageMap, mappingKeys)

                # print(thisSlot, member_type, member['label'], member_value)
                if member_value != None:
                    var_key = member['label']
                    # if "mapping" in memberType:
                    #     var_key = var_key + "[...]"
                    # elif isinstance(member_value, list):
                    #     var_key = var_key + "[..]"
                    structDict[var_key] = member_value
                loadedByteInSlot += numberOfBytes
            if structDict != {}:
                return (structDict,"struct")
            return None
        elif stateVariableInfo["encoding"] == "inplace" or stateVariableInfo["encoding"] == "bytes":
            tmpValue = self.getSlotValue(slot, offset, numberOfBytes, stateVariableInfo["label"], storageMap)
            if tmpValue != None:
                # update mappingKeys
                travelArg(tmpValue, self.newMappingKeys)
                return (tmpValue, stateVariableInfo["label"])
            return None
        else:
            assert False, f"unknow {stateVariableType}"
            

    def getSlotValue(self, slot, offset, numOfBytes, var_type, storageMap):
        if slot not in storageMap:
            return None
        # print(slot, offset, numOfBytes, var_type)
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
            try:
                # print(slot_value, value, offset, numOfBytes, var_type)
                var_value = decode([var_type], bytes.fromhex(value))[0]
                if var_type == "address":
                    var_value = var_value.lower()
                var_value = normalizeArg(var_value)
            except:
                # print(slot_value, value, offset, numOfBytes, var_type)
                var_value = None
        return var_value
    
if __name__ == "__main__":
    with open("invs_new/20200215_bzx/0x77f973fcaf871459aa58cd81881ce453759281bc/benign_var_dict.json") as f:
        var_dict_list = json.load(f)

    with open("dapps/20200215_bzx/0x77f973fcaf871459aa58cd81881ce453759281bc/contracts/0xc77ee4283b6853900282d5fc498555f642aa52a7/storageLayout.json", "r") as f:
        storageLayout = json.load(f)

    storageLayout = StateVariableExtractor(storageLayout)
    for var_dict in var_dict_list[:2]:
        mappingKeys = storageLayout.searchKeys(var_dict)
        for point in var_dict["points"]:
            storageLayout.loadStateVariable(var_dict["points"][point]["storage"], mappingKeys=mappingKeys)