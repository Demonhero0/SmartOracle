// Copyright 2014 The go-ethereum Authors
// This file is part of the go-ethereum library.
//
// The go-ethereum library is free software: you can redistribute it and/or modify
// it under the terms of the GNU Lesser General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// The go-ethereum library is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
// GNU Lesser General Public License for more details.
//
// You should have received a copy of the GNU Lesser General Public License
// along with the go-ethereum library. If not, see <http://www.gnu.org/licenses/>.

package vm

import (
	"github.com/ethereum/go-ethereum/common"
	"github.com/ethereum/go-ethereum/common/math"
	"github.com/ethereum/go-ethereum/crypto"
	"github.com/ethereum/go-ethereum/log"
)

// Config are the configuration options for the Interpreter
type Config struct {
	Tracer                  EVMLogger // Opcode logger
	NoBaseFee               bool      // Forces the EIP-1559 baseFee to 0 (needed for 0 price calls)
	EnablePreimageRecording bool      // Enables recording of SHA3/keccak preimages
	ExtraEips               []int     // Additional EIPS that are to be enabled
}

// ScopeContext contains the things that are per-call, such as stack and memory,
// but not transients like pc and gas
type ScopeContext struct {
	Memory   *Memory
	Stack    *Stack
	Contract *Contract
}

// EVMInterpreter represents an EVM interpreter
type EVMInterpreter struct {
	evm   *EVM
	table *JumpTable

	hasher    crypto.KeccakState // Keccak256 hasher instance shared across opcodes
	hasherBuf common.Hash        // Keccak256 hasher result array shared across opcodes

	readOnly   bool   // Whether to throw on stateful modifications
	returnData []byte // Last CALL's return data for subsequent reuse
}

// NewEVMInterpreter returns a new instance of the Interpreter.
func NewEVMInterpreter(evm *EVM) *EVMInterpreter {
	// If jump table was not initialised we set the default one.
	var table *JumpTable
	switch {
	case evm.chainRules.IsCancun:
		table = &cancunInstructionSet
	case evm.chainRules.IsShanghai:
		table = &shanghaiInstructionSet
	case evm.chainRules.IsMerge:
		table = &mergeInstructionSet
	case evm.chainRules.IsLondon:
		table = &londonInstructionSet
	case evm.chainRules.IsBerlin:
		table = &berlinInstructionSet
	case evm.chainRules.IsIstanbul:
		table = &istanbulInstructionSet
	case evm.chainRules.IsConstantinople:
		table = &constantinopleInstructionSet
	case evm.chainRules.IsByzantium:
		table = &byzantiumInstructionSet
	case evm.chainRules.IsEIP158:
		table = &spuriousDragonInstructionSet
	case evm.chainRules.IsEIP150:
		table = &tangerineWhistleInstructionSet
	case evm.chainRules.IsHomestead:
		table = &homesteadInstructionSet
	default:
		table = &frontierInstructionSet
	}
	var extraEips []int
	if len(evm.Config.ExtraEips) > 0 {
		// Deep-copy jumptable to prevent modification of opcodes in other tables
		table = copyJumpTable(table)
	}
	for _, eip := range evm.Config.ExtraEips {
		if err := EnableEIP(eip, table); err != nil {
			// Disable it, so caller can check if it's activated or not
			log.Error("EIP activation failed", "eip", eip, "error", err)
		} else {
			extraEips = append(extraEips, eip)
		}
	}
	evm.Config.ExtraEips = extraEips
	return &EVMInterpreter{evm: evm, table: table}
}

