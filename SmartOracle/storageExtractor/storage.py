import json
from storageExtractor.layout import extractStorageLayout

import os 
import json 
import math 
from web3 import Web3
import traceback
import math 

from functools import lru_cache

def toHex(val, size=8):
    # print(type(val))
    if isinstance(val, str):
        assert val.startswith("0x")
        val = int(val, 16)
    try:    
        assert isinstance(val, int)
    except:
        # print(val)
        traceback.print_exc()
        pass
    return '0x{0:0{1}x}'.format(val, size)

def toInt(hexstr):
    if not isinstance(hexstr, int):
        if not isinstance(hexstr, str):
            hexstr = hexstr.hex()
        if hexstr.startswith("0x"):
                return int(hexstr, 16)
        else:
                return int(hexstr)
            
    else:
        return hexstr 

ClassMapping = dict() 
Constants = set()
storages_slot = dict()


# For different types including int, uint, array, mapping, struct, enum and etc., 
# each storage must have a known slot and optional value
def Type_init(self, astId, contract, label, offset, slot, type):
    global Constants
    self.astId, self.contract, self.name, self.offset, self.slot, self.type_identifier = astId, contract, label, offset, slot, type 
    
    self.offset = toInt(self.offset)
    self.slot = toInt(self.slot)
    
    try:
        if self.encoding=="dynamic_array":
            self.firstElementSlot = toInt(Web3.soliditySha3(["uint256"], [self.slot]))
            self.value = 0
            self.elements = list() 
            # the num of elements is stored at memory of 'self.slot'
            self.numOfItems = 0
            Constants.add(self.numOfItems)
            Constants.add(self.numOfItems+1)

        elif self.encoding == "mapping":
            self.value = 0
            self.values = dict()
        elif self.encoding == "inplace":
            """
                uint8, .., uint256
                int8, .. , int256
                byte8, .., byte32
                address
                bytes, or string (note: length <= 32 bytes)
                fixed array
            """
            if self.isStruct():
                self.value = StorageMonitor(self.members, self.slot)
            elif self.getType().find("[")==-1 and (self.getType().find("int")!=-1 or self.isEnum() or self.getType().find("bool")!=-1):
                self.value = 0
            elif self.basecls is not None:
                # this is a static array
                baseNumOfBytes = int(ClassMapping[self.basecls].numOfBytes)
                self.staticarraysize = int(int(self.numOfBytes)/baseNumOfBytes)
                self.elements = []
                for i in range(self.staticarraysize):
                    elementSlot = int(self.slot) + int((i*baseNumOfBytes)/32)
                    self.elements.append(self.getBasecls()(astId=self.astId, contract=self.contract, label="", offset=0, slot=elementSlot, type=self.getBasecls().label))
                self.values = self.elements
            else:
                self.value = toHex(0, size=2*self.numOfBytes)
            # TODO 
            pass 
        elif self.encoding == "bytes":
            # TODO 
            # This default value may be not true
            self.value = "0x0"

        # For context slicing; record the tainted mapping keys w.r.t. each transaction
        self.taintedKeys = []
    except Exception as e:
        print(e)
        print(self.members)
        traceback.print_exc()
        # raise Exception("Unknown error")

