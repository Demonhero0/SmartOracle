package cmd

import (
	"encoding/hex"
	"encoding/json"
	"fmt"
	"math/big"
	"os"

	"github.com/ethereum/go-ethereum/common"
	"github.com/ethereum/go-ethereum/core"
	"github.com/ethereum/go-ethereum/core/rawdb"
	"github.com/ethereum/go-ethereum/core/state"
	"github.com/ethereum/go-ethereum/core/types"
	vm "github.com/ethereum/go-ethereum/core/vm"
	tracer "github.com/ethereum/go-ethereum/eth/tracers/txTracer"
	inv "github.com/ethereum/go-ethereum/hunter/invariant"
	"github.com/ethereum/go-ethereum/hunter/trace"
	"github.com/ethereum/go-ethereum/params"
	"github.com/ethereum/go-ethereum/research"
)

func newStateDB(block *types.Block, chainConfig *params.ChainConfig) *state.StateDB {
	db := rawdb.NewMemoryDatabase()
	statedb, err := state.New(common.Hash{}, state.NewDatabase(db), nil)
	if err != nil {
		fmt.Println(err)
	}

	_, err = statedb.Commit(block.NumberU64(), chainConfig.IsEIP158(block.Number()))
	if err != nil {
		panic(fmt.Errorf("error calling statedb.Commit() in MakeOffTheChainStateDB(): %v", err))
	}
	return statedb
}

func getHashRPCFn(block *types.Block, accountState *trace.AccountState) func(num uint64) common.Hash {

	return func(num uint64) common.Hash {
		var h common.Hash
		if num == block.NumberU64() {
			h = block.Hash()
		} else {
			header, _ := accountState.RPCProvider.GetHeaderByNumber(big.NewInt(int64(num)))
			h = header.Hash()
		}
		return h
	}
}

func NewOffTheChainStateDB() *state.StateDB {
	db := rawdb.NewMemoryDatabase()
	state, _ := state.New(common.Hash{}, state.NewDatabase(db), nil)
	return state
}

// MakeOffTheChainStateDB returns an in-memory *state.StateDB initialized with alloc
func MakeOffTheChainStateDB(alloc research.SubstateAlloc, blockNumber uint64) *state.StateDB {
	statedb := NewOffTheChainStateDB()
	for addr, a := range alloc {
		statedb.SetCode(addr, a.Code)
		statedb.SetNonce(addr, a.Nonce)
		statedb.SetBalance(addr, a.Balance)
		// DON'T USE SetStorage because it makes REVERT and dirtyStorage unavailble
		for k, v := range a.Storage {
			statedb.SetState(addr, k, v)
		}
	}
	// Commit and re-open to start with a clean state.
	_, err := statedb.Commit(blockNumber, false)
	if err != nil {
		panic(fmt.Errorf("error calling statedb.Commit() in MakeOffTheChainStateDB(): %v", err))
	}
	return statedb
}

func MakeOffTheChainStateDBWithAccountState(state trace.State, blockNumber uint64) *state.StateDB {
	statedb := NewOffTheChainStateDB()
	for addr, a := range state {
		statedb.SetCode(addr, a.Code)
		statedb.SetNonce(addr, a.Nonce)
		statedb.SetBalance(addr, a.Balance)
		// DON'T USE SetStorage because it makes REVERT and dirtyStorage unavailble
		for k, v := range a.Storage {
			statedb.SetState(addr, k, v)
		}
	}
	// Commit and re-open to start with a clean state.
	_, err := statedb.Commit(blockNumber, false)
	if err != nil {
		panic(fmt.Errorf("error calling statedb.Commit() in MakeOffTheChainStateDB(): %v", err))
	}
	return statedb
}

type Config struct {
	RPC_url string
}

func loadConfigJson(path string) *Config {
	file, _ := os.Open(path)
	defer file.Close()
	decoder := json.NewDecoder(file)
	conf := Config{}
	err := decoder.Decode(&conf)
	if err != nil {
		fmt.Println("loadConfigJson Error:", err)
	}
	return &conf
}