// Run loops and evaluates the contract's code with the given input data and returns
// the return byte-slice and an error if one occurred.
//
// It's important to note that any errors returned by the interpreter should be
// considered a revert-and-consume-all-gas operation except for
// ErrExecutionReverted which means revert-and-keep-gas-left.
func (in *EVMInterpreter) Run(contract *Contract, input []byte, readOnly bool) (ret []byte, err error) {
	// Increment the call depth which is restricted to 1024
	in.evm.depth++
	defer func() { in.evm.depth-- }()

	// Make sure the readOnly is only set if we aren't in readOnly yet.
	// This also makes sure that the readOnly flag isn't removed for child calls.
	if readOnly && !in.readOnly {
		in.readOnly = true
		defer func() { in.readOnly = false }()
	}

	// Reset the previous call's return data. It's unimportant to preserve the old buffer
	// as every returning call will return new data anyway.
	in.returnData = nil

	// Don't bother with the execution if there's no code.
	if len(contract.Code) == 0 {
		return nil, nil
	}

	var (
		op          OpCode        // current opcode
		mem         = NewMemory() // bound memory
		stack       = newstack()  // local stack
		callContext = &ScopeContext{
			Memory:   mem,
			Stack:    stack,
			Contract: contract,
		}
		// For optimisation reason we're using uint64 as the program counter.
		// It's theoretically possible to go above 2^64. The YP defines the PC
		// to be uint256. Practically much less so feasible.
		pc   = uint64(0) // program counter
		cost uint64
		// copies used by tracer
		pcCopy  uint64 // needed for the deferred EVMLogger
		gasCopy uint64 // for EVMLogger to log gas remaining before execution
		logged  bool   // deferred EVMLogger should ignore already logged steps
		res     []byte // result of the opcode execution function
		debug   = in.evm.Config.Tracer != nil
	)
	// Don't move this deferred function, it's placed before the capturestate-deferred method,
	// so that it get's executed _after_: the capturestate needs the stacks before
	// they are returned to the pools
	defer func() {
		returnStack(stack)
	}()
	contract.Input = input

	if debug {
		defer func() {
			if err != nil {
				if !logged {
					in.evm.Config.Tracer.CaptureState(pcCopy, op, gasCopy, cost, callContext, in.returnData, in.evm.depth, err)
				} else {
					in.evm.Config.Tracer.CaptureFault(pcCopy, op, gasCopy, cost, callContext, in.evm.depth, err)
				}
			}
		}()
	}
	// The Interpreter main run loop (contextual). This loop runs until either an
	// explicit STOP, RETURN or SELFDESTRUCT is executed, an error occurred during
	// the execution of one of the operations or until the done flag is set by the
	// parent context.
	for {
		if debug {
			// Capture pre-execution values for tracing.
			logged, pcCopy, gasCopy = false, pc, contract.Gas
		}
		// Get the operation from the jump table and validate the stack to ensure there are
		// enough stack items available to perform the operation.
		op = contract.GetOp(pc)
		operation := in.table[op]
		cost = operation.constantGas // For tracing
		// Validate stack
		if sLen := stack.len(); sLen < operation.minStack {
			return nil, &ErrStackUnderflow{stackLen: sLen, required: operation.minStack}
		} else if sLen > operation.maxStack {
			return nil, &ErrStackOverflow{stackLen: sLen, limit: operation.maxStack}
		}
		if !contract.UseGas(cost) {
			return nil, ErrOutOfGas
		}
		// for trace
		// -------------
		if in.evm.TraceStateFlag {
			in.beforeOpcodeExecutionHook(&pc, op, callContext)
		}
		// -------------
		if operation.dynamicGas != nil {
			// All ops with a dynamic memory usage also has a dynamic gas cost.
			var memorySize uint64
			// calculate the new memory size and expand the memory to fit
			// the operation
			// Memory check needs to be done prior to evaluating the dynamic gas portion,
			// to detect calculation overflows
			if operation.memorySize != nil {
				memSize, overflow := operation.memorySize(stack)
				if overflow {
					return nil, ErrGasUintOverflow
				}
				// memory is expanded in words of 32 bytes. Gas
				// is also calculated in words.
				if memorySize, overflow = math.SafeMul(toWordSize(memSize), 32); overflow {
					return nil, ErrGasUintOverflow
				}
			}
			// Consume the gas and return an error if not enough gas is available.
			// cost is explicitly set so that the capture state defer method can get the proper cost
			var dynamicCost uint64
			dynamicCost, err = operation.dynamicGas(in.evm, contract, stack, mem, memorySize)
			cost += dynamicCost // for tracing
			if err != nil || !contract.UseGas(dynamicCost) {
				return nil, ErrOutOfGas
			}
			// Do tracing before memory expansion
			if debug {
				in.evm.Config.Tracer.CaptureState(pc, op, gasCopy, cost, callContext, in.returnData, in.evm.depth, err)
				logged = true
			}
			if memorySize > 0 {
				mem.Resize(memorySize)
			}
		} else if debug {
			in.evm.Config.Tracer.CaptureState(pc, op, gasCopy, cost, callContext, in.returnData, in.evm.depth, err)
			logged = true
		}
		// execute the operation
		// for trace
		if in.evm.TraceStateFlag {
			res, err = in.opcodeExecutionHook(&pc, op, callContext)
		} else {
			res, err = operation.execute(&pc, in, callContext)
		}
		if err != nil {
			break
		}
		pc++
	}

	if err == errStopToken {
		err = nil // clear stop token error
	}

	return res, err
}

