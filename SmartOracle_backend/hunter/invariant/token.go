package inv

import (
	"fmt"
	"math/big"
	"strings"

	// "encoding/hex"

	abi "github.com/ethereum/go-ethereum/accounts/abi"
	"github.com/ethereum/go-ethereum/common"
	"github.com/ethereum/go-ethereum/core"
	types "github.com/ethereum/go-ethereum/core/types"
	"github.com/ethereum/go-ethereum/hunter/trace"
)

type TokenHandler struct {
	RelatedAddress map[common.Address]bool
	RelatedToken   map[common.Address]bool
	erc20Abi       abi.ABI

	OriginalMsg *core.Message
}

func InitTokenHandler(oriMsg *core.Message) *TokenHandler {
	var err error
	tokenHandler := TokenHandler{
		RelatedAddress: make(map[common.Address]bool),
		RelatedToken:   make(map[common.Address]bool),
		OriginalMsg:    oriMsg,
	}

	tokenHandler.erc20Abi, err = abi.JSON(strings.NewReader(getAbiString()))
	if err != nil {
		fmt.Println("Parser error", err)
	}
	return &tokenHandler
}

func (t *TokenHandler) BalanceMsg(token, addr common.Address) (msg core.Message) {
	var accessList types.AccessList
	data, err := t.erc20Abi.Pack("balanceOf", addr)
	if err != nil {
		fmt.Println(err)
	}
	// fmt.Println(hex.EncodeToString(data))

	msg = core.Message{
		To:        &token,                     // to         *common.Address
		From:      common.HexToAddress("0x1"), // from       common.Address
		Nonce:     uint64(0),                  // nonce      uint64
		Value:     big.NewInt(int64(0)),       // amount     *big.Int
		GasLimit:  uint64(8000000),            // gasLimit   uint64
		GasPrice:  new(big.Int).Set(t.OriginalMsg.GasPrice),
		GasFeeCap: new(big.Int).Set(t.OriginalMsg.GasFeeCap),
		GasTipCap: new(big.Int).Set(t.OriginalMsg.GasTipCap),
		// GasFeeCap: new(big.Int),
		// GasTipCap: new(big.Int),
		// new(big.Int).SetInt64(350000000000), // gasPrice   *big.Int
		// new(big.Int).SetInt64(350000000000), // gasFeeCap  *big.Int
		// new(big.Int).SetInt64(350000000000), // gasTipCap  *big.Int
		Data:              data,       // data []byte
		AccessList:        accessList, // accessList AccessList
		SkipAccountChecks: true}       // isFake     bool

	return msg
}

func (t *TokenHandler) addRelatedToken(addr common.Address) {
	t.RelatedToken[addr] = true
}

func (t *TokenHandler) addRelatedAddress(addr common.Address) {
	t.RelatedAddress[addr] = true
}

func (t *TokenHandler) ParseTxTree(call *trace.CallFrame) {
	if call.To != nil {
		t.addRelatedAddress(*call.To)
	}

	// the event before
	for _, inCall := range call.Calls {
		t.ParseTxTree(inCall)
	}

	for _, event := range call.Logs {
		t.parseEvent(event)
	}
}

func (t *TokenHandler) parseEvent(event *trace.Log) {
	// identify erc20 transfer
	if len(event.Topics) > 0 && event.Topics[0].String() == "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef" && len(event.Topics) == 3 {
		// parsed, err := abi.JSON(strings.NewReader(oracle.Erc20string))
		// if err != nil {
		// 	fmt.Println("Parser error", err)
		// }
		// _, err := parsed.Unpack("Transfer", event.Data)
		// if err != nil {
		// 	fmt.Println("Parser error", err)
		// }
		// fmt.Println(res,err)
		// amount := res[0]
		sender := common.HexToAddress(event.Topics[1].String())
		to := common.HexToAddress(event.Topics[2].String())
		t.addRelatedAddress(sender)
		t.addRelatedAddress(to)
		t.addRelatedToken(event.Address)
	}
}
