import numpy as np
import statsmodels.api as sm
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import PolynomialFeatures

def less(varA, varB):
    return varA < varB
    
def lessEqual(varA, varB):
    return varA <= varB

def opposite(varA, varB):
    return -varA == varB

def equal(varA, varB):
    return varA == varB

def inList(var, varList):
    if var in varList:
        return True, varList.index(var)
    else:
        return False, -1

class ComparisonRelation(object):

    def __init__(self, x_name, y_name) -> None:
        self.x_name = x_name
        self.y_name = y_name

# single variable
class IsConstant(object):
    def __init__(self, x_name) -> None:
        self.x_name = x_name
        self.constant = None
        self.type = "normal"

    def __str__(self) -> str:
        return f"{self.x_name} = {self.constant}"

    def constructRelation(self, x_value):
        if type(x_value) == str or type(x_value) == int:
            self.constant = x_value
            return True
        return False

    def checkRelation(self, x_value):
        return self.constant == x_value
    
    def getVars(self):
        return [self.x_name]

SingleInvList = [
    IsConstant
]

# double variables
class EqualRelation(object):
    def __init__(self, x_name, y_name) -> None:
        self.x_name = x_name
        self.y_name = y_name
        # self.variables = [x_name, y_name]
        self.type = "normal"

    def __str__(self) -> str:
        x_name, y_name = (self.x_name, self.y_name) if self.x_name < self.y_name else (self.y_name, self.x_name)
        return f"{x_name} == {y_name}"
    
    def constructRelation(self, x_value, y_value):
        return self.checkRelation(x_value, y_value, True)
    
    def checkRelation(self, x_value, y_value, ignoreZero = False):
        if not isinstance(x_value, list) and not isinstance(x_value, dict) and not isinstance(y_value, list) and not isinstance(y_value, dict):
            if type(x_value) == type(y_value):
                if ignoreZero and (x_value == 0 or y_value == 0):
                    return False
                return x_value == y_value
        return False
    
    def getVars(self):
        return [self.x_name, self.y_name]

class OppositeRelation(object):
    def __init__(self, x_name, y_name) -> None:
        self.x_name = x_name
        self.y_name = y_name
        self.type = "normal"

    def __str__(self) -> str:
        x_name, y_name = (self.x_name, self.y_name) if self.x_name < self.y_name else (self.y_name, self.x_name)
        return f"{x_name} == - ({y_name})"
    
    def constructRelation(self, x_value, y_value):
        return self.checkRelation(x_value, y_value, True)
    
    def checkRelation(self, x_value, y_value, ignoreZero = False):
        if ignoreZero and (x_value == 0 or y_value == 0):
            return False
        if type(x_value) == int and type(y_value) == int:
            return x_value == -y_value 
        return False
    
    def getVars(self):
        return [self.x_name, self.y_name]

ComparisonRelationList = [
    EqualRelation,
    OppositeRelation
]

def flatList(x):
    xList = list()
    if isinstance(x, list):
        for item in x:
            xList.extend(flatList(item))
    elif isinstance(x, dict):
        for item in x.values():
            xList.extend(flatList(item))
    elif isinstance(x, tuple):
        xList.append(x[0])
    else:
        assert False, "error in flatList"
    return xList

class MembershipRelation(object):
    def __init__(self, element, parentList) -> None:
        self.x_name = element
        self.y_name = parentList
        self.type = "normal"

    def __str__(self):
        return f"{self.x_name} in {self.y_name}"

    def constructRelation(self, element, parentList):
        assert not isinstance(element, dict) and not isinstance(element, list), "unsupoort membership relation"
        return self.checkRelation(element, parentList)

    def checkRelation(self, element, parentList):
        flatedList = flatList(parentList)
        if element in flatedList:
            return True
        return False
    
    def getVars(self):
        return [self.x_name, self.y_name]
    