func (in *EVMInterpreter) beforeOpcodeExecutionHook(pc *uint64, op OpCode, scope *ScopeContext) {
	op_str := opCodeToString[op]
	if op_str == "SLOAD" {
		// prepare storage for dynamicGas
		loc := scope.Stack.peek()
		hash := common.Hash(loc.Bytes32())
		blockNumber := in.evm.Context.BlockNumber
		if !in.evm.StateDB.AccountState().IsTouchedStorage(scope.Contract.Address(), hash, blockNumber) {
			if in.evm.StateDB.AccountState().IsRequirePRC() {
				value, _ := in.evm.StateDB.AccountState().RPCProvider.GetStorageAt(scope.Contract.Address(), hash, blockNumber)
				in.evm.StateDB.SetState(scope.Contract.Address(), hash, value)
			}
			val := in.evm.StateDB.GetState(scope.Contract.Address(), hash)
			in.evm.StateDB.AccountState().UpdateTouchedStorage(scope.Contract.Address(), loc.Bytes32(), val)
			// for commited account state
			in.evm.StateDB.AccountState().CommitedAccountState.UpdateTouchedStorage(scope.Contract.Address(), loc.Bytes32(), in.evm.StateDB.GetState(scope.Contract.Address(), hash))
		}
	} else if op_str == "SSTORE" {
		_, loc := scope.Stack.Back(1), scope.Stack.Back(0)
		hash := common.Hash(loc.Bytes32())
		blockNumber := in.evm.Context.BlockNumber
		if !in.evm.StateDB.AccountState().IsTouchedStorage(scope.Contract.Address(), hash, blockNumber) {
			if in.evm.StateDB.AccountState().IsRequirePRC() {
				value, _ := in.evm.StateDB.AccountState().RPCProvider.GetStorageAt(scope.Contract.Address(), hash, blockNumber)
				in.evm.StateDB.SetState(scope.Contract.Address(), hash, value)
			}
			// in.evm.StateDB.AccountState().UpdateTouchedStorage(scope.Contract.Address(), loc.Bytes32(), in.evm.StateDB.GetState(scope.Contract.Address(), hash))
			// for commited account state
			in.evm.StateDB.AccountState().CommitedAccountState.UpdateTouchedStorage(scope.Contract.Address(), loc.Bytes32(), in.evm.StateDB.GetState(scope.Contract.Address(), hash))
		}
	} else if op_str == "BALANCE" {
		slot := scope.Stack.peek()
		address := common.Address(slot.Bytes20())
		CheckAndSetBalance(in.evm, address)
	} else if op_str == "EXTCODEHASH" || op_str == "EXTCODESIZE" || op_str == "EXTCODECOPY" {
		slot := scope.Stack.peek()
		address := common.Address(slot.Bytes20())
		CheckAndSetCode(in.evm, address)
	} else if op_str == "CALL" || op_str == "CALLCODE" || op_str == "DELEGATECALL" || op_str == "STATICCALL" {
		addr := scope.Stack.Back(1)
		toAddr := common.Address(addr.Bytes20())
		SetCodeBalanceNonce(in.evm, toAddr)
	}
}

func (in *EVMInterpreter) opcodeExecutionHook(pc *uint64, op OpCode, callContext *ScopeContext) (res []byte, err error) {
	operation := in.table[op]
	op_str := opCodeToString[op]
	if op_str == "CREATE" || op_str == "CREATE2" || op_str == "CALL" || op_str == "CALLCODE" || op_str == "DELEGATECALL" || op_str == "STATICCALL" {
		accountStateSnapshot := in.evm.StateDB.AccountState().ExportSnapshot()
		var (
			from, to common.Address
		)
		from = callContext.Contract.Address()
		if op_str == "CALL" || op_str == "CALLCODE" {
			addr := *callContext.Stack.Back(1)
			to = common.Address(addr.Bytes20())
		} else if op_str == "CREATE" {
			to = crypto.CreateAddress(from, in.evm.StateDB.GetNonce(from))
		} else if op_str == "CREATE2" {
			offset, size, salt := callContext.Stack.Back(1), callContext.Stack.Back(2), callContext.Stack.Back(3)
			code := callContext.Memory.GetCopy(int64(offset.Uint64()), int64(size.Uint64()))
			codeAndHash := &codeAndHash{code: code}
			to = crypto.CreateAddress2(from, salt.Bytes32(), codeAndHash.Hash().Bytes())
		}
		res, err = operation.execute(pc, in, callContext)
		// record account state
		if err != nil {
			in.evm.StateDB.AccountState().RevertAccountState(accountStateSnapshot, in.evm.StateDB, in.evm.StateDB.AccountState().IsRequirePRC())
		} else {
			if op_str == "CALL" || op_str == "CALLCODE" {
				in.evm.StateDB.AccountState().UpdateTouchedBalance(from, in.evm.StateDB.GetBalance(from))
				in.evm.StateDB.AccountState().UpdateTouchedNonce(from, in.evm.StateDB.GetNonce(from))
				in.evm.StateDB.AccountState().UpdateTouchedBalance(to, in.evm.StateDB.GetBalance(to))
				in.evm.StateDB.AccountState().UpdateTouchedNonce(to, in.evm.StateDB.GetNonce(to))
			} else if op_str == "CREATE" {
				in.evm.StateDB.AccountState().UpdateTouchedBalance(from, in.evm.StateDB.GetBalance(from))
				in.evm.StateDB.AccountState().UpdateTouchedNonce(from, in.evm.StateDB.GetNonce(from))
				in.evm.StateDB.AccountState().UpdateTouchedBalance(to, in.evm.StateDB.GetBalance(to))
				in.evm.StateDB.AccountState().UpdateTouchedNonce(to, in.evm.StateDB.GetNonce(to))
				in.evm.StateDB.AccountState().UpdateTouchedCode(to, in.evm.StateDB.GetCode(to))
			} else if op_str == "CREATE2" {
				in.evm.StateDB.AccountState().UpdateTouchedCode(to, in.evm.StateDB.GetCode(to))
				in.evm.StateDB.AccountState().UpdateTouchedNonce(from, in.evm.StateDB.GetNonce(from))
				in.evm.StateDB.AccountState().UpdateTouchedNonce(to, in.evm.StateDB.GetNonce(to))
			}
		}
	} else if op_str == "SELFDESTRUCT" || op_str == "SSTORE" {
		res, err = operation.executeHook(pc, in, callContext)
	} else {
		res, err = operation.execute(pc, in, callContext)
	}
	return res, err
}

