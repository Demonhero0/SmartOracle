package trace

import (
	"encoding/json"
	"fmt"
	"io/ioutil"
	"math/big"
	"strconv"
	"strings"

	"github.com/ethereum/go-ethereum/common"
)

type Log struct {
	Address  common.Address `json:"address"`
	Topics   []common.Hash  `json:"topics"`
	Data     []byte         `json:"data"`
	Position uint           `json:"index"`
}

type Transaction struct {
	TxHash      string     `json:"txHash"`
	BlockNumber *big.Int   `json:"blockNumber"`
	Timestamp   uint64     `json:"timestamp"`
	TxIndex     int        `json:"position"`
	InitialGas  uint64     `json:"-"`
	Call        *CallFrame `json:"call"`
}

type CallFrame struct {
	Type         string          `json:"type"`
	From         common.Address  `json:"from"`
	To           *common.Address `json:"to"`
	Value        *big.Int        `json:"value"`
	Input        []byte          `json:"input"`
	Output       []byte          `json:"output"`
	IsContract   bool            `json:"isContract"`
	Gas          uint64          `json:"gas"`
	GasUsed      uint64          `json:"gasUsed"`
	Error        string          `json:"err"`
	RevertReason string          `json:"revertReason,omitempty"`
	Logs         []*Log          `json:"logs"`
	Calls        []*CallFrame    `json:"calls"`

	// for invHunter
	CallLocation     uint64                                         `json:"callLocation"`
	IsState          bool                                           `json:"isState"`
	Create           bool                                           `json:"-"`
	Created          map[common.Address]bool                        `json:"-"`
	Deleted          map[common.Address]bool                        `json:"-"`
	PreState         State                                          `json:"preState,omitempty"`
	PostState        State                                          `json:"postState,omitempty"`
	PreTokenBalance  map[common.Address]map[common.Address]*big.Int `json:"preTokenBalance,omitempty"`
	PostTokenBalance map[common.Address]map[common.Address]*big.Int `json:"postTokenBalance,omitempty"`

	Branch []JumpInfo `json:"branch,omitempty"`
}

type JumpInfo struct {
	Pc          uint64 `json:"pc"`
	Destination uint64 `json:"destination"`
	Cond        bool   `json:"cond"`
}

type State = map[common.Address]*Account

type Account struct {
	Balance *big.Int                    `json:"balance,omitempty"`
	Code    []byte                      `json:"code,omitempty"`
	Nonce   uint64                      `json:"nonce,omitempty"`
	Storage map[common.Hash]common.Hash `json:"storage,omitempty"`
}

func (a *Account) Exists() bool {
	return a.Nonce > 0 || len(a.Code) > 0 || len(a.Storage) > 0 || (a.Balance != nil && a.Balance.Sign() != 0)
}

// func (state *State) Copy() State {
// 	newState := make(State)
// 	for addr := range state {
// 		newState[addr] = &Account{
// 			Balance: new(big.Int).Set(state[addr].Balance),
// 			Nonce:   state[addr].Nonce,
// 			Code:
// 		}
// 	}
// }

func (callFrame *CallFrame) UpdateCallFrame(
	from common.Address,
	to common.Address,
	value *big.Int,
	callType string,
	input []byte,
	gasLimit uint64,
	gas uint64,
	returnData []byte,
	err error,
) {
	callFrame.From = from
	callFrame.To = &to
	callFrame.Value = value
	callFrame.Type = callType
	for _, b := range input {
		callFrame.Input = append(callFrame.Input, b)
	}
	// callFrame.GasLimit = gasLimit
	callFrame.Gas = gas
	callFrame.Output = returnData
	if err != nil {
		callFrame.Error = err.Error()
	} else {
		callFrame.Error = ""
	}
}

func (transaction *Transaction) DumpTree(dumpPath string) {
	b, _ := json.Marshal(*transaction)
	ioutil.WriteFile(dumpPath+"/"+transaction.BlockNumber.String()+"_"+strconv.Itoa(transaction.TxIndex)+".json", b, 0644)
}

func (transaction *Transaction) DumpTreeWithTxHash(dumpPath string) {
	b, _ := json.Marshal(*transaction)
	// fmt.Println("DumpTreeWithTxHash", transaction.TxHash)
	ioutil.WriteFile(dumpPath+"/"+transaction.TxHash+".json", b, 0644)
}

func LoadTx(path string) Transaction {
	file, err := ioutil.ReadFile(path)
	if err != nil {
		fmt.Println("LoadTx error:", err)
	}
	ExTx := Transaction{}
	err = json.Unmarshal([]byte(file), &ExTx)
	if err != nil {
		fmt.Println("Json to struct error:", err)
	}
	return ExTx
}

func (transaction *Transaction) ParseTxTree() {
	fmt.Println(transaction.BlockNumber, transaction.Timestamp, transaction.TxIndex)
	callFrame := transaction.Call
	for _, tx := range callFrame.Calls {
		parseTxTreeUtil(tx, 0)
	}

	for _, event := range callFrame.Logs {
		parseEvent(event, 0)
	}
}

func parseEvent(event *Log, depth int) {
	fmt.Println(strings.Repeat("-", depth+2), depth+1, "event", event.Position)
}

func parseTxTreeUtil(callFrame *CallFrame, depth int) {
	fmt.Println(strings.Repeat("-", depth+1), depth, callFrame.Type, callFrame.To)
	for _, tx := range callFrame.Calls {
		parseTxTreeUtil(tx, depth+1)
	}

	for _, event := range callFrame.Logs {
		parseEvent(event, depth)
	}
}
