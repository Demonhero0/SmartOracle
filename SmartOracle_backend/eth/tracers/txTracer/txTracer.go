package tracer

import (
	"errors"
	"math/big"

	"github.com/ethereum/go-ethereum/accounts/abi"
	"github.com/ethereum/go-ethereum/common"
	"github.com/ethereum/go-ethereum/common/hexutil"
	"github.com/ethereum/go-ethereum/core/vm"
	"github.com/ethereum/go-ethereum/crypto"
	"github.com/ethereum/go-ethereum/eth/tracers"
	"github.com/ethereum/go-ethereum/log"

	trace "github.com/ethereum/go-ethereum/hunter/trace"
)

type TxTracer struct {
	accountState *trace.AccountState
	callstack    []*trace.CallFrame
	gasLimit     uint64

	// record account state
	isRecordState   bool
	targetAddress   map[common.Address]bool
	env             *vm.EVM
	statedCall      []*trace.CallFrame
	tmpCallLocation uint64
}

func NewTxTracer() *TxTracer {
	return &TxTracer{
		callstack:     make([]*trace.CallFrame, 1),
		targetAddress: make(map[common.Address]bool),
	}
}

func (t *TxTracer) SetIsRecordState() {
	t.isRecordState = true
}

func (t *TxTracer) SetAccountState(a *trace.AccountState) {
	t.accountState = a
}

func (t *TxTracer) GetCallFrame() *trace.CallFrame {
	return t.callstack[0]
}

func (t *TxTracer) AddTargetAddress(addr common.Address) {
	t.targetAddress[addr] = true
}

// CaptureStart implements the EVMLogger interface to initialize the tracing operation.
func (t *TxTracer) CaptureStart(env *vm.EVM, from common.Address, to common.Address, create bool, input []byte, gas uint64, value *big.Int) {
	toCopy := to
	t.callstack[0] = &trace.CallFrame{
		Type:       vm.CALL.String(),
		From:       from,
		To:         &toCopy,
		IsContract: len(env.StateDB.GetCode(to)) > 0,
		Input:      common.CopyBytes(input),
		Gas:        t.gasLimit,
		Value:      value,
	}
	if create {
		t.callstack[0].Type = vm.CREATE.String()
	}

	// record state
	t.env = env
	if t.isRecordState && t.targetAddress[to] {
		call := t.callstack[0]
		call.IsState = true
		call.PreState = trace.State{}
		call.PostState = trace.State{}
		call.Created = make(map[common.Address]bool)
		call.Deleted = make(map[common.Address]bool)

		t.statedCall = append(t.statedCall, call)
		call.Create = create
		t.lookupAccount(call, from)
		t.lookupAccount(call, to)
		// t.lookupAccount(call, env.Context.Coinbase)

		// ignore gas consumption
		// The recipient balance includes the value transferred.
		toBal := new(big.Int).Sub(call.PreState[to].Balance, value)
		call.PreState[to].Balance = toBal

		// The sender balance is after reducing: value and gasLimit.
		// We need to re-add them to get the pre-tx balance.
		fromBal := new(big.Int).Set(call.PreState[from].Balance)
		// gasPrice := env.TxContext.GasPrice
		// consumedGas := new(big.Int).Mul(gasPrice, new(big.Int).SetUint64(t.gasLimit))
		// fromBal.Add(fromBal, new(big.Int).Add(value, consumedGas))
		fromBal.Add(fromBal, value)
		call.PreState[from].Balance = fromBal
		call.PreState[from].Nonce--

		if create {
			call.Created[to] = true
		}
	}
}

// CaptureEnd is called after the call finishes to finalize the tracing.
func (t *TxTracer) CaptureEnd(output []byte, gasUsed uint64, err error) {
	processOutput(t.callstack[0], output, err)

	// record state
	if t.isRecordState && t.callstack[0].IsState {
		t.handleCallEnd(t.callstack[0])
		t.statedCall = t.statedCall[:len(t.statedCall)-1]
	}
}