class MembershipBytesRelation(object):
    def __init__(self, element, parent) -> None:
        self.x_name = element
        self.y_name = parent
        self.type = "normal"

    def __str__(self):
        return f"{self.x_name} inByte {self.y_name}"

    def constructRelation(self, element, parentList):
        assert not isinstance(element, dict) and not isinstance(element, list), "unsupoort membership relation"
        return self.checkRelation(element, parentList, True)

    def checkRelation(self, element, parent, ignoreEquation=False):
        if ignoreEquation and element == parent:
            return False
        if type(element) == int:
            return element > 1024 and hex(element)[2:] in parent
        elif type(element) == str:
            return len(element) > 10 and element in parent
        return False
    
    def getVars(self):
        return [self.x_name, self.y_name]
    
class InferenceRelation(object):
    def __init__(self, baseRelation, replacement) -> None:
        self.type = "inference"
        self.baseRelation = baseRelation
        self.replacement = replacement

        self.variables = list()
        for name in baseRelation.getVars():
            self.variables.append({
                    "name": name,
                    "replaceFormat": name,
                })
        # for name in ['x_name','y_name']:
        #     if hasattr(baseRelation, name):
        #         self.variables.append({
        #             "name": getattr(self.baseRelation, name),
        #             "replaceFormat": getattr(self.baseRelation, name),
        #         })
        # self.x_name = self.baseRelation.x_name
        # self.x_replaceFormat = self.baseRelation.x_name

        # self.y_name = self.baseRelation.y_name
        # self.y_replaceFormat = self.baseRelation.y_name

        self.replacementFormat = str(hash(str(self.baseRelation)))
        self.stringFormat = None


    def __str__(self):
        return self.stringFormat

    def constructRelation(self, replacement_value):
        if replacement_value != "":
            flag = False
            for var in self.variables:
                if replacement_value in var['name']:
                    # if "allowance" in str(self.baseRelation):
                    #     print("----------")
                    #     print(var['name'], replacement_value, )
                    var['name'] = var['name'].replace(replacement_value, self.replacement)
                    var['replaceFormat'] = var['name'].replace(replacement_value, self.replacementFormat)
                    flag = True
            # if replacement_value in self.x_name:
            #     self.x_replaceFormat = self.x_name.replace(replacement_value, self.replacementFormat)
            #     self.x_name = self.x_name.replace(replacement_value, self.replacement)
            #     flag = True
            # if replacement_value in self.y_name:
            #     self.y_replaceFormat = self.y_name.replace(replacement_value, self.replacementFormat)
            #     self.y_name = self.y_name.replace(replacement_value, self.replacement)
            #     flag = True
            self.stringFormat = str(self.baseRelation).replace(replacement_value, self.replacement)
            return flag
        return False
    
    def getOriginalVarName(self, replacement_value):
        # print("format", self.x_replaceFormat, self.y_replaceFormat)
        return [var["replaceFormat"].replace(self.replacementFormat, replacement_value) for var in self.variables]
        # return self.x_replaceFormat.replace(self.replacementFormat, replacement_value), self.y_replaceFormat.replace(self.replacementFormat, replacement_value)

    def getModel(self):
        return {
            "variables" : [var['name'] for var in self.variables],
            "replacement": self.replacement
        }
    
    def getVars(self):
        return [var['name'] for var in self.variables]
    # def checkRelation(self, replacement_value, traceDict):
    #     if self.replacement in traceDict:
    #         replacement_value = 
    #     else:
    #         return "exist_nonsensical"
        
    #     self.normalRelation.checkRelation()


      
    
class LinearRelationWithThreeVar(object):

    def __init__(self, x_name, y_name, z_name) -> None:
        self.x_name = x_name
        self.y_name = y_name
        self.z_nane = z_name

    def __str__(self):
        # z = x + y
        return f"{self.z_name} = {self.x_name} + {self.y_name}"
    
    def constructRelation(self, data, threshold=1):
        # if successfully find model, return True, model
        # else return False, None
        
        data = np.array(data, dtype=np.int64)

        x = data[:, 0]  
        y = data[:, 1]  
        z = data[:, 2]

        return (z == x + y).all(), None

    def checkRelation(self, data):
        # x = np.array([1, data[0]], dtype=np.int64)
        x = data[0]
        y = data[1]
        z = data[2]
        return z == x + y