func SetCodeBalanceNonce(evm *EVM, account common.Address) {
	CheckAndSetCode(evm, account)
	CheckAndSetBalance(evm, account)
	CheckAndSetNonce(evm, account)
}

func CheckAndSetCode(evm *EVM, account common.Address) {
	blockNumber := evm.Context.BlockNumber
	if !evm.StateDB.AccountState().IsTouchedCode(account, blockNumber) {
		if evm.StateDB.AccountState().IsRequirePRC() {
			code, _ := evm.StateDB.AccountState().RPCProvider.GetCodeAt(account, blockNumber)
			evm.StateDB.SetCode(account, code)
		}
		evm.StateDB.AccountState().UpdateTouchedCode(account, evm.StateDB.GetCode(account))
		evm.StateDB.AccountState().CommitedAccountState.UpdateTouchedCode(account, evm.StateDB.GetCode(account))
	} else if evm.StateDB.GetCode(account) == nil && evm.StateDB.AccountState().GetCode(account) != nil {
		evm.StateDB.SetCode(account, evm.StateDB.AccountState().GetCode(account))
	}
}

func CheckAndSetBalance(evm *EVM, account common.Address) {
	blockNumber := evm.Context.BlockNumber
	if !evm.StateDB.AccountState().IsTouchedBalance(account, blockNumber) {
		if evm.StateDB.AccountState().IsRequirePRC() {
			balance, _ := evm.StateDB.AccountState().RPCProvider.GetBalanceAt(account, blockNumber)
			evm.StateDB.SetBalance(account, balance)
		}
		evm.StateDB.AccountState().CommitedAccountState.UpdateTouchedBalance(account, evm.StateDB.GetBalance(account))
	}
	evm.StateDB.AccountState().UpdateTouchedBalance(account, evm.StateDB.GetBalance(account))
}

func CheckAndSetNonce(evm *EVM, account common.Address) {
	blockNumber := evm.Context.BlockNumber
	if !evm.StateDB.AccountState().IsTouchedNonce(account, blockNumber) {
		if evm.StateDB.AccountState().IsRequirePRC() {
			nonce, _ := evm.StateDB.AccountState().RPCProvider.GetNonceAt(account, blockNumber)
			evm.StateDB.SetNonce(account, nonce)
		}
		evm.StateDB.AccountState().CommitedAccountState.UpdateTouchedNonce(account, evm.StateDB.GetNonce(account))
	}
	evm.StateDB.AccountState().UpdateTouchedNonce(account, evm.StateDB.GetNonce(account))
}

// func (in *EVMInterpreter) dynamicGasHook(op OpCode, contract *Contract, stack *Stack, mem *Memory, memorySize uint64) (dynamicCost uint64, err error) {
// 	op_str := opCodeToString[op]
// 	operation := in.table[op]
// 	if in.evm.StateDB.AccountState().IsRequirePRC() {
// 		if op_str == "SSTORE" {
// 			dynamicCost, err = operation.dynamicGasHook(in.evm, contract, stack, mem, memorySize)
// 		} else {
// 			dynamicCost, err = operation.dynamicGas(in.evm, contract, stack, mem, memorySize)
// 		}
// 	} else {
// 		dynamicCost, err = operation.dynamicGas(in.evm, contract, stack, mem, memorySize)
// 	}
// 	fmt.Println("SSTORE", dynamicCost)
// 	return dynamicCost, err
// }
