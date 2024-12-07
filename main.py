import requests
import asyncio
import websockets
import json
from solders.transaction import VersionedTransaction
from solders.keypair import Keypair
from solders.commitment_config import CommitmentLevel
from solders.rpc.requests import SendVersionedTransaction
from solders.rpc.config import RpcSendTransactionConfig
from solders.pubkey import Pubkey

# Parameters
target_contract_address = 'YOUR_TARGET_CONTRACT_ADDRESS'
sol_amount = 1  # Replace with the amount of SOL you want to spend
buyer_private_key_base58 = 'YOUR_BASE58_PRIVATE_KEY'  # Replace with your private key in base58 format
rpc_endpoint = 'Your RPC Endpoint'

# Function to send transaction through Pump Portal
def send_portal_transaction():
    response = requests.post(url="https://pumpportal.fun/api/trade-local", json={
        "publicKey": 'YOUR_PUBLIC_KEY',  # Your wallet public key
        "action": "buy",  # "buy" or "sell"
        "mint": target_contract_address,  # contract address of the token you want to trade
        "denominatedInSol": "true",  # "true" if amount is amount of SOL, "false" if amount is number of tokens
        "amount": sol_amount,  # amount of SOL or tokens
        "slippage": 1,  # percent slippage allowed
        "priorityFee": 0.00001,  # priority fee
        "pool": "pump"  # exchange to trade on. "pump" or "raydium" Super Important!!
    })

    if response.status_code == 200:  # successfully generated transaction
        data = response.content
        keypair = Keypair.from_base58_string(buyer_private_key_base58)
        tx = VersionedTransaction(VersionedTransaction.from_bytes(data).message, [keypair])

        commitment = CommitmentLevel.Confirmed
        config = RpcSendTransactionConfig(preflight_commitment=commitment)
        tx_payload = SendVersionedTransaction(tx, config)

        response = requests.post(
            url=rpc_endpoint,
            headers={"Content-Type": "application/json"},
            data=tx_payload.to_json()
        )
        tx_signature = response.json().get('result')
        if tx_signature:
            print(f'Transaction: https://solscan.io/tx/{tx_signature}')
        else:
            print(f'Error in transaction response: {response.json()}')
    else:
        print(f'Error generating transaction: {response.status_code}, {response.text}')

# Function to check if the contract already exists
def check_if_contract_exists():
    try:
        response = requests.post(
            url=rpc_endpoint,
            headers={"Content-Type": "application/json"},
            data=json.dumps({
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getAccountInfo",
                "params": [target_contract_address, {"commitment": "confirmed"}]
            })
        )
        result = response.json().get('result')
        if result and result.get('value'):
            print('Target contract already live:', target_contract_address)
            send_portal_transaction()
            return True
        else:
            print('Target contract not live yet, monitoring for creation...')
            return False
    except Exception as e:
        print(f'Error checking contract existence: {e}')
        return False

# Function to monitor token creation
async def monitor_token_creation():
    uri = "wss://pumpportal.fun/api/data"
    async with websockets.connect(uri) as websocket:
        # Subscribing to token creation events
        payload = {
            "method": "subscribeNewToken",
        }
        await websocket.send(json.dumps(payload))

        async for message in websocket:
            parsed_data = json.loads(message)
            # Check if the created token matches the target contract address
            if parsed_data.get('method') == 'newTokenCreated' and parsed_data['data'].get('contractAddress') == target_contract_address:
                print(f'Target contract detected: {target_contract_address}')
                try:
                    # Execute the purchase of the token
                    send_portal_transaction()
                except Exception as error:
                    print(f'Error during token purchase: {error}')
            else:
                print(parsed_data)

# Check if the contract already exists, otherwise monitor for its creation
if not check_if_contract_exists():
    asyncio.get_event_loop().run_until_complete(monitor_token_creation())