// CaptureState implements the EVMLogger interface to trace a single step of VM execution.
func (t *TxTracer) CaptureState(pc uint64, op vm.OpCode, gas, cost uint64, scope *vm.ScopeContext, rData []byte, depth int, err error) {
	// skip if the previous op caused an error
	if err != nil {
		return
	}

	// recording log
	switch op {
	case vm.LOG0, vm.LOG1, vm.LOG2, vm.LOG3, vm.LOG4:
		size := int(op - vm.LOG0)

		stack := scope.Stack
		stackData := stack.Data()

		// Don't modify the stack
		mStart := stackData[len(stackData)-1]
		mSize := stackData[len(stackData)-2]
		topics := make([]common.Hash, size)
		for i := 0; i < size; i++ {
			topic := stackData[len(stackData)-2-(i+1)]
			topics[i] = common.Hash(topic.Bytes32())
		}

		data, err := tracers.GetMemoryCopyPadded(scope.Memory, int64(mStart.Uint64()), int64(mSize.Uint64()))
		if err != nil {
			// mSize was unrealistically large
			log.Warn("failed to copy CREATE2 input", "err", err, "tracer", "callTracer", "offset", mStart, "size", mSize)
			return
		}

		log := trace.Log{
			Address:  scope.Contract.Address(),
			Topics:   topics,
			Data:     hexutil.Bytes(data),
			Position: uint(len(t.callstack[len(t.callstack)-1].Calls)),
		}
		t.callstack[len(t.callstack)-1].Logs = append(t.callstack[len(t.callstack)-1].Logs, &log)
	}

	// recording state
	for _, call := range t.statedCall {
		stack := scope.Stack
		stackData := stack.Data()
		stackLen := len(stackData)
		caller := scope.Contract.Address()
		switch {
		case stackLen >= 1 && (op == vm.SLOAD || op == vm.SSTORE):
			slot := common.Hash(stackData[stackLen-1].Bytes32())
			t.lookupStorage(call, caller, slot)
		case stackLen >= 1 && (op == vm.EXTCODECOPY || op == vm.EXTCODEHASH || op == vm.EXTCODESIZE || op == vm.BALANCE || op == vm.SELFDESTRUCT):
			addr := common.Address(stackData[stackLen-1].Bytes20())
			t.lookupAccount(call, addr)
			if op == vm.SELFDESTRUCT {
				call.Deleted[caller] = true
			}
		case stackLen >= 5 && (op == vm.DELEGATECALL || op == vm.CALL || op == vm.STATICCALL || op == vm.CALLCODE):
			addr := common.Address(stackData[stackLen-2].Bytes20())
			t.lookupAccount(call, addr)
			t.tmpCallLocation = pc
		case op == vm.CREATE:
			nonce := t.env.StateDB.GetNonce(caller)
			addr := crypto.CreateAddress(caller, nonce)
			t.lookupAccount(call, addr)
			call.Created[addr] = true
		case stackLen >= 4 && op == vm.CREATE2:
			offset := stackData[stackLen-2]
			size := stackData[stackLen-3]
			init, err := tracers.GetMemoryCopyPadded(scope.Memory, int64(offset.Uint64()), int64(size.Uint64()))
			if err != nil {
				log.Warn("failed to copy CREATE2 input", "err", err, "tracer", "prestateTracer", "offset", offset, "size", size)
				return
			}
			inithash := crypto.Keccak256(init)
			salt := stackData[stackLen-4]
			addr := crypto.CreateAddress2(caller, salt.Bytes32(), inithash)
			t.lookupAccount(call, addr)
			call.Created[addr] = true
		case stackLen >= 2 && op == vm.JUMPI && t.targetAddress[scope.Contract.Address()]:
			pos, cond := *scope.Stack.Back(0), *scope.Stack.Back(1)
			destination := pc + 1
			if !cond.IsZero() {
				destination = pos.Uint64()
			}
			call.Branch = append(call.Branch, trace.JumpInfo{
				Pc:          pc,
				Destination: destination,
				Cond:        !cond.IsZero(),
			})
		}
	}
}

// CaptureEnter is called when EVM enters a new scope (via call, create or selfdestruct).
func (t *TxTracer) CaptureEnter(typ vm.OpCode, from common.Address, to common.Address, input []byte, gas uint64, value *big.Int) {
	toCopy := to
	call := trace.CallFrame{
		Type:       typ.String(),
		From:       from,
		To:         &toCopy,
		IsContract: len(t.env.StateDB.GetCode(to)) > 0,
		Input:      common.CopyBytes(input),
		Gas:        gas,
		Value:      value,
	}

	t.callstack = append(t.callstack, &call)

	// record state
	size := len(t.callstack)
	if size <= 1 {
		return
	}
	call.CallLocation = t.tmpCallLocation
	// call targetAddrss
	flag1 := t.targetAddress[to]
	// targetAddress calls to others
	flag2 := len(t.statedCall) > 0 && t.targetAddress[call.From]
	if t.isRecordState && typ == vm.CALL && (flag1 || flag2) {
		call.IsState = true
		call.PreState = trace.State{}
		call.PostState = trace.State{}
		call.Created = make(map[common.Address]bool)
		call.Deleted = make(map[common.Address]bool)

		call.Create = typ == vm.CREATE || typ == vm.CREATE2
		t.lookupAccount(&call, from)
		t.lookupAccount(&call, to)
		if flag2 {
			parentCall := t.statedCall[len(t.statedCall)-1]
			for addr := range parentCall.PreState {
				if addr != from && addr != to {
					t.lookupAccount(&call, addr)
				}
			}
		}

		// The recipient balance includes the value transferred.
		toBal := new(big.Int).Sub(call.PreState[to].Balance, value)
		call.PreState[to].Balance = toBal

		// The sender balance is after reducing: value and gasLimit.
		// We need to re-add them to get the pre-tx balance.
		fromBal := new(big.Int).Set(call.PreState[from].Balance)
		fromBal.Add(fromBal, value)
		call.PreState[from].Balance = fromBal

		if call.Create {
			call.Created[to] = true
		}

		t.statedCall = append(t.statedCall, &call)
	}
}