class LinearRelation(object):

    def __init__(self, x_name, y_name) -> None:
        self.type = "LinearRelation"
        self.x_name = x_name
        self.y_name = y_name
        self.a = 0
        self.b = 0

    def __str__(self):
        # y = a * x + b
        return f"{self.y_name} = {self.a} * {self.x_name} + {self.b}"

    def constructRelation(self, data, threshold=1):
        # if successfully find model, return True, model
        # else return False, None
        data = np.array(data, dtype=np.int64)

        x = data[:, 0]  
        y = data[:, 1]  

        x = sm.add_constant(x)

        model = sm.OLS(y, x).fit()
        self.model = model

        r_squared_value = model.rsquared

        if r_squared_value >= threshold and abs(model.params[1]) > 1e-5 and self.checkRelation([x[0],y[0]]):
            violate = False
            for item in data:
                if not self.checkRelation(item):
                    violate = True
                    break
            if violate or abs((model.params[1] - 1) < 1e-5 and abs(model.params[0]) < 1e-5):
                return False
            else:
                self.a = self.model.params[1]
                self.b = self.model.params[0]
                return True
        else:
            return False

    def checkRelation(self, data):
        # if the data fit the model, return true, else false
        x = data[0]
        y = data[1]
        # predicted_y = self.model.predict(x)

        a = self.a
        b = self.b
        predicted_y = a * x + b
        return (predicted_y - y) < 1e-5
    
    def dumpModel(self):
        return {
            "type": self.type,
            "x_name": self.x_name,
            "y_name": self.y_name,
            "a": self.a,
            "b": self.b
        }
    
    def loadModel(self, modelDict):
        self.type = modelDict["type"]
        self.x_name = modelDict["x_name"]
        self.y_name = modelDict["y_name"]
        self.a = modelDict["a"]
        self.b = modelDict["b"]
        
    
class QuadraticRelation(object):

    def __init__(self, x_name, y_name) -> None:
        self.type = "QuadraticRelation"
        self.x_name = x_name
        self.y_name = y_name
        self.a = 0
        self.b = 0
        self.c = 0

    def __str__(self):
        return f"{self.y_name} = {self.a} * {self.x_name}^2 + {self.b} * {self.x_name} + {self.c}"

    def constructRelation(self, data, threshold=1):
        # if successfully find model, return True, model
        # else return False, None
        data = np.array(data, dtype=np.int64)

        x = data[:, 0]  
        y = data[:, 1]  

        x_poly = np.column_stack((x**2, x))

        model = sm.OLS(y, sm.add_constant(x_poly)).fit()
        self.model = model

        r_squared_value = model.rsquared

        if r_squared_value >= threshold and abs(model.params[1]) > 1e-5 and self.checkRelation([x[0],y[0]]):
            violate = False
            for item in data:
                if not self.checkRelation(item):
                    violate = True
                    break
            if violate:
                return False
            else:
                self.a = self.model.params[1]
                self.b = self.model.params[2]
                self.c = self.model.params[0]
                return True
        else:
            return False

    def checkRelation(self, data):
        # if the data fit the model, return true, else false
        assert self.model != None, "none model"
        x = data[0]
        y = data[1]
        
        a = self.a
        b = self.b
        c = self.c
        predicted_y = a * x**2 + b * x + c
        return (predicted_y - y) < 1e-5
    
    def dumpModel(self):
        return {
            "type": self.type,
            "x_name": self.x_name,
            "y_name": self.y_name,
            "a": self.a,
            "b": self.b,
            "c": self.c
        }
    
    def loadModel(self, modelDict):
        self.type = modelDict["type"]
        self.x_name = modelDict["x_name"]
        self.y_name = modelDict["y_name"]
        self.a = modelDict["a"]
        self.b = modelDict["b"]
        self.c = modelDict["c"]

