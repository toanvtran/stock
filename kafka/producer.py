from confluent_kafka import Producer
import json
import time, requests
from datetime import datetime

# Kafka configuration
KAFKA_BOOTSTRAP_SERVERS = "my-cluster-kafka-bootstrap:9092"
TOPIC = "stock-data"

# Producer configuration
producer_config = {
    'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS,
    'client.id': 'python-producer',
}

def delivery_report(err, msg):
    if err is not None:
        print(f"Message delivery failed: {err}")
    else:
        print(f"Message delivered to {msg.topic()} [{msg.partition()}]")

def fetch_ohlcv_data(symbol, interval='1m', limit=20):
    """
    Fetch historical OHLCV data from CryptoWatch.

    :param exchange: The exchange (e.g., 'binance')
    :param pair: The trading pair (e.g., 'btcusdt')
    :param period: The time period (e.g., 3600 for 1-hour)
    :param limit: The number of data points to fetch
    :return: List of OHLCV data (open, high, low, close, volume)
    """

    api_key = '1e177e4c-bc22-4b93-af52-a317d046880e'
    # Base URL for CoinCap API
    url = f'https://api.coincap.io/v2/assets'

    # Headers with authentication
    headers = {
        'Authorization': f'Bearer {api_key}'
    }

    # Send the GET request
    params = {
        'interval': interval,  # Time interval (1d, 1h, etc.)
        'limit': limit  # Number of data points to retrieve
    }
    response = requests.get(url, headers = headers, params=params)

    if response.status_code == 200:
        data = response.json()
        return data['data']
    else:
        print(f"Failed to fetch data from CoinCap for {symbol}: {response.status_code}")
        return []
    
def produce_stock_data():
    """
    Produces stock data to a Kafka topic.
    """
    producer = Producer(producer_config)

    try: 
        while True: 
            ohlcv_data = fetch_ohlcv_data(0)
            for data in ohlcv_data:
                timestamp = datetime.now().isoformat()  # Convert timestamp to ISO format
                message = {
                    'symbol': data['id'],
                    'timestamp': timestamp,
                    'rank': data['rank'],
                    'priceUsd': data['priceUsd'],
                    'marketCapUsd': data['marketCapUsd'],
                    'volumeUsd24Hr': data['volumeUsd24Hr'],
                    'changePercent24Hr': data['changePercent24Hr'],
                    'vwap24Hr': data['vwap24Hr'],
                    'supply': data['supply'],
                    'maxSupply': data['maxSupply']
                }
                # Send the message
                producer.produce(TOPIC, key=message['symbol'], value=json.dumps(message), callback=delivery_report)
                producer.poll(0)  # Poll the producer for delivery events
                print(f"Produced: {message}")
                
            time.sleep(60)
            producer.flush()
    except Exception as e:
        print(f"Producer error: {e}")
    finally:
        producer.flush()  # Ensure all messages are sent before exiting

if __name__ == "__main__":
    produce_stock_data()

 