class AbstractStorageItem:
    def __init__(self):
        pass

    def getSlot(self):
        return self.slot

    def getLabel(self):
        return self.name
    
    def getValue(self):
        if self.isInplace() and self.getType().find("int")!=-1:
            if self.basecls is not None:
                return self.values 
            # return int(self.value)%(10**15) 
            else:
                return int(self.value) 
        return self.value
    
    @property
    def mappings(self):
        return self.values

    @classmethod 
    def getType(cls):
        return cls.label

    @classmethod
    def isBytes(cls):
        return cls.encoding == "bytes"

    @classmethod
    def isInplace(cls):
        return cls.encoding == "inplace"

    @classmethod
    def isMapping(cls):
        return cls.encoding=="mapping"
    
    @classmethod
    def isDynamicArray(cls):
        return cls.encoding=="dynamic_array"
    
    @classmethod
    def isFixedArray(cls):
        return cls.encoding=="inplace" and cls.getType().find("[")!=-1
    
    @classmethod
    def isStruct(cls):
        return cls.getType().find("struct") != -1

    @classmethod
    def isEnum(cls):
        return cls.getType().find("enum") != -1

    @classmethod
    def hasArrayMappingValue(cls):
        global ClassMapping
        assert cls.isMapping()
        return ClassMapping[cls.valuecls].encoding=="dynamic_array"
    
    @classmethod
    def hasStructMappingValue(cls):
        global ClassMapping
        assert cls.isMapping()
        return ClassMapping[cls.valuecls].members is not None 
    
    @classmethod
    def getMappingStruct(cls):
        global ClassMapping
        assert cls.hasStructMappingValue()
        return ClassMapping[cls.valuecls]
    
    @classmethod
    def getMappingDynArray(cls):
        global ClassMapping
        assert cls.hasArrayMappingValue()
        return ClassMapping[cls.valuecls]
    
    @classmethod
    def getBasecls(cls):
        assert cls.basecls is not None 
        global ClassMapping
        # debug when cls.basecls == bytes4
        if "[]" not in cls.basecls and "bytes" in cls.basecls:
            return ClassMapping["bytes32"]
        return ClassMapping[cls.basecls]

    @classmethod
    def getValuecls(cls):
        assert cls.valuecls is not None 
        global ClassMapping
        return ClassMapping[cls.valuecls]
    
    @classmethod
    def getKeycls(cls):
        assert cls.keycls is not None 
        global ClassMapping
        if cls.keycls in ClassMapping:
            return ClassMapping[cls.keycls]
        else:
            return None
    
    def _setValue(self, slot, value):
        raise NotImplementedError()

    def setValue(self, slot, value, additionalKeys=list()):
        return self._setValue(slot, value, additionalKeys)

def setValueForInplace(self, slot, value, additionalKeys=list()):
    global Constants
    try:
        assert isinstance(slot, str) and isinstance(value, str)
        assert slot.startswith("0x") and value.startswith("0x")
        slot = "0x"+slot.replace("0x", "")
        value = "0x"+value.replace("0x", "")
        if self.isStruct():
            if self.value.readStateChange(slot, value, additionalKeys):
                return True 
            else:
                return False 
        # print(slot, value, self.label, self.slot)
        if self.slot <= int(slot, 16) and int(slot, 16) <= self.slot + int((int(self.numOfBytes) + int(self.offset) -1) / 32):
            if self.isEnum():
                value = "0x"+value[66-2*(self.offset+self.numOfBytes):66-2*self.offset].replace("0x", "")
                self.value = int(value, 16)
                if slot not in storages_slot:
                    storages_slot[slot] = dict()
                storages_slot[slot]["numOfBytes"] = self.numOfBytes
                storages_slot[slot]["offset"] = self.offset
            else:
                if self.basecls is not None:
                    element_slot = int(slot, 16)-self.slot 
                    baseNumOfBytes = self.getBaseCls().numOfBytes
                    element_index_start, element_index_end = element_slot * 32 / baseNumOfBytes, (element_slot+1) * 32 / baseNumOfBytes
                    for index in range(element_index_start, min(element_index_end, self.staticarraysize)):
                        value = "0x"+value[66-2*(self.offset+(index+1)*baseNumOfBytes):66-2*(self.offset+index*baseNumOfBytes)].replace("0x", "")
                        if self.getType().find("int")!=-1:
                            value = int(value, 16)
                        elif self.getType().find("bool") !=-1:
                            value = int(value, 16)
                        self.values[index] = value 
                        if slot not in storages_slot:
                            storages_slot[slot] = dict()
                        storages_slot[slot]["numOfBytes"] = baseNumOfBytes
                        storages_slot[slot]["offset"] = self.offset
                        storages_slot[slot]["index"] = self.index
                else:
                    value = "0x"+value[66-2*(self.offset+self.numOfBytes):66-2*self.offset].replace("0x", "")
                    if self.getType().find("int")!=-1:
                        self.value = int(value, 16)
                        Constants.add(self.value)
                    elif self.getType().find("bool") !=-1:
                        self.value = int(value, 16)
                        # Constants.add(self.value)
                    else:
                        self.value = value 
                        if self.getType().find("address")!=-1:
                            Constants.add(self.value)
                    if slot not in storages_slot:
                        storages_slot[slot] = dict()
                    storages_slot[slot]["numOfBytes"] = self.numOfBytes
                    storages_slot[slot]["offset"] = self.offset
            return True 
        return False 
    except:
        # traceback.print_exc()
        pass
    return False