// CaptureExit is called when EVM exits a scope, even if the scope didn't
// execute any code.
func (t *TxTracer) CaptureExit(output []byte, gasUsed uint64, err error) {
	size := len(t.callstack)
	if size <= 1 {
		return
	}
	// pop call
	call := t.callstack[size-1]
	t.callstack = t.callstack[:size-1]
	size -= 1

	call.GasUsed = gasUsed
	processOutput(call, output, err)
	t.callstack[size-1].Calls = append(t.callstack[size-1].Calls, call)

	// record state
	if t.isRecordState && call.IsState {
		t.handleCallEnd(call)
		t.statedCall = t.statedCall[:len(t.statedCall)-1]
	}
}

// CaptureFault implements the EVMLogger interface to trace an execution fault.
func (t *TxTracer) CaptureFault(pc uint64, op vm.OpCode, gas, cost uint64, scope *vm.ScopeContext, depth int, err error) {
}

func (t *TxTracer) CaptureTxStart(gasLimit uint64) {
	t.gasLimit = gasLimit
}

func (t *TxTracer) CaptureTxEnd(restGas uint64) {
	t.callstack[0].GasUsed = t.gasLimit - restGas
}

func processOutput(f *trace.CallFrame, output []byte, err error) {
	if err == nil {
		f.Output = output
		return
	}
	f.Error = err.Error()
	if f.Type == "CREATE" || f.Type == "CREATE2" {
		f.To = nil
	}
	if !errors.Is(err, errors.New("execution reverted")) || len(output) == 0 {
		return
	}
	f.Output = output
	if len(output) < 4 {
		return
	}
	if unpacked, err := abi.UnpackRevert(output); err == nil {
		f.RevertReason = unpacked
	}
}

func failed(f *trace.CallFrame) bool {
	return len(f.Error) > 0
}

// clearFailedLogs clears the logs of a callframe and all its children
// in case of execution failure.
func clearFailedLogs(cf *trace.CallFrame, parentFailed bool) {
	failed := failed(cf) || parentFailed
	// Clear own logs
	if failed {
		cf.Logs = nil
	}
	for i := range cf.Calls {
		clearFailedLogs(cf.Calls[i], failed)
	}
}

// lookupAccount fetches details of an account and adds it to the prestate
// if it doesn't exist there.
func (t *TxTracer) lookupAccount(call *trace.CallFrame, addr common.Address) {
	if _, ok := call.PreState[addr]; ok {
		return
	}

	call.PreState[addr] = &trace.Account{
		Balance: t.env.StateDB.GetBalance(addr),
		Nonce:   t.env.StateDB.GetNonce(addr),
		Code:    t.env.StateDB.GetCode(addr),
		Storage: make(map[common.Hash]common.Hash),
	}
}

// lookupStorage fetches the requested storage slot and adds
// it to the prestate of the given contract. It assumes `lookupAccount`
// has been performed on the contract before.
func (t *TxTracer) lookupStorage(call *trace.CallFrame, addr common.Address, key common.Hash) {
	if _, ok := call.PreState[addr].Storage[key]; ok {
		return
	}
	call.PreState[addr].Storage[key] = t.env.StateDB.GetState(addr, key)
}

func (t *TxTracer) handleCallEnd(call *trace.CallFrame) {
	for addr, state := range call.PreState {
		// The deleted account's state is pruned from `post` but kept in `pre`
		if _, ok := call.Deleted[addr]; ok {
			continue
		}
		postAccount := &trace.Account{Storage: make(map[common.Hash]common.Hash)}
		newBalance := t.env.StateDB.GetBalance(addr)
		newNonce := t.env.StateDB.GetNonce(addr)
		newCode := t.env.StateDB.GetCode(addr)

		postAccount.Balance = newBalance
		postAccount.Nonce = newNonce
		postAccount.Code = newCode

		for key := range state.Storage {
			newVal := t.env.StateDB.GetState(addr, key)
			postAccount.Storage[key] = newVal
		}

		call.PostState[addr] = postAccount
	}
	// the new created contracts' prestate were empty, so delete them
	for a := range call.Created {
		// the created contract maybe exists in statedb before the creating tx
		if s := call.PreState[a]; s != nil && !s.Exists() {
			delete(call.PreState, a)
		}
	}
}
