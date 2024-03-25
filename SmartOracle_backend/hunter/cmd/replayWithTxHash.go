package cmd

import (
	"fmt"
	"math/big"
	"time"

	"github.com/ethereum/go-ethereum/common"
	"github.com/ethereum/go-ethereum/core"
	"github.com/ethereum/go-ethereum/core/state"
	"github.com/ethereum/go-ethereum/core/types"
	vm "github.com/ethereum/go-ethereum/core/vm"
	tracer "github.com/ethereum/go-ethereum/eth/tracers/txTracer"
	"github.com/ethereum/go-ethereum/params"

	// "gopkg.in/urfave/cli.v1"

	trace "github.com/ethereum/go-ethereum/hunter/trace"
	cli "github.com/urfave/cli/v2"
)

var ReplayWithTxHashCommand = cli.Command{
	Action:    replayWithTxHashAction,
	Name:      "replay-txhash",
	Usage:     "executes a specific transaction for given txhash",
	ArgsUsage: "<txhash> <output_path>",
	Description: `
The replay command requires one argument:
<txhash> <output_path>

<txhash> is the hash of the transaction. <output_path> is the path of output.`,
}

// record-replay: func replayAction for replay command
func replayWithTxHashAction(ctx *cli.Context) error {
	var err error

	txhash := ctx.Args().Get(0)
	dumpPath := ctx.Args().Get(1)

	accountState := trace.InitAccountState()
	accountState.SetRequireRPC(true)
	config := loadConfigJson("hunter/config.json")
	accountState.RPCProvider.SetURL(config.RPC_url)

	txReceipt, err := accountState.RPCProvider.GetTransactionReceipt(common.HexToHash(txhash))
	blockNumber := txReceipt.BlockNumber
	position := txReceipt.TransactionIndex
	block, err := accountState.RPCProvider.GetBlockByNumber(blockNumber)

	msg, blockCtx, txCtx, statedb, chainConfig, err := stateAtTransaction(blockNumber, position, block, accountState)

	if err != nil {
		return err
	}
	fmt.Println("tracing", txhash)
	// init tracer
	tracer := tracer.NewTxTracer()
	tracer.SetAccountState(accountState)
	vmConfig := vm.Config{
		Tracer: tracer,
	}
	evm := vm.NewEVM(blockCtx, txCtx, statedb, chainConfig, vmConfig)
	evm.TraceStateFlag = true

	evm.StateDB.SetAccountState(accountState)

	statedb.SetTxContext(common.HexToHash(txhash), int(position))
	core.ApplyMessageTrace(evm, msg, new(core.GasPool).AddGas(msg.GasLimit))

	transaction := trace.Transaction{
		TxHash:      txhash,
		BlockNumber: blockNumber,
		TxIndex:     int(position),
		Timestamp:   block.Time(),
		Call:        tracer.GetCallFrame(),
	}
	transaction.DumpTreeWithTxHash(dumpPath)
	return err
}

func stateAtTransaction(blockNumber *big.Int, position uint, block *types.Block, accountState *trace.AccountState) (*core.Message, vm.BlockContext, vm.TxContext, *state.StateDB, *params.ChainConfig, error) {
	//Set up Executing Environment
	var (
		chainConfig *params.ChainConfig
		statedb     *state.StateDB
	)

	// chainConfig
	chainConfig = &params.ChainConfig{}
	*chainConfig = *params.MainnetChainConfig
	// disable DAOForkSupport, otherwise account states will be overwritten
	chainConfig.DAOForkSupport = false

	signer := types.MakeSigner(chainConfig, block.Number(), block.Time())
	statedb = newStateDB(block, chainConfig)
	statedb.SetAccountState(accountState)
	statedb.AccountState().CommitAccountState()
	for idx, tx := range block.Transactions() {
		msg, _ := core.TransactionToMessage(tx, signer, block.BaseFee())
		txCtx := core.NewEVMTxContext(msg)
		blockCtx := vm.BlockContext{
			CanTransfer: core.CanTransfer,
			Transfer:    core.Transfer,
			Coinbase:    block.Coinbase(),
			BlockNumber: blockNumber,
			Time:        block.Time(),
			Difficulty:  block.Difficulty(),
			GasLimit:    block.GasLimit(),
			BaseFee:     block.BaseFee(),
			GetHash:     getHashRPCFn(block, accountState),
		}

		if idx == int(position) {
			return msg, blockCtx, txCtx, statedb, chainConfig, nil
		}
		fmt.Println("preparing", blockNumber, idx)
		vmenv := vm.NewEVM(blockCtx, txCtx, statedb, chainConfig, vm.Config{})
		vmenv.TraceStateFlag = true

		statedb.SetTxContext(tx.Hash(), idx)
		if _, err := core.ApplyMessageTrace(vmenv, msg, new(core.GasPool).AddGas(tx.Gas())); err != nil {
			return nil, blockCtx, txCtx, statedb, chainConfig, fmt.Errorf("transaction %#x failed: %v", tx.Hash(), err)
		}
		// Ensure any modifications are committed to the state
		// Only delete empty objects if EIP158/161 (a.k.a Spurious Dragon) is in effect
		statedb.Finalise(vmenv.ChainConfig().IsEIP158(block.Number()))
		vmenv.StateDB.AccountState().CommitAccountState()

		// limit time
		time.Sleep(500 * time.Millisecond)
	}
	return nil, vm.BlockContext{}, vm.TxContext{}, statedb, chainConfig, fmt.Errorf("transaction index %d out of range for block %#x", position, block.Hash())
}
