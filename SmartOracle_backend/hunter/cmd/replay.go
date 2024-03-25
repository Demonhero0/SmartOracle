package cmd

import (
	"encoding/json"
	"fmt"
	"math/big"
	"os"
	"sort"
	"strconv"
	"strings"

	tracer "github.com/ethereum/go-ethereum/eth/tracers/txTracer"

	// "gopkg.in/urfave/cli.v1"
	cli "github.com/urfave/cli/v2"

	"github.com/ethereum/go-ethereum/research"

	"github.com/ethereum/go-ethereum/hunter/trace"
)

var ReplayCommand = cli.Command{
	Action: replayAction,
	Name:   "replay",
	Usage:  "executes full state transitions and check output consistency",
	// ArgsUsage: "<blockNumFirst> <blockNumLast>",
	Description: `
The substate-cli replay command requires two arguments:
<blockNumFirst> <blockNumLast>

<blockNumFirst> and <blockNumLast> are the first and
last block of the inclusive range of blocks to replay transactions.`,
}

type BlockPosition []string

func (s BlockPosition) Len() int {
	return len(s)
}

func (s BlockPosition) Swap(i, j int) {
	s[i], s[j] = s[j], s[i]
}

func (s BlockPosition) Less(i, j int) bool {
	block_i, _ := strconv.ParseUint(strings.Split(s[i], "_")[0], 10, 64)
	position_i, _ := strconv.Atoi(strings.Split(s[i], "_")[1])
	block_j, _ := strconv.ParseUint(strings.Split(s[j], "_")[0], 10, 64)
	position_j, _ := strconv.Atoi(strings.Split(s[j], "_")[1])
	if block_i < block_j {
		return true
	} else if block_i == block_j {
		return position_i < position_j
	} else {
		return false
	}
}

// record-replay: func replayAction for replay command
func replayAction(ctx *cli.Context) error {
	var err error

	// if len(ctx.Args()) != 2 {
	// 	return fmt.Errorf("substate-cli replay command requires exactly 2 arguments")
	// }

	// first, ferr := strconv.ParseInt(ctx.Args().Get(0), 10, 64)
	// last, lerr := strconv.ParseInt(ctx.Args().Get(1), 10, 64)
	// if ferr != nil || lerr != nil {
	// 	return fmt.Errorf("substate-cli replay: error in parsing parameters: block number not an integer")
	// }
	// if first < 0 || last < 0 {
	// 	return fmt.Errorf("substate-cli replay: error: block number must be greater than 0")
	// }
	// if first > last {
	// 	return fmt.Errorf("substate-cli replay: error: first block has larger number than last block")
	// }
	filePath := ctx.Args().Get(0)

	first := 14000000
	last := 15000000
	// filePath := "hunter/trash/blockTxList.json"

	outputPath := "hunter/outputTxs"
	os.Mkdir(outputPath, os.ModePerm)
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

	research.OpenSubstateDBReadOnly()
	defer research.CloseSubstateDB()
	pool := research.NewSubstateTaskPool("substate-cli replay-txs", replayTxList, uint64(first), uint64(last), ctx)

	accountState := trace.InitAccountState()
	sort.Sort(BlockPosition(blockTxList))
	for _, block_tx := range blockTxList {
		temp_list := strings.Split(block_tx, "_")
		block, _ := strconv.ParseUint(temp_list[0], 10, 64)
		tx, _ := strconv.Atoi(temp_list[1])
		if block <= pool.Last && block >= pool.First {
			substate := pool.DB.GetBlockSubstates(block)[tx]
			// prepare to execution
			rawTxTree, _ := executeRegularMsgsTx(block, tx, substate, accountState)
			rawTxTree.DumpTree("hunter/output_replay")
		}
	}
	// accountState.DumpAccountStateSnapshot("hunter/temp/testAccountState_true.json")
	// accountState.CommitedAccountState.DumpAccountStateSnapshot("hunter/testCommittedAccountState_true.json")

	return err
}

func replayTxList(block uint64, tx int, substate *research.Substate, taskPool *research.SubstateTaskPool) error {
	return nil
}

func executeRegularMsgsTx(block uint64, tx int, substate *research.Substate, accountState *trace.AccountState) (*trace.Transaction, error) {

	fmt.Println(block, tx)
	inputAlloc := substate.InputAlloc
	inputEnv := substate.Env
	inputMessage := substate.Message

	var (
		err     error
		statedb = MakeOffTheChainStateDB(inputAlloc, block)
	)

	msg := inputMessage.AsMessage()
	statedb.SetAccountState(accountState)

	// init tracer
	tracer := tracer.NewTxTracer()
	tracer.SetAccountState(accountState)

	_, err = executeMsg(&msg, *inputEnv, statedb, tracer, true)
	transaction := &trace.Transaction{
		BlockNumber: new(big.Int).SetUint64(inputEnv.Number),
		TxIndex:     tx,
		Timestamp:   inputEnv.Timestamp,
		Call:        tracer.GetCallFrame(),
	}

	return transaction, err
}
