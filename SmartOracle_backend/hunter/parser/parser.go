package parser

import (
	// "encoding/hex"

	"encoding/json"
	"fmt"
	"io/ioutil"
	"math/big"
	"strconv"
	"strings"

	abi "github.com/ethereum/go-ethereum/accounts/abi"
	"github.com/ethereum/go-ethereum/common"
	vm "github.com/ethereum/go-ethereum/core/vm"
)

type ERC20TokenTx struct {
	From    common.Address
	To      common.Address
	Address common.Address
	Amount  *big.Int
	Index   int
}

type ERC20TokenSwap struct {
	TokenIn   common.Address
	AmountIn  *big.Int
	TokenOut  common.Address
	AmountOut *big.Int
	Address   common.Address
	Index     int
}

type ERC721TokenTx struct {
	From    common.Address
	To      common.Address
	Address common.Address
	TokenId *big.Int
	Index   int
}

type ERC1155TokenTx struct {
	Operator common.Address
	From     common.Address
	To       common.Address
	Address  common.Address
	TokenId  *big.Int
	Value    *big.Int
	Index    int
}

type OpenseaOrder struct {
	Maker      common.Address
	Taker      common.Address
	Address    common.Address
	Price      *big.Int
	NFTTokenTx interface{}
	Index      int
}

type ERC20TokenMint struct {
	Address common.Address
	To      common.Address
	Amount  *big.Int
	Index   int
}

type ExpandedTx struct {
	RawTx              *vm.ExternalTx   "json:RawTx"
	ERC20TokenTxList   []ERC20TokenTx   "json:ERC20TokenTxList"
	ERC20TokenMintList []ERC20TokenMint "json:ERC20TokenMintList"
	ERC20TokenSwapList []ERC20TokenSwap "json:ERC20TokenSwapList"
	ERC721TokenTxList  []ERC721TokenTx  "json:ERC721TokenTxList"
	ERC1155TokenTxList []ERC1155TokenTx "json:ERC1155TokenTxList"

	OpenseaOrderList []OpenseaOrder "json:OpenseaOrderList"
}

type Parser struct {
	Abi             abi.ABI
	TokenSwapMap    map[common.Address]TokenSwapInfo
	ExpandedTx      ExpandedTx
	openseaContract common.Address
}

func (parser *Parser) InitParser() {
	var err error
	parser.Abi, err = abi.JSON(strings.NewReader(getAbiString()))
	if err != nil {
		fmt.Println("Parser error", err)
	}

	// load tokenSwapInfo
	parser.TokenSwapMap = getTokenSwapMap()
	parser.openseaContract = common.HexToAddress("0x7be8076f4ea4a4ad08075c2508e481d6c946d12b")
}

func DumpExpandedTx(expandedTx ExpandedTx, path string) {
	var err error
	b, _ := json.Marshal(expandedTx)
	err = ioutil.WriteFile(path+"/"+expandedTx.RawTx.BlockNumber.String()+"_"+strconv.Itoa(expandedTx.RawTx.TxIndex)+"_expanded"+".json", b, 0644)
	if err != nil {
		fmt.Println(err)
	}
}

func (parser *Parser) ExtractExpandedTx(ExTx *vm.ExternalTx) ExpandedTx {

	// var tokenTxIndex *int
	parser.ExpandedTx = ExpandedTx{
		RawTx: ExTx,
	}
	index := new(int)
	*index = 0
	if len(ExTx.InTxs) == 1 {
		parser.parseTxTreeUtil(ExTx.InTxs[0], index)
	}
	return parser.ExpandedTx
}

