package trace

import (
	"encoding/json"
	"math/big"
	"os"

	"github.com/ethereum/go-ethereum/common"
	RPCProvider "github.com/ethereum/go-ethereum/hunter/rpc"
)

type StateDB interface {
	GetBalance(common.Address) *big.Int
	SetBalance(common.Address, *big.Int)

	GetNonce(common.Address) uint64
	SetNonce(common.Address, uint64)

	GetCode(common.Address) []byte
	SetCode(common.Address, []byte)

	GetState(common.Address, common.Hash) common.Hash
	SetState(common.Address, common.Hash, common.Hash)
}

type AccountState struct {
	touchedStorageMap    map[common.Address]map[common.Hash]common.Hash
	touchedCodeMap       map[common.Address][]byte
	touchedNonceMap      map[common.Address]uint64
	touchedBalanceMap    map[common.Address]*big.Int
	RPCProvider          *RPCProvider.Provider
	requireRPC           bool
	CommitedAccountState *AccountState
}

func InitAccountState() *AccountState {
	newAccountState := &AccountState{
		touchedStorageMap: make(map[common.Address]map[common.Hash]common.Hash),
		touchedCodeMap:    make(map[common.Address][]byte),
		touchedNonceMap:   make(map[common.Address]uint64),
		touchedBalanceMap: make(map[common.Address]*big.Int),
		RPCProvider:       new(RPCProvider.Provider),
	}
	newAccountState.CommitAccountState()
	return newAccountState
}

// about RPC
func (accountState *AccountState) SetRequireRPC(flag bool) {
	accountState.requireRPC = flag
}

func (accountState *AccountState) IsRequirePRC() bool {
	return accountState.requireRPC
}

// about Storage
func (accountState *AccountState) IsTouchedStorage(account common.Address, key common.Hash, blockNumber *big.Int) (flag bool) {
	if _, ok := accountState.touchedStorageMap[account]; ok {
		if _, ok1 := accountState.touchedStorageMap[account][key]; ok1 {
			flag = true
		}
	}
	return flag
}

func (accountState *AccountState) UpdateTouchedStorage(account common.Address, key, value common.Hash) {
	if _, ok := accountState.touchedStorageMap[account]; !ok {
		accountState.touchedStorageMap[account] = make(map[common.Hash]common.Hash)
	}
	// if len(accountState.touchedStorageMap[account][key]) == 0 {
	// 	accountState.touchedStorageMap[account][key] = append(accountState.touchedStorageMap[account][key], value)
	// } else if value != accountState.GetStorage(account, key) {
	// 	accountState.touchedStorageMap[account][key] = append(accountState.touchedStorageMap[account][key], value)
	// }
	accountState.touchedStorageMap[account][key] = value
}

func (accountState *AccountState) GetStorage(account common.Address, key common.Hash) common.Hash {
	return accountState.touchedStorageMap[account][key]
}

// about code
func (accountState *AccountState) IsTouchedCode(account common.Address, blockNumber *big.Int) (flag bool) {
	if _, ok := accountState.touchedCodeMap[account]; ok {
		flag = true
	}
	return flag
}

func (accountState *AccountState) UpdateTouchedCode(account common.Address, code []byte) {
	for _, b := range code {
		accountState.touchedCodeMap[account] = append(accountState.touchedCodeMap[account], b)
	}
}

func (accountState *AccountState) GetCode(account common.Address) []byte {
	return accountState.touchedCodeMap[account]
}

// about nonce
func (accountState *AccountState) IsTouchedNonce(account common.Address, blockNumber *big.Int) (flag bool) {
	if _, ok := accountState.touchedNonceMap[account]; ok {
		flag = true
	}
	return flag
}

func (accountState *AccountState) UpdateTouchedNonce(account common.Address, nonce uint64) {
	// if len(accountState.touchedNonceMap[account]) == 0 {
	// 	accountState.touchedNonceMap[account] = append(accountState.touchedNonceMap[account], nonce)
	// } else if nonce != accountState.GetNonce(account) {
	// 	accountState.touchedNonceMap[account] = append(accountState.touchedNonceMap[account], nonce)
	// }
	accountState.touchedNonceMap[account] = nonce
}

func (accountState *AccountState) GetNonce(account common.Address) uint64 {
	return accountState.touchedNonceMap[account]
}

// about balance
func (accountState *AccountState) IsTouchedBalance(account common.Address, blockNumber *big.Int) (flag bool) {
	if _, ok := accountState.touchedBalanceMap[account]; ok {
		flag = true
	}
	return flag
}

