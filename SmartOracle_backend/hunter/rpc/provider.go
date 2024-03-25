package RPCProvider

import (
	"context"
	"log"
	"math/big"

	"github.com/ethereum/go-ethereum/common"
	"github.com/ethereum/go-ethereum/core/types"
	"github.com/ethereum/go-ethereum/ethclient"
)

type Provider struct {
	blockNumber *big.Int
	rpcURL      string
}

func (provider *Provider) SetURL(url string) {
	provider.rpcURL = url
}

func (provider *Provider) GetStorageAt(account common.Address, key common.Hash, blockNumber *big.Int) (common.Hash, error) {
	blockNumber = new(big.Int).Sub(blockNumber, big.NewInt(1))
	client, err := ethclient.Dial(provider.rpcURL)
	if err != nil {
		log.Fatal(err)
	}

	value, err := client.StorageAt(context.Background(), account, key, blockNumber)
	// fmt.Println("GetStorageAt", hex.EncodeToString(value), err)
	return common.BytesToHash(value), err
}

func (provider *Provider) GetCodeAt(account common.Address, blockNumber *big.Int) ([]byte, error) {
	blockNumber = new(big.Int).Sub(blockNumber, big.NewInt(1))
	client, err := ethclient.Dial(provider.rpcURL)
	if err != nil {
		log.Fatal(err)
	}

	value, err := client.CodeAt(context.Background(), account, blockNumber)
	// fmt.Println("getCodeAt", account, len(value))
	return value, err
}

func (provider *Provider) GetNonceAt(account common.Address, blockNumber *big.Int) (uint64, error) {
	blockNumber = new(big.Int).Sub(blockNumber, big.NewInt(1))
	client, err := ethclient.Dial(provider.rpcURL)
	if err != nil {
		log.Fatal(err)
	}

	value, err := client.NonceAt(context.Background(), account, blockNumber)
	// fmt.Println("getNonceAt", account, value)
	return value, err
}

func (provider *Provider) GetBalanceAt(account common.Address, blockNumber *big.Int) (*big.Int, error) {
	blockNumber = new(big.Int).Sub(blockNumber, big.NewInt(1))
	client, err := ethclient.Dial(provider.rpcURL)
	if err != nil {
		log.Fatal(err)
	}

	value, err := client.BalanceAt(context.Background(), account, blockNumber)
	// fmt.Println("getBalanceAt", account, value)
	return value, err
}

func (provider *Provider) GetTransactionByHash(hash common.Hash) (tx *types.Transaction, isPending bool, err error) {
	client, err := ethclient.Dial(provider.rpcURL)
	if err != nil {
		log.Fatal(err)
	}

	tx, isPending, err = client.TransactionByHash(context.Background(), hash)
	return tx, isPending, err
}

func (provider *Provider) GetTransactionReceipt(hash common.Hash) (txReceipt *types.Receipt, err error) {
	client, err := ethclient.Dial(provider.rpcURL)
	if err != nil {
		log.Fatal(err)
	}

	txReceipt, err = client.TransactionReceipt(context.Background(), hash)
	return txReceipt, err
}

func (provider *Provider) GetBlockByNumber(number *big.Int) (block *types.Block, err error) {
	client, err := ethclient.Dial(provider.rpcURL)
	if err != nil {
		log.Fatal(err)
	}

	block, err = client.BlockByNumber(context.Background(), number)
	return block, err
}

func (provider *Provider) GetHeaderByNumber(number *big.Int) (header *types.Header, err error) {
	client, err := ethclient.Dial(provider.rpcURL)
	if err != nil {
		log.Fatal(err)
	}

	header, err = client.HeaderByNumber(context.Background(), number)
	return header, err
}

// func main() {
// 	// client, err := ethclient.Dial("https://eth-mainnet.g.alchemy.com/v2/HAiqB1Ad1L6naK_ipKNjkTDZ56Ozepj9")
// 	// if err != nil {
// 	// 	log.Fatal(err)
// 	// }

// 	// // Get the balance of an account
// 	// account := common.HexToAddress("0x71c7656ec7ab88b098defb751b7401b5f6d8976f")
// 	// balance, err := client.BalanceAt(context.Background(), account, nil)
// 	// if err != nil {
// 	// 	log.Fatal(err)
// 	// }

// 	// fmt.Printf("Account balance: %d\n", balance) // 25893180161173005034

// 	// // Get the latest known block
// 	// block, err := client.BlockByNumber(context.Background(), nil)
// 	// if err != nil {
// 	// 	log.Fatal(err)
// 	// }

// 	// fmt.Printf("Latest block: %d\n", block.Number().Uint64())
// 	account := common.HexToAddress("0x6b175474e89094c44da98b954eedeac495271d0f")
// 	key := common.HexToHash("0x15faa59cd19891e9621a3bba273a9f040887cde9f44ce391e7a85ff4c6110dc6")
// 	blockNumber := big.NewInt(10954414)
// 	getStorageAt(account, key, blockNumber)
// }