func (parser *Parser) parseTxTreeUtil(InTx *vm.InternalTx, index *int) []*vm.Event {
	// the event before

	if InTx.Value != nil && InTx.Value.Cmp(new(big.Int)) > 0 {
		parser.ExpandedTx.ERC20TokenTxList = append(parser.ExpandedTx.ERC20TokenTxList, ERC20TokenTx{
			From:    InTx.From,
			To:      InTx.To,
			Address: common.HexToAddress("0x0"),
			Amount:  new(big.Int).Add(InTx.Value, new(big.Int)),
			Index:   *index,
		})
		*index = *index + 1
	}

	var eventList []*vm.Event
	for _, tx := range InTx.InTxs {
		tmpEvents := parser.parseTxTreeUtil(tx, index)
		eventList = append(eventList, tmpEvents...)
	}

	for _, event := range InTx.Events {
		parser.parseEvent(event, index, eventList)
		eventList = append(eventList, event)
	}

	return eventList
}

func (parser *Parser) parseEvent(event *vm.Event, index *int, eventList []*vm.Event) (eventName string) {
	if event.Topics[0].String() == "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef" && len(event.Topics) == 3 {
		// ERC-20 transfer
		eventName = "ERC20-TokenTx"
		erc20TokenTx := parser.parseERC20TokenTx(event)
		erc20TokenTx.Index = *index
		*index = *index + 1
		parser.ExpandedTx.ERC20TokenTxList = append(parser.ExpandedTx.ERC20TokenTxList, erc20TokenTx)
	} else if event.Topics[0].String() == "0xe1fffcc4923d04b559f4d29a8bfc6cda04eb5b0d3c460751c2402c5c5cc9109c" && len(event.Topics) == 2 {
		eventName = "ERC20-Mint"
		erc20TokenMint := parser.parseERC20TokenMint(event)
		erc20TokenMint.Index = *index
		*index = *index + 1
		parser.ExpandedTx.ERC20TokenMintList = append(parser.ExpandedTx.ERC20TokenMintList, erc20TokenMint)
	} else if event.Topics[0].String() == "0xc42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67" && len(event.Topics) == 3 {
		// Uniswap V3 swap
		eventName = "ERC20-TokenSwap"
		erc20TokenSwap := parser.parseUniswapV3TokenSwap(event)
		erc20TokenSwap.Index = *index
		*index = *index + 1
		parser.ExpandedTx.ERC20TokenSwapList = append(parser.ExpandedTx.ERC20TokenSwapList, erc20TokenSwap)
	} else if event.Topics[0].String() == "0xd78ad95fa46c994b6551d0da85fc275fe613ce37657fb8d5e3d130840159d822" && len(event.Topics) == 3 {
		// Uniswap V2 swap
		eventName = "ERC20-TokenSwap"
		erc20TokenSwap := parser.parseUniswapV2TokenSwap(event)
		erc20TokenSwap.Index = *index
		*index = *index + 1
		parser.ExpandedTx.ERC20TokenSwapList = append(parser.ExpandedTx.ERC20TokenSwapList, erc20TokenSwap)
	} else if event.Topics[0].String() == "0xc3d58168c5ae7397731d063d5bbf3d657854427343f4c083240f7aacaa2d0f62" && len(event.Topics) == 4 {
		// ERC-1155 transfer
		eventName = "ERC1155-TokenTx"
		erc1155TokenTx := parser.parseERC1155TokenTx(event)
		erc1155TokenTx.Index = *index
		*index = *index + 1
		parser.ExpandedTx.ERC1155TokenTxList = append(parser.ExpandedTx.ERC1155TokenTxList, erc1155TokenTx)
	} else if event.Topics[0].String() == "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef" && len(event.Topics) == 4 {
		// ERC-721 transfer
		eventName = "ERC721-TokenTx"
		erc721TokenTx := parser.parseERC721TokenTx(event)
		erc721TokenTx.Index = *index
		*index = *index + 1
		parser.ExpandedTx.ERC721TokenTxList = append(parser.ExpandedTx.ERC721TokenTxList, erc721TokenTx)
	} else if event.Topics[0].String() == "0xc4109843e0b7d514e4c093114b863f8e7d8d9a458c372cd51bfe526b588006c9" && len(event.Topics) == 4 {
		eventName = "Opensea-Order"
		openseaOrder := parser.parseOpenseaOrder(event, eventList)
		openseaOrder.Index = *index
		*index = *index + 1
		parser.ExpandedTx.OpenseaOrderList = append(parser.ExpandedTx.OpenseaOrderList, openseaOrder)
	}
	return eventName
}