func (accountState *AccountState) UpdateTouchedBalance(account common.Address, balance *big.Int) {
	// if len(accountState.touchedBalanceMap[account]) == 0 {
	// 	accountState.touchedBalanceMap[account] = append(accountState.touchedBalanceMap[account], balance)
	// } else if balance.Cmp(accountState.GetBalance(account)) != 0 {
	// 	accountState.touchedBalanceMap[account] = append(accountState.touchedBalanceMap[account], balance)
	// }
	accountState.touchedBalanceMap[account] = balance
}

func (accountState *AccountState) GetBalance(account common.Address) *big.Int {
	return new(big.Int).Set(accountState.touchedBalanceMap[account])
}

func (accountState *AccountState) UpdateTouchedMap(account common.Address, blockNumber *big.Int, balance *big.Int, nonce uint64, code []byte) {
	accountState.UpdateTouchedCode(account, code)
	accountState.UpdateTouchedBalance(account, balance)
	accountState.UpdateTouchedNonce(account, nonce)
}

func (accountState *AccountState) RevertAccountState(accountStateSnapshot AccountStateSnapshot, statedb StateDB, resetStateDB bool) {
	for account := range accountState.touchedStorageMap {
		for key := range accountState.touchedStorageMap[account] {
			isNewStorage := true
			if _, ok := accountStateSnapshot.TouchedStorageMap[account]; ok {
				if _, ok1 := accountStateSnapshot.TouchedStorageMap[account][key]; ok1 {
					accountState.touchedStorageMap[account][key] = accountStateSnapshot.TouchedStorageMap[account][key]
					isNewStorage = false
				}
			}
			if isNewStorage {
				accountState.touchedStorageMap[account][key] = accountState.GetCommittedStorage(account, key)
			}
			if resetStateDB {
				statedb.SetState(account, key, accountState.GetStorage(account, key))
			}
		}
	}
	// for account := range accountState.touchedCodeMap {
	// 	if _, ok := accountStateSnapshotIndex.touchedCodeIndexMap[account]; ok {
	// 		accountState.touchedCodeMap[account]
	// 	} else {

	// 	}
	// 	accountState.touchedCodeMap[account] = statedb.GetCode(account)
	// }
	for account := range accountState.touchedBalanceMap {
		if _, ok := accountStateSnapshot.TouchedBalanceMap[account]; ok {
			accountState.touchedBalanceMap[account] = accountStateSnapshot.TouchedBalanceMap[account]
		} else {
			accountState.touchedBalanceMap[account] = accountState.GetCommittedBalance(account)
		}
		if resetStateDB {
			statedb.SetBalance(account, accountState.GetBalance(account))
		}
	}
	for account := range accountState.touchedNonceMap {
		if _, ok := accountStateSnapshot.TouchedNonceMap[account]; ok {
			accountState.touchedNonceMap[account] = accountStateSnapshot.TouchedNonceMap[account]
		} else {
			accountState.touchedNonceMap[account] = accountState.GetCommitedNonce(account)
		}
		if resetStateDB {
			statedb.SetNonce(account, accountState.GetNonce(account))
		}
	}
}

func (accountState *AccountState) SyncStateDB(statedb StateDB) {
	for account := range accountState.touchedStorageMap {
		for key := range accountState.touchedStorageMap[account] {
			accountState.touchedStorageMap[account][key] = statedb.GetState(account, key)
		}
	}
	for account := range accountState.touchedCodeMap {
		accountState.touchedCodeMap[account] = statedb.GetCode(account)
	}
	for account := range accountState.touchedBalanceMap {
		accountState.touchedBalanceMap[account] = statedb.GetBalance(account)
	}
	for account := range accountState.touchedNonceMap {
		accountState.touchedNonceMap[account] = statedb.GetNonce(account)
	}
}

func (accountState *AccountState) CommitAccountState() {
	accountState.CommitedAccountState = accountState.deepCopy()
}

func (accountState *AccountState) deepCopy() *AccountState {
	newAccountState := &AccountState{
		touchedStorageMap: make(map[common.Address]map[common.Hash]common.Hash),
		touchedCodeMap:    make(map[common.Address][]byte),
		touchedNonceMap:   make(map[common.Address]uint64),
		touchedBalanceMap: make(map[common.Address]*big.Int),
	}
	for account := range accountState.touchedStorageMap {
		newAccountState.touchedStorageMap[account] = make(map[common.Hash]common.Hash)
		for key := range accountState.touchedStorageMap[account] {
			newAccountState.touchedStorageMap[account][key] = accountState.touchedStorageMap[account][key]
		}
	}
	for account := range accountState.touchedCodeMap {
		newAccountState.touchedCodeMap[account] = accountState.touchedCodeMap[account]
	}
	for account := range accountState.touchedBalanceMap {
		newAccountState.touchedBalanceMap[account] = new(big.Int).Set(accountState.touchedBalanceMap[account])
	}
	for account := range accountState.touchedNonceMap {
		newAccountState.touchedNonceMap[account] = accountState.touchedNonceMap[account]
	}
	return newAccountState
}

