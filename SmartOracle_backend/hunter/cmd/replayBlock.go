package cmd

import (
	"fmt"
	"math/big"
	"strconv"
	"time"

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

var ReplayBlockhCommand = cli.Command{
	Action:    replayBlockAction,
	Name:      "replay-block",
	Usage:     "executes a specific block for given number",
	ArgsUsage: "<block> <tx_num> <output_path>",
	Description: `
The replay command requires three argument:
<block> <tx_num> <output_path>

<block> is the block number. <tx_num> is the end of the position of the transaction. <output_path> is the path of output. This function will return the whole transaction of the block.`,
}

// record-replay: func replayAction for replay command
func replayBlockAction(ctx *cli.Context) error {
	var err error

	accountState := trace.InitAccountState()
	accountState.SetRequireRPC(true)

	config := loadConfigJson("hunter/config.json")
	accountState.RPCProvider.SetURL(config.RPC_url)

	number := ctx.Args().Get(0)
	endPosition, _ := strconv.Atoi(ctx.Args().Get(1))
	dumpPath := ctx.Args().Get(2)
	blockNumber, _ := new(big.Int).SetString(number, 10)
	block, err := accountState.RPCProvider.GetBlockByNumber(blockNumber)

	var blockTransactionList []*trace.Transaction
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
		fmt.Println("tracing", number, idx)
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

		tracer := tracer.NewTxTracer()
		tracer.SetAccountState(accountState)
		vmConfig := vm.Config{
			Tracer: tracer,
		}
		vmenv := vm.NewEVM(blockCtx, txCtx, statedb, chainConfig, vmConfig)
		vmenv.TraceStateFlag = true

		statedb.SetTxContext(tx.Hash(), idx)
		if _, err := core.ApplyMessageTrace(vmenv, msg, new(core.GasPool).AddGas(tx.Gas())); err != nil {
			return fmt.Errorf("transaction %#x failed: %v", tx.Hash(), err)
		}
		// Ensure any modifications are committed to the state
		// Only delete empty objects if EIP158/161 (a.k.a Spurious Dragon) is in effect
		statedb.Finalise(vmenv.ChainConfig().IsEIP158(block.Number()))
		vmenv.StateDB.AccountState().CommitAccountState()

		transaction := trace.Transaction{
			TxHash:      tx.Hash().String(),
			BlockNumber: blockNumber,
			TxIndex:     idx,
			Timestamp:   block.Time(),
			Call:        tracer.GetCallFrame(),
		}
		blockTransactionList = append(blockTransactionList, &transaction)

		// limit time
		time.Sleep(200 * time.Millisecond)

		if idx == endPosition {
			break
		}
	}

	// accountState.DumpAccountStateSnapshot("hunter/temp/testAccountState.json")
	for _, tx := range blockTransactionList {
		tx.DumpTree(dumpPath)
	}
	return err
}

// tracing 10954405 126