def setValueForDynamicArray(self, slot, value,  additionalKeys=list()):
    global ClassMapping
    global Constants
    assert isinstance(slot, str) and isinstance(value, str)
    assert slot.startswith("0x") and value.startswith("0x")
   
    try:
        if int(slot, 16) == self.slot:
            self.value = int(value, 16)
            self.numOfItems = self.value 
            Constants.add(self.numOfItems)
            Constants.add(self.numOfItems+1)
            return True

        elif self.firstElementSlot <= int(slot, 16) \
        and int(slot, 16) <= (self.firstElementSlot + math.ceil(self.getBasecls().numOfBytes/32)*(len(self.elements)+1)):
            # if config.DEBUG:
            #     print("find array slot...")
            index = int((int(slot, 16) - self.firstElementSlot) /math.ceil(self.getBasecls().numOfBytes/32))
            # TODO
            # Here, we assume every item in an array are stored at a new slot
            # This may be not true. May apply to uint128 ... uint256 only
            # Need to check later
            elementSlot = index * math.ceil(self.getBasecls().numOfBytes/32) + self.firstElementSlot
            assert elementSlot <= int(slot, 16), "elementSlot must be less than or equal to slot"
            if index < len(self.elements):
                # if config.DEBUG:
                #     print("update item")
                self.elements[index].setValue(slot, value)
            else:
                # if config.DEBUG:
                #     print("create item")
                self.elements.append(self.getBasecls()(astId=self.astId, contract=self.contract, label="", offset=0, slot=elementSlot, type=self.getBasecls().label))
                self.elements[-1].setValue(slot, value)
                self.numOfItems = len(self.elements)
            return True 
    except:
        traceback.print_exc()
    return False 

@lru_cache
def soliditySha3(key, slot):
    if isinstance(key, int):
        key = key
    elif isinstance(key, str):
        if key.startswith("0x"):
            key = int(key, 16)
        else:
            try:
                key = int(key)
            except:
                key = 0
    else:
        assert False, f"{key} is not supported"
    if key < 0:
        key = abs(key)
    assert key >= 0
    # return Web3.solidity_keccak(["uint256", "uint256"], [key, slot])
    return Web3.soliditySha3(["uint256", "uint256"], [key, slot])