class InverseRelation(object):

    def __init__(self, x_name, y_name) -> None:
        self.type = "InverseRelation"
        self.x_name = x_name
        self.y_name = y_name
        self.k = 0

    def __str__(self):
        assert self.k != 0, "k == 0 in InverseRelation"
        return f"{self.x_name} * {self.y_name} = {self.k}"

    def constructRelation(self, data, threshold=1):

        data_new = []
        for varXY in data:
            varX, varY = 1/varXY[0], varXY[1]
            data_new.append([varX, varY])
        data_new = np.array(data_new, dtype=np.int64)

        x = data_new[:, 0]
        y = data_new[:, 1]

        model = sm.OLS(y, x, hasconst=False).fit()
        self.model = model

        r_squared_value = model.rsquared

        if r_squared_value >= threshold and abs(model.params[0]) > 1e-5:
            violate = False
            for item in data:
                if not self.checkRelation(item):
                    violate = True
                    break
            if violate:
                return False
            else:
                self.k = self.model.params[0]
                return True
        else:
            return False

    def checkRelation(self, data):
        assert self.k != 0
        x = data[0]
        y = data[1]
        k = self.k
        return (x * y - k) < 1e-5
    
    def dumpModel(self):
        return {
            "type": self.type,
            "x_name": self.x_name,
            "y_name": self.y_name,
            "k": self.k,
        }
    
    def loadModel(self, modelDict):
        self.type = modelDict["type"]
        self.x_name = modelDict["x_name"]
        self.y_name = modelDict["y_name"]
        self.k = modelDict["k"]

def loadModel(modelDict):
    if modelDict["type"] == "LinearRelation":
        model = LinearRelation(modelDict["x_name"], modelDict["y_name"])
        model.loadModel(modelDict)
        return model
    elif modelDict["type"] == "QuadraticRelation":
        model = QuadraticRelation(modelDict["x_name"], modelDict["y_name"])
        model.loadModel(modelDict)
        return model
    elif modelDict["type"] == "InverseRelation":
        model = InverseRelation(modelDict["x_name"], modelDict["y_name"])
        model.loadModel(modelDict)
        return model
    return None

    
modelRelationWithTwoVarList = [
    LinearRelation,
    # QuadraticRelation,
    InverseRelation,
]

modelRelationWithThreeVarList = [
    LinearRelationWithThreeVar
]

if __name__ == "__main__":
    data = list()
    data = [
        # [1, 4],
        # [2, 5],
        # [3, 6],
        # [4, 7],
        # [5, 8],
        # [6, 9],
        # [7, 10],
        [10000000, 1231412413]
    ]
    linearRelation = LinearRelation("x", "y")
    flag1, model = linearRelation.constructRelation(data)
    if flag1:
        print(linearRelation)
        print(linearRelation.checkRelation([8, 11]))

    data = [
        [1 , 6],
        [2 , 15],
        [3 , 28],
        [4 , 45],
        [5 , 66],
        [6 , 91],
        [7 , 120],
        [8 , 153],
        [9 , 190],
        [10 , 231]
    ]

    quadraticRelation = QuadraticRelation("x", "y")
    flag2, model = quadraticRelation.constructRelation(data)
    if flag2:
        print(quadraticRelation)
        print(quadraticRelation.checkRelation([11, 276]))

    data = [
        # [1, 2],
        # [1/2, 4],
        # [1/3, 6],
        # [1/4, 8],
        # [1/5, 10],
        # [1/6, 12],
        # [1/7, 14],
        # [1/8, 16],
        # [1/9, 18],
        # [1/10, 20],
        [1, 0]
    ]
    inverseRelation = InverseRelation("x", "y")
    flag3, model3 = inverseRelation.constructRelation(data)
    if flag3:
        print(inverseRelation)
        print(inverseRelation.checkRelation([1/11, 23]))