func (parser *Parser) parseERC20TokenMint(event *vm.Event) ERC20TokenMint {
	to := common.HexToAddress(event.Topics[1].String())
	amount := new(big.Int).SetBytes(event.Data)
	appendERC20TokenMint := ERC20TokenMint{
		Address: event.Address,
		To:      to,
		Amount:  amount,
	}
	return appendERC20TokenMint
}

func (parser *Parser) parseERC20TokenTx(event *vm.Event) ERC20TokenTx {
	amount := new(big.Int).SetBytes(event.Data)
	sender := common.HexToAddress(event.Topics[1].String())
	to := common.HexToAddress(event.Topics[2].String())
	appendERC20TokenTx := ERC20TokenTx{
		From:    sender,
		To:      to,
		Address: event.Address,
		Amount:  amount,
	}
	return appendERC20TokenTx
}

func (parser *Parser) parseUniswapV3TokenSwap(event *vm.Event) ERC20TokenSwap {
	// identify swap action in uniswap v3
	// fmt.Println(parser)
	res, err := parser.Abi.Unpack("SwapUniswapV3", event.Data)
	if err != nil {
		fmt.Println("Parser error", err)
	}
	var token0 common.Address
	var token1 common.Address
	amount0 := res[0].(*big.Int)
	amount1 := res[1].(*big.Int)
	// the case for table
	if _, ok := parser.TokenSwapMap[event.Address]; ok {
		token0 = parser.TokenSwapMap[event.Address].Token0
		token1 = parser.TokenSwapMap[event.Address].Token1
	} else {
		// the case fo no-table
		// find the kind of token
		for _, tokenTx := range parser.ExpandedTx.ERC20TokenTxList {
			if new(big.Int).Abs(amount0).Cmp(tokenTx.Amount) == 0 {
				token0 = tokenTx.Address
			}
			if new(big.Int).Abs(amount1).Cmp(tokenTx.Amount) == 0 {
				token1 = tokenTx.Address
			}
			if token0 != common.HexToAddress("0x0") && token1 != common.HexToAddress("0x0") {
				break
			}
		}
	}
	var amountIn *big.Int
	var amountOut *big.Int
	var tokenIn common.Address
	var tokenOut common.Address
	if amount0.Cmp(new(big.Int)) >= 0 {
		tokenIn = token0
		amountIn = amount0
		tokenOut = token1
		amountOut = amount1
	} else {
		tokenIn = token1
		amountIn = amount1
		tokenOut = token0
		amountOut = amount0
	}
	appendERC20TokenSwap := ERC20TokenSwap{
		TokenIn:   tokenIn,
		AmountIn:  new(big.Int).Abs(amountIn),
		TokenOut:  tokenOut,
		AmountOut: new(big.Int).Abs(amountOut),
		Address:   event.Address,
	}
	return appendERC20TokenSwap
}