func executeMsg(message *core.Message, inputEnv research.SubstateEnv, statedb *state.StateDB, tracer *tracer.TxTracer, traceFlag bool) (res *core.ExecutionResult, err error) {
	//Set up Executing Environment
	var (
		vmConfig    vm.Config
		chainConfig *params.ChainConfig
	)
	vmConfig = vm.Config{}
	chainConfig = &params.ChainConfig{}
	*chainConfig = *params.MainnetChainConfig
	// disable DAOForkSupport, otherwise account states will be overwritten
	chainConfig.DAOForkSupport = false

	var hashError error
	getHash := func(num uint64) common.Hash {
		if inputEnv.BlockHashes == nil {
			hashError = fmt.Errorf("getHash(%d) invoked, no blockhashes provided", num)
			return common.Hash{}
		}
		h, ok := inputEnv.BlockHashes[num]
		if !ok {
			hashError = fmt.Errorf("getHash(%d) invoked, blockhash for that block not provided", num)
		}
		return h
	}

	// Apply Message
	var (
		gaspool = new(core.GasPool)
	)
	gaspool.AddGas(inputEnv.GasLimit)
	blockCtx := vm.BlockContext{
		CanTransfer: core.CanTransfer,
		Transfer:    core.Transfer,
		Coinbase:    inputEnv.Coinbase,
		BlockNumber: new(big.Int).SetUint64(inputEnv.Number),
		Time:        inputEnv.Timestamp,
		Difficulty:  inputEnv.Difficulty,
		GasLimit:    inputEnv.GasLimit,
		GetHash:     getHash,
	}
	// If currentBaseFee is defined, add it to the vmContext.
	if inputEnv.BaseFee != nil {
		blockCtx.BaseFee = new(big.Int).Set(inputEnv.BaseFee)
	}

	txCtx := vm.TxContext{
		GasPrice: message.GasPrice,
		Origin:   message.From,
	}

	if tracer == nil && !traceFlag {
		evm := vm.NewEVM(blockCtx, txCtx, statedb, chainConfig, vmConfig)
		res, err = core.ApplyMessage(evm, message, gaspool)
	} else {
		vmConfig.Tracer = tracer
		evm := vm.NewEVM(blockCtx, txCtx, statedb, chainConfig, vmConfig)
		evm.TraceStateFlag = traceFlag
		res, err = core.ApplyMessageTrace(evm, message, gaspool)
	}

	if hashError != nil {
		return res, hashError
	}

	return res, err
}

func getBalance(tokenHandler *inv.TokenHandler, statedb *state.StateDB, inputEnv research.SubstateEnv) map[common.Address]map[common.Address]*big.Int {
	tokenUserBalance := make(map[common.Address]map[common.Address]*big.Int)
	SomeEther, _ := new(big.Int).SetString("1000000000000000000000", 10)
	statedb.AddBalance(common.HexToAddress("0x1"), SomeEther)
	// fmt.Println("Ether balance", statedb.GetBalance(common.HexToAddress("0x1")))
	for token := range tokenHandler.RelatedToken {
		tokenUserBalance[token] = make(map[common.Address]*big.Int)
		for addr := range tokenHandler.RelatedAddress {
			msgBalance := tokenHandler.BalanceMsg(token, addr)
			res, err := executeMsg(&msgBalance, inputEnv, statedb, nil, false)
			if err == nil {
				amount, flag := new(big.Int).SetString(hex.EncodeToString(res.ReturnData), 16)
				// fmt.Println(token, addr, amount)
				if flag {
					tokenUserBalance[token][addr] = amount
				}
			} else {
				fmt.Println(err)
				os.Exit(100)
			}
		}
	}
	// fmt.Println("Ether balance", statedb.GetBalance(common.HexToAddress("0x1")))
	return tokenUserBalance
}

func getBalanceTree(call *trace.CallFrame, tokenHandler *inv.TokenHandler, inputEnv research.SubstateEnv, targetAddress common.Address) {

	if call.IsState {
		preStateDB := MakeOffTheChainStateDBWithAccountState(call.PreState, uint64(1))
		postStateDB := MakeOffTheChainStateDBWithAccountState(call.PostState, uint64(1))
		call.PreTokenBalance = getBalance(tokenHandler, preStateDB, inputEnv)
		call.PostTokenBalance = getBalance(tokenHandler, postStateDB, inputEnv)

		// record eth balance in tokenBalance
		recordEth(call.PreState, call.PreTokenBalance)
		recordEth(call.PostState, call.PostTokenBalance)
		removeUnrelatedState(call.PreState, targetAddress)
		removeUnrelatedState(call.PostState, targetAddress)
	}

	for _, inCall := range call.Calls {
		getBalanceTree(inCall, tokenHandler, inputEnv, targetAddress)
	}
}

func recordEth(state trace.State, tokenBalance map[common.Address]map[common.Address]*big.Int) {
	ethToken := common.HexToAddress("0x0")
	tokenBalance[ethToken] = make(map[common.Address]*big.Int)
	for addr := range state {
		tokenBalance[ethToken][addr] = new(big.Int).Set(state[addr].Balance)
	}
}

func removeUnrelatedState(state trace.State, targetAddress common.Address) {
	for addr := range state {
		if addr != targetAddress {
			delete(state, addr)
		} else {
			state[addr].Code = []byte{}
			state[addr].Nonce = 0
			state[addr].Balance = nil
		}
	}
}
