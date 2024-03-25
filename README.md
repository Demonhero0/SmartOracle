# SmartOracle
The artifcat of SmartOracle, including code and partial data.

There are two parts of the code:

* "SmartOracle_backend" to execute transactions and extract execution traces.
* "SmartOracle" to parse traces, mine invariants and check invariants.

## SmartOracle_backend

### Usage
Before using this, please prepare the substate according to https://github.com/verovm/usenix-atc21. After that, using the following cammand to extract execution traces. (In the path of "SmartOracle_backend")

```
go run hunter/main.go replay-inv {path of blockTxList.json} {proxy_addr} {dumpPath} {path of substate}
```
example for blockTxList.json
```
["11751666_213", "13465049_404", "11751776_29", "11657574_80"]
```

## SmartOracle

### Setup

Setting environment of python3.8.
```
pip install -r requirements.txt
```

### Usage

After extracting execution traces, we can further mine invariants. Since the execution traces take too much storage space, we only provide the example "20211221_visor_finance" for demo. (In the path of "SmartOracle")

```
python main.py --dapp 20211221_visor_finance 
```