def setValueForMapping(self, slot, value, additionalKeys=list()):
    global ClassMapping
    global Constants
    assert isinstance(slot, str) and isinstance(value, str)
    assert slot.startswith("0x") and value.startswith("0x")

    @lru_cache
    def calculateKeySlot(key):
        #  mapping(uintXX=>) or mapping(intXXX => )
        if ClassMapping[self.keycls].label.find("int")!=-1 and ClassMapping[self.keycls].label.find("[")==-1:
            ret = soliditySha3(key, self.slot)
            # print("int", ret, ret.hex())
            return toInt(ret.hex())
        # mapping(address=>) or mapping(address => )
        elif ClassMapping[self.keycls].label.find("address")!=-1 and ClassMapping[self.keycls].label.find("[")==-1:
            ret = soliditySha3(key, self.slot)
            # print("address", ret, ret.hex())
            return toInt(ret.hex())
        
        # mapping(bytes32=>) or mapping(bytes32 => )
        elif ClassMapping[self.keycls].label.find("bytes32")!=-1 and ClassMapping[self.keycls].label.find("[")==-1:
            ret = soliditySha3(key, self.slot)
            # print("bytes32", ret, ret.hex())
            return toInt(ret.hex())

        elif (isinstance(key, int) or isinstance(key, str)) and \
             ClassMapping[self.keycls].numOfBytes *2 +2 > (len(hex(key)) if isinstance(key, int) else len(key)):
            ret = soliditySha3(key, self.slot)
            # print("key of arbitrary type:", key, ret.hex())
            return toInt(ret.hex())
        else:
            assert False, f"{key} is not supported for {self.__class__}"
            # pass 
    
    keycls = self.getKeycls()

    for key in additionalKeys:
            # try:
            if keycls != None:
                if keycls.getType().find("int")!=-1:
                    if isinstance(key, str):
                        if key.startswith("0x"):
                            key = int(key, 16)
                        else:
                            try:
                                key = int(key)
                            except:
                                continue
                if type(key) == bool:
                    continue
                candiate_slot = calculateKeySlot(key)
                # print("candiate_slot:", key, candiate_slot)
                if key not in self.values:
                    var = self.getValuecls()(astId=self.astId, contract=self.contract, label="", offset=0, slot=candiate_slot, type=self.getValuecls().label)
                else:
                    var = self.values[key]
                # print(var)
                # print('\n'.join(['{0}: {1}'.format(item[0], item[1]) for item in var.__dict__.items()]))
                # print("numofbytes", self.numOfBytes)
                # print("ClassMapping",ClassMapping[self.keycls].numOfBytes)

                if True == var.setValue(slot, value, additionalKeys=additionalKeys):
                    self.values[key] = var
                    if slot not in storages_slot:
                        storages_slot[slot] = dict()
                    storages_slot[slot]["key"] = key
                    # print("start")
                    # for k in self.values:
                        # print(k, self.values[k].value)
                    # print(slot, toInt(value), key)
                    # self.taintedKeys = []
                    self.taintedKeys.append(key)
                    # incase there is a nested mapping structure
                    if len(var.taintedKeys)>0:
                        self.taintedKeys.append(var.taintedKeys)
                    return True 
            # except:
            #     pass 
    
    return False 

def setValueForStructMappingValue(self, slot, value, additionalKeys=list()):
    return self.setValueForMapping(slot, value, additionalKeys ) 

def setValueForArrayMappingValue(self, slot, value, additionalKeys=list()):
    return self.setValueForMapping(slot, value, additionalKeys)  

def setValueForInplaceStructValue(self, slot, value, additionalKeys=list()):
    return self.setValueForMapping(slot, value, additionalKeys) 

def setValueForBytes(self, slot, value, additionalKeys=list()):
    if self.setValueForInplace(slot, value, additionalKeys):
        return True
    else:
        return False 

def _setValue(self, slot, value, additionalKeys=list()):
    if self.isInplace():
        return self.setValueForInplace(slot, value, additionalKeys) 
    elif self.isDynamicArray():
        return self.setValueForDynamicArray(slot, value, additionalKeys) 
    elif self.isMapping():
        return self.setValueForMapping(slot, value, additionalKeys) 
    elif self.isBytes():
        return self.setValueForBytes(slot, value, additionalKeys)
    else:
        raise LookupError(f"unfounded variable type {self}")
            
def createTypeClasses(types):
    global ClassMapping
    for type_identifier in types:
        try:
            if isinstance(type_identifier, dict):
                type_identifier = type_identifier["type"]
            
            ClassMapping[type_identifier] = type(type_identifier, (AbstractStorageItem, ), \
                {
                    "encoding": types[type_identifier]["encoding"],
                    "label": types[type_identifier]["label"],
                    "basecls": types[type_identifier]["base"] if "base" in types[type_identifier] else None,
                    "numOfBytes": toInt(types[type_identifier]["numberOfBytes"]) if "numberOfBytes" in types[type_identifier] else None,
                    "keycls": types[type_identifier]["key"] if "key" in types[type_identifier] else None,
                    "valuecls": types[type_identifier]["value"] if "value" in types[type_identifier] else None,
                    "members": types[type_identifier]["members"] if "members" in types[type_identifier] else None,
                    "__init__": Type_init,
                    "_setValue": _setValue,
                    "setValueForInplace": setValueForInplace, 
                    "setValueForDynamicArray": setValueForDynamicArray,
                    "setValueForMapping": setValueForMapping, 
                    "setValueForStructMappingValue": setValueForStructMappingValue, 
                    "setValueForArrayMappingValue": setValueForArrayMappingValue,
                    "setValueForInplaceStructValue": setValueForInplaceStructValue,
                    "setValueForBytes": setValueForBytes,
                }
            )
        except:
            traceback.print_exc()
            # print(type_identifier, types)
            # pass 
            raise Exception("Unsupported type")
    pass 

