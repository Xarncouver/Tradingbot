nfrom binance import Client
from binance.enums import *
import websocket, pprint, json, smtplib, math
import config


# Binance CLient API Setup:
client = Client(config.apikey, config.apiSecurity)


# Global Variables:
ws_1_candle_close = []
ma_ready = False
ma_period_short = config.ma_period_short
ma_period_long = config.ma_period_long
ma_long_list = []
trade_symbol = config.trade_symbol_1
interval = config.interval
assets_to_trade = 100 - config.percentage_assets_to_trade
completed_trades = 0
order_details = []


# check if we are in an open position
def open_order(): 
    trades = client.get_my_trades(symbol= trade_symbol)
    last_trade = trades[-1]
    last_trade_buy = last_trade['isBuyer']
    if last_trade_buy:
        return True
    else:
        return False


#get available assets to trade:
def max_trade_amount():
    global assets_to_trade
    asset_1_balance = client.get_asset_balance(asset= config.asset_1)
    asset_1_avail = int(math.floor(float(asset_1_balance["free"])))

    asset_2_balance = client.get_asset_balance(asset=config.asset_2)
    asset_2_avial = float(asset_2_balance["free"])

    all_symbols_price = client.get_symbol_ticker()
    for dict in all_symbols_price:
        if dict['symbol'] == config.asset_1 + config.asset_2:
            asset_1_price = float(dict['price'])

    if open_order():
        return asset_1_avail
    else:
        return math.floor((asset_2_avial / asset_1_price) - ((asset_2_avial / asset_1_price) / 100) * assets_to_trade)




# Websocket for live data stream:
socket_1 = "wss://stream.binance.com:9443/ws/{}@kline_15m".format(trade_symbol.lower())
socket_2 = "wss://stream.binance.com:9443/ws/dogebtc@kline_1m"
print('Connecting to stream: ' + socket_1)

# Get historical klines data:
hist_candles = client.get_historical_klines(trade_symbol.upper(), Client.KLINE_INTERVAL_15MINUTE, "21 days ago UTC")
for candle in hist_candles:  # Separate the closes from historical klines
    ws_1_candle_close.append(candle[4])


# Calculate moving average for a set period:
def moving_average(ma_period):
    period_close = ws_1_candle_close[-ma_period:]
    close_sum = 0.0
    if len(ws_1_candle_close) > ma_period:
        for n in period_close:
            close_sum += float(n)
        ma = float(close_sum / ma_period)
        ma_ready = True
        return ma
    else:
        ma_ready = False
        return 'Insufficient data to calculate Moving Average!'

# Order execute function:
def order(symbol, side, quantity, order_type=ORDER_TYPE_MARKET):
    global order_details
    try:
        print("Sending order")
        order = client.create_order(symbol=symbol, side=side, quantity=quantity, type=order_type)
        print(order)
        order_details = order
    except Exception as e:
        print(e)
        return False
    return True


# Email Server Setup for bot notifications:
def send_email(buy_or_sell):
    email_server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
    email_server.login(config.email, config.email_pass)

    email_subject = "Tradebot Update: {} Order".format(buy_or_sell)
    email_body = 'Order detials: {}'.format(order_details)
    email_msg = 'Subject: {} \n\n{}'.format(email_subject, email_body)
    email_server.sendmail(config.email, 'wimpie.jjw2@gmail.com', email_msg)


def on_open(ws_1):                # Message on connection to socket
    print("Connected!")

def on_close(ws_1):               # Message on disconnect from socket
    print('Connection Closed!')

def on_message(ws_1, message_1):  # Define what happens everytime a reply from the server is received
    global open_order, completed_trades, trade_symbol, trade_quantity, ma_long_list
    ws_1_message_json = json.loads(message_1)
    #pprint.pprint(ws_1_message_json['k'])
    ws_1_candle = ws_1_message_json['k']
    ws_1_close = ws_1_candle['c']
    ws_1_is_closed = ws_1_candle['x']
    token_symbol = ws_1_candle['s']
    last_close = 0.0
    order_price = last_close      # Price on order execution
    ma_long_list.append(ma_period_long)

    if ws_1_is_closed:
        ws_1_candle_close.append(ws_1_close)
        last_close = float(ws_1_candle_close[-1])


        # Buy condition logic:
        if len(ma_long_list) >= 3:
            if (last_close > moving_average(ma_period_long) < moving_average(ma_period_short)) and (
                ma_long_list[-1] > ma_long_list[-2] > ma_long_list[-3]
            ):
                if not open_order():
                    # execute buy order logic:
                    order_placed = order(trade_symbol, SIDE_BUY, trade_quantity)
                    if order_placed:
                        send_email("Buy")
                        print("$$$ Buy Order Executed!!! $$$")
                        # config.open_order = True
                        print(order_placed)
                    else:
                        print(
                            """==================================================\n
                            Buy condition met but could not place buy order!!!\n
                            ==================================================""")
                else:
                    # config.open_order = True
                    print(
                        '''================================================\n
                        Buy conditions met, but already in open position\n
                        ================================================''')


        # Sell condition logic:
        if last_close < moving_average(ma_period_long) > moving_average(ma_period_short):
            if open_order():
                # execute sell order logic:
                order_sold = order(trade_symbol, SIDE_SELL, trade_quantity)

                if order_sold:
                    send_email("Sell")
                    #config.open_order = False
                    completed_trades += 1
                    print("$$$ Sell Order Executed!!! $$$")
                    print(order_sold)

        # Print debug info:
        print("\nCoin Pair: " + token_symbol)
        print("Max assets to trade: {}".format(max_trade_amount()))
        # pprint.pprint('{} closes: {}'.format(token_symbol, ws_1_candle_close[-ma_period_long :]))
        print(ma_period_long, "Period Moving Average: {0:.16f}".format(moving_average(ma_period_long)))
        print(ma_period_short, "Period Moving Average: {0:.16f}".format(moving_average(ma_period_short)))
        print('Current closing price: {0:.16f}'.format(last_close))
        print('Open order: ' + str(open_order()))
        print('Completed Trades: ' + str(completed_trades) + '\n')


# Starting websocket:
ws_1 = websocket.WebSocketApp(socket_1, on_open=on_open, on_close=on_close, on_message=on_message)
ws_1.run_forever()

