func (accountState *AccountState) GetCommittedStorage(account common.Address, key common.Hash) common.Hash {
	return accountState.CommitedAccountState.GetStorage(account, key)
}

func (accountState *AccountState) GetCommittedBalance(account common.Address) *big.Int {
	return new(big.Int).Set(accountState.CommitedAccountState.GetBalance(account))
}

func (accountState *AccountState) GetCommitedNonce(account common.Address) uint64 {
	return accountState.CommitedAccountState.GetNonce(account)
}

// func (accountState *AccountState) DumpJson(path string) {
// 	b, _ := json.Marshal(*accountState)
// 	os.WriteFile(path, b, 0644)
// }

type AccountStateSnapshot struct {
	TouchedStorageMap map[common.Address]map[common.Hash]common.Hash `json:"touchedStorageMap"`
	TouchedCodeMap    map[common.Address][]byte                      `json:"touchedCodeMap"`
	TouchedNonceMap   map[common.Address]uint64                      `json:"touchedNonceMap"`
	TouchedBalanceMap map[common.Address]*big.Int                    `json:"touchedBalanceMap"`
}

// type AccountStateSnapshotIndex struct {
// 	touchedStorageIndexMap map[common.Address]map[common.Hash]int
// 	touchedCodeIndexMap    map[common.Address]int
// 	touchedNonceIndexMap   map[common.Address]int
// 	touchedBalanceIndexMap map[common.Address]int
// }

func (accountState *AccountState) ExportSnapshot() AccountStateSnapshot {
	newAccountState := AccountStateSnapshot{
		TouchedStorageMap: make(map[common.Address]map[common.Hash]common.Hash),
		TouchedCodeMap:    make(map[common.Address][]byte),
		TouchedNonceMap:   make(map[common.Address]uint64),
		TouchedBalanceMap: make(map[common.Address]*big.Int),
	}
	for account := range accountState.touchedStorageMap {
		newAccountState.TouchedStorageMap[account] = make(map[common.Hash]common.Hash)
		for key := range accountState.touchedStorageMap[account] {
			newAccountState.TouchedStorageMap[account][key] = accountState.touchedStorageMap[account][key]
		}
	}
	for account := range accountState.touchedCodeMap {
		newAccountState.TouchedCodeMap[account] = accountState.touchedCodeMap[account]
	}
	for account := range accountState.touchedBalanceMap {
		newAccountState.TouchedBalanceMap[account] = new(big.Int).Set(accountState.touchedBalanceMap[account])
	}
	for account := range accountState.touchedNonceMap {
		newAccountState.TouchedNonceMap[account] = accountState.touchedNonceMap[account]
	}
	return newAccountState
}

func (accountState *AccountState) DumpAccountStateSnapshot(path string) {
	accountStateSnapshot := accountState.ExportSnapshot()
	b, _ := json.Marshal(accountStateSnapshot)
	os.WriteFile(path, b, 0644)
}

// func (accountState *AccountState) ExportSnapshotIndex() AccountStateSnapshotIndex {
// 	newAccountStateSnapshotIndex := AccountStateSnapshotIndex{
// 		touchedStorageIndexMap: make(map[common.Address]map[common.Hash]int),
// 		touchedCodeIndexMap:    make(map[common.Address]int),
// 		touchedNonceIndexMap:   make(map[common.Address]int),
// 		touchedBalanceIndexMap: make(map[common.Address]int),
// 	}
// 	for account := range accountState.touchedStorageMap {
// 		newAccountStateSnapshotIndex.touchedStorageIndexMap[account] = make(map[common.Hash]int)
// 		for key := range accountState.touchedStorageMap[account] {
// 			newAccountStateSnapshotIndex.touchedStorageIndexMap[account][key] = len(accountState.touchedStorageMap[account][key])
// 		}
// 	}
// 	for account := range accountState.touchedCodeMap {
// 		if len(accountState.touchedCodeMap[account]) > 0 {
// 			newAccountStateSnapshotIndex.touchedCodeIndexMap[account] = 1
// 		} else {
// 			newAccountStateSnapshotIndex.touchedCodeIndexMap[account] = 0
// 		}
// 	}
// 	for account := range accountState.touchedBalanceMap {
// 		newAccountStateSnapshotIndex.touchedNonceIndexMap[account] = len(accountState.touchedBalanceMap[account])
// 	}
// 	for account := range accountState.touchedNonceMap {
// 		newAccountStateSnapshotIndex.touchedBalanceIndexMap[account] = len(accountState.touchedNonceMap[account])
// 	}
// 	return newAccountStateSnapshotIndex
// }