func (parser *Parser) parseUniswapV2TokenSwap(event *vm.Event) ERC20TokenSwap {
	// identify swap action in uniswap v2
	res, err := parser.Abi.Unpack("SwapUniswapV2", event.Data)
	if err != nil {
		fmt.Println("Parser error", err)
	}
	var token0 common.Address
	var token1 common.Address
	amount0In := res[0].(*big.Int)
	amount1In := res[1].(*big.Int)
	amount0Out := res[2].(*big.Int)
	amount1Out := res[3].(*big.Int)

	if _, ok := parser.TokenSwapMap[event.Address]; ok {
		token0 = parser.TokenSwapMap[event.Address].Token0
		token1 = parser.TokenSwapMap[event.Address].Token1
	} else {
		// the case fo no-table
		// find the kind of token
		for _, tokenTx := range parser.ExpandedTx.ERC20TokenTxList {
			if new(big.Int).Abs(amount0In).Cmp(tokenTx.Amount) == 0 || new(big.Int).Abs(amount0Out).Cmp(tokenTx.Amount) == 0 {
				token0 = tokenTx.Address
			}
			if new(big.Int).Abs(amount1In).Cmp(tokenTx.Amount) == 0 || new(big.Int).Abs(amount1Out).Cmp(tokenTx.Amount) == 0 {
				token1 = tokenTx.Address
			}
			if token0 != common.HexToAddress("0x0") && token1 != common.HexToAddress("0x0") {
				break
			}
		}
	}
	var amountIn *big.Int
	var amountOut *big.Int
	var tokenIn common.Address
	var tokenOut common.Address
	if amount0In.Cmp(new(big.Int)) > 0 {
		tokenIn = token0
		amountIn = amount0In
		tokenOut = token1
		amountOut = amount1Out
	} else if amount1In.Cmp(new(big.Int)) > 0 {
		tokenIn = token1
		amountIn = amount1In
		tokenOut = token0
		amountOut = amount0Out
	}
	appendERC20TokenSwap := ERC20TokenSwap{
		TokenIn:   tokenIn,
		AmountIn:  new(big.Int).Abs(amountIn),
		TokenOut:  tokenOut,
		AmountOut: new(big.Int).Abs(amountOut),
		Address:   event.Address,
	}
	return appendERC20TokenSwap
}

func (parser *Parser) parseERC721TokenTx(event *vm.Event) ERC721TokenTx {
	sender := common.HexToAddress(event.Topics[1].String())
	to := common.HexToAddress(event.Topics[2].String())
	tokenId, _ := new(big.Int).SetString(event.Topics[3].String()[2:], 16)
	appendERC721TokenTx := ERC721TokenTx{
		From:    sender,
		To:      to,
		Address: event.Address,
		TokenId: tokenId,
	}
	return appendERC721TokenTx
}

func (parser *Parser) parseERC1155TokenTx(event *vm.Event) ERC1155TokenTx {
	operator := common.HexToAddress(event.Topics[1].String())
	sender := common.HexToAddress(event.Topics[2].String())
	to := common.HexToAddress(event.Topics[3].String())
	res, err := parser.Abi.Unpack("ERC1155TransferSingle", event.Data)
	if err != nil {
		fmt.Println("Parser error", err)
	}
	tokenId := res[0].(*big.Int)
	value := res[1].(*big.Int)
	appendERC1155TokenTx := ERC1155TokenTx{
		Operator: operator,
		From:     sender,
		To:       to,
		Address:  event.Address,
		TokenId:  tokenId,
		Value:    value,
	}
	return appendERC1155TokenTx
}

func (parser *Parser) parseOpenseaOrder(event *vm.Event, eventList []*vm.Event) OpenseaOrder {
	maker := common.HexToAddress(event.Topics[1].String())
	taker := common.HexToAddress(event.Topics[2].String())
	res, err := parser.Abi.Unpack("OpenseaOrdersMatched", event.Data)
	if err != nil {
		fmt.Println("Parser error", err)
	}
	price := res[2].(*big.Int)

	appendOpenseaOrder := OpenseaOrder{
		Maker:   maker,
		Taker:   taker,
		Price:   price,
		Address: event.Address,
	}
	// find the corresponding NFT transfer

	for _, event := range eventList {
		if event.Topics[0].String() == "0xc3d58168c5ae7397731d063d5bbf3d657854427343f4c083240f7aacaa2d0f62" && len(event.Topics) == 4 {
			// ERC-1155 transfer
			nftTokenTx := parser.parseERC1155TokenTx(event)
			appendOpenseaOrder.NFTTokenTx = nftTokenTx
		} else if event.Topics[0].String() == "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef" && len(event.Topics) == 4 {
			// ERC-721 transfer
			nftTokenTx := parser.parseERC721TokenTx(event)
			appendOpenseaOrder.NFTTokenTx = nftTokenTx
		}
	}
	return appendOpenseaOrder
}