class StorageMonitor:
    
    def __init__(self, storageJson, slot=0, typeJson = None):
        global ClassMapping

        if typeJson is not None:
            try:
                if type(storageJson) == int:
                    print(storageJson)
                assert not isinstance(storageJson, int)

                if type(typeJson) == int:
                    print(typeJson)
                assert not isinstance(typeJson, int)
            except:
                print(storageJson)
                print(typeJson)
                raise Exception("unknown error")
            createTypeClasses(types=typeJson)
        
        self.slot = toInt(slot) 
        self.storages = list()

        self.storageJson = storageJson
        
        self.availableslots = dict()
        self.grid_storages = dict()
        grid_storages = self.grid_storages 

        self.fields = list()

        for storageItem in storageJson:
            try:
                astId, contract, label, offset, slot, type_identifier = storageItem["astId"], storageItem["contract"], storageItem["label"],storageItem["offset"],storageItem["slot"],storageItem["type"]
                if isinstance(slot, str):
                    if slot.startswith("0x"):
                        slot = int(slot, 16) + self.slot  
                    else:
                        try:
                            slot = int(slot) + self.slot 
                        except:
                            print(slot, type(slot), self.slot, type(self.slot))
                            raise Exception()

                if isinstance(offset, str):
                    if offset.startswith("0x"):
                        offset = int(offset, 16)
                    else:
                        offset = int(offset)
                if slot not in grid_storages:
                    grid_storages[slot] = dict()
                
                assert type_identifier in ClassMapping
                grid_storages[slot][offset] = ClassMapping[type_identifier](astId, contract, label, offset, slot, type_identifier)
                self.storages.append(grid_storages[slot][offset])
                setattr(self, label, grid_storages[slot][offset])
                self.fields.append((label, grid_storages[slot][offset]))
            except:
                pass
                # traceback.print_exc()
                # print(storageItem) 
                # print(ClassMapping[type_identifier])
                # raise Exception("Unknown Error")
    
    def getFields(self):
        return self.fields

    def getAllInplaceValues(self):
        inplace_values = set() 
        for storageItem in self.storages:
            if storageItem.isInplace() and not storageItem.isStruct() and storageItem.basecls is None:
               inplace_values.add(storageItem.getValue())
        return inplace_values

    def readStateChange(self, slot, value, additionalKeys):
        assert isinstance(value, str), "value should be hex string"
        assert value.startswith("0x")==True, "value should be hex string"
        assert isinstance(slot, str), "slot should be hex string"
        assert slot.startswith("0x")==True, "slot should be hex string"
        
        hit = False
        for storageItem in self.storages:
            if storageItem.setValue(slot, value, additionalKeys):
                if slot not in storages_slot:
                    storages_slot[slot] = dict()
                storages_slot[slot]["storageItem"] = storageItem
                # print(slot, value)
                hit = True 
                if storageItem.numOfBytes>=32:
                    break 
        if hit:
            return True 
        else:
            return False 

    def txStateTransition(self, slot_statechanges, additionalKeys):
        for slot_statechange in slot_statechanges:
            slot, state = tuple(slot_statechange.split(":"))
            self.readStateChange(slot, state, additionalKeys=additionalKeys)

def isString(v_type):
    return  v_type.find("address")!=-1 or v_type.find("bytes")!=-1 or  v_type.find("contract")!=-1
def isBool(v_type):
    return  v_type.find("bool")!=-1 

def isArray(v_type):
    return  v_type.find("[")!=-1

