package parser

import (
	"encoding/json"

	"github.com/ethereum/go-ethereum/common"
)

type TokenSwapInfo struct {
	Token0 common.Address `json:"token0"`
	Token1 common.Address `json:"token1"`
}

func getTokenSwapMap() map[common.Address]TokenSwapInfo {
	tokenSwapString := `{
        "0x0d4a11d5EEaaC28EC3F61d100daF4d40471f1852":{
            "Token0" : "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
            "Token1" : "0xdAC17F958D2ee523a2206206994597C13D831ec7"
        }
    }`
	tokenSwapMap := make(map[common.Address]TokenSwapInfo)
	json.Unmarshal([]byte(tokenSwapString), tokenSwapMap)
	return tokenSwapMap
}
