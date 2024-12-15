from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col
from pyspark.sql.types import StructType, StringType, StructField
import os
from influxdb_client import InfluxDBClient, Point, WriteOptions

# Retrieve environment variables
kafka_bootstrap_servers = os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'my-cluster-kafka-bootstrap:9092')

influx_url = os.environ.get('INFLUXDB_URL', 'url')
influx_token = os.environ.get('INFLUXDB_TOKEN', 'your-token')
influx_org = os.environ.get('INFLUXDB_ORG', 'my-org')
influx_bucket = os.environ.get('INFLUXDB_BUCKET', 'my-bucket')
influx_measurement = os.environ.get('INFLUXDB_MEASUREMENT', 'stock_measurements')

# Initialize Spark Session
spark = SparkSession.builder \
    .appName("KafkaToInflux") \
    .getOrCreate()

print("Spark Session Created")

import requests

def test_influxdb_connection():
    try:
        response = requests.get(f"{influx_url}/health")
        if response.status_code == 200:
            print(f"InfluxDB is healthy: {response.json()}")
        else:
            print(f"Failed to connect to InfluxDB. Status code: {response.status_code}")
    except Exception as e:
        print(f"Error connecting to InfluxDB: {e}")

# Run the test
test_influxdb_connection()


# Kafka Data Schema for 'value'
message_schema = StructType([
    StructField("symbol", StringType(), True),            # Cryptocurrency symbol
    StructField("timestamp", StringType(), True),         # Timestamp of the data
    StructField("rank", StringType(), True),              # Rank of the cryptocurrency
    StructField("priceUsd", StringType(), True),          # Price in USD
    StructField("marketCapUsd", StringType(), True),      # Market cap in USD
    StructField("volumeUsd24Hr", StringType(), True),     # 24-hour volume in USD
    StructField("changePercent24Hr", StringType(), True), # Percentage change in 24 hours
    StructField("vwap24Hr", StringType(), True),          # Volume-weighted average price in 24 hours
    StructField("supply", StringType(), True),            # Supply
    StructField("maxSupply", StringType(), True)          # Max supply
])

# Read from Kafka
df = spark.readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", kafka_bootstrap_servers) \
    .option("subscribe", "stock-data") \
    .load()
 
# Parse the 'key' (symbol) and 'value' (JSON payload)
df_parsed = df.select(
    col("key").cast("string").alias("symbol_key"),  # Rename the key to avoid conflict
    from_json(col("value").cast("string"), message_schema).alias("data")
).select("symbol_key", "data.*")  # Flatten the structure

# df_parsed.printSchema()
# df_parsed.writeStream.format("console").outputMode("append").start().awaitTermination()

# Transform the data
df_transformed = df_parsed.select(
    col("symbol"),  # Use the Kafka key as the main symbol
    col("timestamp"),
    col("rank").cast("int"),
    col("priceUsd").cast("double"),
    col("marketCapUsd").cast("double"),
    col("volumeUsd24Hr").cast("double"),
    col("changePercent24Hr").cast("double"),
    col("vwap24Hr").cast("double"),
    col("supply").cast("double"),
    col("maxSupply").cast("double")
)

# df_transformed.printSchema()
# df_transformed.writeStream.format("console").outputMode("append").start().awaitTermination()

# Write to InfluxDB
def write_to_influx(batch_df, batch_id):
    print(f"Processing batch {batch_id} with {batch_df.count()} records")

    # Collect records and print them for debugging
    records = batch_df.collect()
    for record in records:
        print(f"Writing record to InfluxDB: {record}")

    if len(records) == 0:
        print(f"No records in batch {batch_id}, skipping")
        return

    try:
        with InfluxDBClient(url=influx_url, token=influx_token, org=influx_org) as client:
            write_api = client.write_api(write_options=WriteOptions(batch_size=20, flush_interval=20))
            points = []
            for row in records:
                if row["symbol"]:  # Ensure 'symbol' is not null
                    p = (
                        Point(influx_measurement)
                        .tag("symbol", row["symbol"])
                        .field("rank", row["rank"] or 0)
                        .field("priceUsd", row["priceUsd"] or 0.0)
                        .field("marketCapUsd", row["marketCapUsd"] or 0.0)
                        .field("volumeUsd24Hr", row["volumeUsd24Hr"] or 0.0)
                        .field("changePercent24Hr", row["changePercent24Hr"] or 0.0)
                        .field("vwap24Hr", row["vwap24Hr"] or 0.0)
                        .field("supply", row["supply"] or 0.0)
                        .field("maxSupply", row["maxSupply"] or 0.0)
                        .time(row["timestamp"])
                    )
                    points.append(p)

            # Debug before writing to InfluxDB
            print(f"Points being written to InfluxDB: {points}")
            write_api.write(bucket=influx_bucket, org=influx_org, record=points)
        print(f"Batch {batch_id} successfully written to InfluxDB")
    except Exception as e:
        print(f"Error writing to InfluxDB for batch {batch_id}: {e}")

# Start Streaming Query
query = df_transformed.writeStream \
    .foreachBatch(write_to_influx) \
    .option("checkpointLocation", "/tmp/checkpoints") \
    .start()

query.awaitTermination()
