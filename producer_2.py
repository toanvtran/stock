from confluent_kafka import Producer
import json
import time
import requests
from datetime import datetime

# Kafka configuration
KAFKA_BOOTSTRAP_SERVERS = "my-cluster-kafka-bootstrap:9092"
TOPIC = "crypto-ohlcv-data"  # Topic for OHLCV data

# Producer configuration
producer_config = {
    'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS,
    'client.id': 'python-crypto-ohlcv-producer',
}

# Function to fetch OHLCV data from CoinCap API
def fetch_ohlcv_data(symbol, interval='1d', limit=5):
    """
    Fetch historical OHLCV data from CoinCap.
    
    :param symbol: The cryptocurrency symbol (e.g., 'bitcoin', 'ethereum')
    :param interval: The time interval (e.g., '1h' for hourly, '1d' for daily)
    :param limit: The number of data points to fetch
    :return: List of OHLCV data (open, high, low, close, volume)
    """
    url = f"https://api.coincap.io/v2/assets/{symbol}/history"
    params = {
        'interval': interval,  # Time interval (1d, 1h, etc.)
        'limit': limit  # Number of data points to retrieve
    }
    
    response = requests.get(url, params=params)
    
    if response.status_code == 200:
        data = response.json()
        return data['data']
    else:
        print(f"Failed to fetch data from CoinCap for {symbol}: {response.status_code}")
        return []

def delivery_report(err, msg):
    if err is not None:
        print(f"Message delivery failed: {err}")
    else:
        print(f"Message delivered to {msg.topic()} [{msg.partition()}]")

def produce_ohlcv_data():
    """
    Produces OHLCV data to a Kafka topic.
    """
    producer = Producer(producer_config)

    try:
        # List of symbols to track (You can add more cryptocurrencies here)
        symbols = ['bitcoin', 'ethereum']  # Example: bitcoin, ethereum, litecoin
        
        while True:
            for symbol in symbols:
                ohlcv_data = fetch_ohlcv_data(symbol)  # Fetch OHLCV data for each symbol
                
                for data in ohlcv_data:
                    timestamp = datetime.fromtimestamp(int(data['time'] / 1000)).isoformat()  # Convert timestamp to ISO format
                    message = {
                        'symbol': symbol,
                        'timestamp': timestamp,
                        'open': float(data['open']),
                        'high': float(data['high']),
                        'low': float(data['low']),
                        'close': float(data['close']),
                        'volume': float(data['volume'])
                    }
                    
                    # Send the message to Kafka
                    producer.produce(TOPIC, key=symbol, value=json.dumps(message), callback=delivery_report)
                    producer.poll(0)  # Poll the producer for delivery events
                    print(f"Produced: {message}")
                
            time.sleep(60)  # Delay between fetching data (e.g., fetch every 60 seconds)
            producer.flush()

    except Exception as e:
        print(f"Producer error: {e}")
    finally:
        producer.flush()  # Ensure all messages are sent before exiting

if __name__ == "__main__":
    produce_ohlcv_data()