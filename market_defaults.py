COINS = {'BTC':'bitcoin', 'ETH':'ethereum', 'USDC':'usd-coin', 'USDT':'tether', 'SOL':'solana', 'DOGE':'dogecoin'}

def empty_market():
    return {'frequency':'daily', 'lastAttempt':None, 'lastSuccess':None, 'errors':[], 'prices':{}, 'fx':{}}