class StorageExtractor(StorageMonitor):
    def __init__(self, proxyAddr, logicConfig, source_path):
        storageLayout_path = f"{source_path}/storageLayout.json"
        version = logicConfig["compilerVersion"]
        contractName = logicConfig["contractName"]
        mainContractPath = logicConfig['mainContractPath'].replace(f"{proxyAddr}/contracts/{logicConfig['address']}/", "")
        storageLayout = extractStorageLayout(mainContractPath, contractName, version, contractsPath=source_path, outputStorageFile=storageLayout_path)
        super().__init__(typeJson=storageLayout["types"], storageJson = storageLayout["storage"])
        self.address = proxyAddr
        self.storageLayout = storageLayout

    def travelArg(self, arg):
        if isinstance(arg, dict):
            for component in arg.values():
                self.travelArg(component)
        elif isinstance(arg, list):
            for item in arg:
                self.travelArg(item)
        else:
            if isinstance(arg, str) and len(arg) <= 66:
                self.envs.add(arg.lower())
            if isinstance(arg, int):
                self.envs.add(arg)
        
    def addTxEnvVar(self, var_dict):
        self.envs.add(var_dict["from"].lower())
        for arg in var_dict["args"].values():
            self.travelArg(arg)

    def readTxStorage(self, var_dict):
        slots = list()
        for slot, state in var_dict["points"]["pre"]["storage"].items():
            slots.append(f"{slot}:{state}")

        self.envs = set()
        self.addTxEnvVar(var_dict)
        self.envs.update(self.getAllInplaceValues())
        # debug
        if "0x" in self.envs:
            self.envs.remove("0x")
        self.txStateTransition(slot_statechanges = slots, additionalKeys=self.envs)
        storageVar = dict()
        for slot in storages_slot:
            # print(slot, self.storages_slot[slot].name, self.storages_slot[slot].type_identifier)
            # print(storages_slot[slot]["storageItem"].name, storages_slot[slot]["storageItem"].type_identifier)
            if "numOfBytes" in storages_slot[slot] and "offset" in storages_slot[slot]:
                storageVar[slot] = dict()
                storageVar[slot]["name"] = storages_slot[slot]["storageItem"].name
                storageVar[slot]["type"] = storages_slot[slot]["storageItem"].type_identifier
                storageVar[slot]["numOfBytes"] = storages_slot[slot]["numOfBytes"]
                storageVar[slot]["offset"] = storages_slot[slot]["offset"]
                if "key" in storages_slot[slot]:
                    storageVar[slot]["key"] = storages_slot[slot]["key"]
                if "index" in storages_slot[slot]:
                    storageVar[slot]["index"] = storages_slot[slot]["index"]
        return storageVar

if __name__ == "__main__":
    # dapp = "meter_io"
    # source_path = "/home/pc/disk1/sujzh3/invFuzz/invHunter/dapps"
    # with open(f"{source_path}/{dapp}/config.json") as f:
    #     configs = json.load(f)

    # for addr, config in configs.items():

    #     dapp_path = f"{source_path}/{dapp}/{addr}" 

    #     var_dict_list_path = dapp_path + "/check_var_dict.json"

    #     with open(var_dict_list_path, "r") as f:
    #         var_dict_list = json.load(f)
    #     extractor = StorageExtractor(dapp=dapp, addr=addr, config=config, source_path=source_path)

    #     slot_dict = dict()
    #     for var_dict in var_dict_list[:]:
    #         slot_dict.update(extractor.readTxStorage(var_dict))

    #     with open(f"{dapp_path}/slot_dict.json", "w") as f:
    #         json.dump(slot_dict, f)

    source_path = "/home/pc/disk1/sujzh3/invFuzz/invHunter/experiment"
    for dapp in os.listdir("experiment"):
        print(dapp)
        with open(f"{source_path}/{dapp}/config.json") as f:
            configs = json.load(f)
        assert len(configs) == 1, "more than one addr"
        for addr, config in configs:
            extractor = StorageExtractor(dapp=dapp, addr=addr, config=config, source_path=source_path)
