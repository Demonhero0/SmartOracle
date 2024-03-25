package cmd

import (
	"encoding/json"
	"fmt"
	"math/big"
	"os"

	// cli "gopkg.in/urfave/cli.v1"
	cli "github.com/urfave/cli/v2"

	"github.com/ethereum/go-ethereum/common"
	tracer "github.com/ethereum/go-ethereum/eth/tracers/txTracer"
	"github.com/ethereum/go-ethereum/research"

	inv "github.com/ethereum/go-ethereum/hunter/invariant"
	"github.com/ethereum/go-ethereum/hunter/trace"
)

var outputPath string
var targetAddress string

var ReplayInvCommand = cli.Command{
	Action: replayInvAction,
	Name:   "replay-inv",
	Usage:  "executes full state transitions and check output consistency",
	// ArgsUsage: "<blockNumFirst> <blockNumLast>",
	Flags: []cli.Flag{
		research.WorkersFlag,
	},
	Description: `
The substate-cli replay command requires two arguments:
<blockNumFirst> <blockNumLast>

<blockNumFirst> and <blockNumLast> are the first and
last block of the inclusive range of blocks to replay transactions.`,
}

// record-replay: func replayAction for replay command
func replayInvAction(ctx *cli.Context) error {
	var err error

	filePath := ctx.Args().Get(0)
	targetAddress = ctx.Args().Get(1)
	outputPath = ctx.Args().Get(2)
	substatePath := ctx.Args().Get(3)

	first := 8000000
	last := 15000000
	// filePath := "hunter/trash/blockTxList.json"

	file, err := os.Open(filePath)
	if err != nil {
		fmt.Println("Load RateMap err", err)
	}
	defer file.Close()

	var blockTxList []string
	decoder := json.NewDecoder(file)
	err = decoder.Decode(&blockTxList)
	if err != nil {
		fmt.Println("json decode err", err)
	}

	research.SetSubstatePath(substatePath)
	research.OpenSubstateDBReadOnly()
	defer research.CloseSubstateDB()
	pool := research.NewSubstateTaskPool("substate-cli replay-inv", replayTxListInv, uint64(first), uint64(last), ctx)
	err = pool.ExecuteWithTx(blockTxList)
	// accountState := trace.InitAccountState()
	// sort.Sort(BlockPosition(blockTxList))
	// for _, block_tx := range blockTxList {
	// 	temp_list := strings.Split(block_tx, "_")
	// 	block, _ := strconv.ParseUint(temp_list[0], 10, 64)
	// 	tx, _ := strconv.Atoi(temp_list[1])
	// 	if block <= pool.Last && block >= pool.First {
	// 		substate := pool.DB.GetBlockSubstates(block)[tx]
	// 		// prepare to execution
	// 		transaction, _ := executeMsgInv(block, tx, substate, accountState, common.HexToAddress(targetAddress))
	// 		transaction.DumpTree(dumpPath)
	// 	}
	// }

	return err
}

func replayTxListInv(block uint64, tx int, substate *research.Substate, taskPool *research.SubstateTaskPool) error {
	inputAlloc := substate.InputAlloc
	inputEnv := substate.Env
	inputMessage := substate.Message

	var (
		err     error
		statedb = MakeOffTheChainStateDB(inputAlloc, block)
	)

	msg := inputMessage.AsMessage()
	// accountState := trace.InitAccountState()
	// statedb.SetAccountState(accountState)

	// init tracer
	tracer := tracer.NewTxTracer()
	// tracer.SetAccountState(accountState)
	tracer.SetIsRecordState()
	tracer.AddTargetAddress(common.HexToAddress(targetAddress))

	_, err = executeMsg(&msg, *inputEnv, statedb, tracer, false)
	transaction := &trace.Transaction{
		BlockNumber: new(big.Int).SetUint64(inputEnv.Number),
		TxIndex:     tx,
		Timestamp:   inputEnv.Timestamp,
		Call:        tracer.GetCallFrame(),
	}
	// extract erc20 token
	tokenHandler := inv.InitTokenHandler(&msg)
	tokenHandler.ParseTxTree(transaction.Call)
	getBalanceTree(transaction.Call, tokenHandler, *inputEnv, common.HexToAddress(targetAddress))

	transaction.DumpTree(outputPath)

	return err
}

// func executeMsgInv(block uint64, tx int, substate *research.Substate, accountState *trace.AccountState, targetAddress common.Address) (*trace.Transaction, error) {
// fmt.Println(block, tx)
// inputAlloc := substate.InputAlloc
// inputEnv := substate.Env
// inputMessage := substate.Message

// var (
// 	err     error
// 	statedb = MakeOffTheChainStateDB(inputAlloc, block)
// )

// msg := inputMessage.AsMessage()
// statedb.SetAccountState(accountState)

// // init tracer
// tracer := tracer.NewTxTracer()
// tracer.SetAccountState(accountState)
// tracer.SetIsRecordState()
// tracer.AddTargetAddress(targetAddress)

// _, err = executeMsg(&msg, *inputEnv, statedb, tracer, true)
// transaction := &trace.Transaction{
// 	BlockNumber: new(big.Int).SetUint64(inputEnv.Number),
// 	TxIndex:     tx,
// 	Timestamp:   inputEnv.Timestamp,
// 	Call:        tracer.GetCallFrame(),
// }

// // extract erc20 token
// tokenHandler := inv.InitTokenHandler(&msg)
// tokenHandler.ParseTxTree(transaction.Call)
// getBalanceTree(transaction.Call, tokenHandler, *inputEnv)

// return transaction, err
// }
