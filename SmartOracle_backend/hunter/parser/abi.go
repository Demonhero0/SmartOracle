package parser

func getAbiString() string {
	return `
    [
        {
            "anonymous": false,
            "inputs": [
                {
                    "indexed": true,
                    "name": "from",
                    "type": "address"
                },
                {
                    "indexed": true,
                    "name": "to",
                    "type": "address"
                },
                {
                    "indexed": false,
                    "name": "value",
                    "type": "uint256"
                }
            ],
            "name": "Transfer",
            "type": "event"
        },
        {
            "anonymous": false,
            "inputs": [
                {
                    "indexed": true,
                    "internalType": "address",
                    "name": "sender",
                    "type": "address"
                },
                {
                    "indexed": true,
                    "internalType": "address",
                    "name": "recipient",
                    "type": "address"
                },
                {
                    "indexed": false,
                    "internalType": "int256",
                    "name": "amount0",
                    "type": "int256"
                },
                {
                    "indexed": false,
                    "internalType": "int256",
                    "name": "amount1",
                    "type": "int256"
                },
                {
                    "indexed": false,
                    "internalType": "uint160",
                    "name": "sqrtPriceX96",
                    "type": "uint160"
                },
                {
                    "indexed": false,
                    "internalType": "uint128",
                    "name": "liquidity",
                    "type": "uint128"
                },
                {
                    "indexed": false,
                    "internalType": "int24",
                    "name": "tick",
                    "type": "int24"
                }
            ],
            "name": "SwapUniswapV3",
            "type": "event"
        },
        {
            "anonymous": false,
            "inputs": [
                {
                    "indexed": true,
                    "internalType": "address",
                    "name": "sender",
                    "type": "address"
                },
                {
                    "indexed": false,
                    "internalType": "uint256",
                    "name": "amount0In",
                    "type": "uint256"
                },
                {
                    "indexed": false,
                    "internalType": "uint256",
                    "name": "amount1In",
                    "type": "uint256"
                },
                {
                    "indexed": false,
                    "internalType": "uint256",
                    "name": "amount0Out",
                    "type": "uint256"
                },
                {
                    "indexed": false,
                    "internalType": "uint256",
                    "name": "amount1Out",
                    "type": "uint256"
                },
                {
                    "indexed": true,
                    "internalType": "address",
                    "name": "to",
                    "type": "address"
                }
            ],
            "name": "SwapUniswapV2",
            "type": "event"
        },
        {
            "anonymous": false,
            "inputs": [
                {
                    "indexed": true,
                    "internalType": "address",
                    "name": "from",
                    "type": "address"
                },
                {
                    "indexed": true,
                    "internalType": "address",
                    "name": "to",
                    "type": "address"
                },
                {
                    "indexed": true,
                    "internalType": "uint256",
                    "name": "tokenId",
                    "type": "uint256"
                }
            ],
            "name": "ERC721Transfer",
            "type": "event"
        },
        {
            "anonymous": false,
            "inputs": [
                {
                    "indexed": true,
                    "internalType": "address",
                    "name": "operator",
                    "type": "address"
                },
                {
                    "indexed": true,
                    "internalType": "address",
                    "name": "from",
                    "type": "address"
                },
                {
                    "indexed": true,
                    "internalType": "address",
                    "name": "to",
                    "type": "address"
                },
                {
                    "indexed": false,
                    "internalType": "uint256",
                    "name": "id",
                    "type": "uint256"
                },
                {
                    "indexed": false,
                    "internalType": "uint256",
                    "name": "value",
                    "type": "uint256"
                }
            ],
            "name": "ERC1155TransferSingle",
            "type": "event"
        },
        {
            "anonymous": false,
            "inputs": [
                {
                    "indexed": false,
                    "name": "buyHash",
                    "type": "bytes32"
                },
                {
                    "indexed": false,
                    "name": "sellHash",
                    "type": "bytes32"
                },
                {
                    "indexed": true,
                    "name": "maker",
                    "type": "address"
                },
                {
                    "indexed": true,
                    "name": "taker",
                    "type": "address"
                },
                {
                    "indexed": false,
                    "name": "price",
                    "type": "uint256"
                },
                {
                    "indexed": true,
                    "name": "metadata",
                    "type": "bytes32"
                }
            ],
            "name": "OpenseaOrdersMatched",
            "type": "event"
        }
    ]`
}
