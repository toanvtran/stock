from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col
from pyspark.sql.types import StructType, StringType, StructField
import os
import sys

# Optional: Configure Python to flush print statements immediately
# This ensures that logs are output in real-time
import sys
sys.stdout.flush()

# Retrieve environment variables with default values
kafka_bootstrap_servers = os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'my-cluster-kafka-bootstrap:9092')

minio_endpoint = os.environ.get('MINIO_ENDPOINT', 'http://minio.lambda-architecture.svc.cluster.local:9000')
minio_access_key = os.environ.get('MINIO_ACCESS_KEY', 'youraccesskey')
minio_secret_key = os.environ.get('MINIO_SECRET_KEY', 'yoursecretkey')
minio_bucket = os.environ.get('MINIO_BUCKET', 'your-bucket')
checkpoint_location = os.environ.get('CHECKPOINT_LOCATION', 's3a://your-bucket/checkpoints/')

print("Starting Spark Streaming Application")
print(f"Kafka Bootstrap Servers: {kafka_bootstrap_servers}")
print(f"MinIO Endpoint: {minio_endpoint}")
print(f"MinIO Bucket: {minio_bucket}")
print(f"Checkpoint Location: {checkpoint_location}")

# Initialize Spark Session
print("Initializing Spark Session...")
spark = SparkSession.builder \
    .appName("KafkaToMinIO") \
    .getOrCreate()

print("Spark Session Created")

# Define the schema for the incoming Kafka messages
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

print("Defined message schema for Kafka data")

# Read from Kafka
print("Starting to read from Kafka...")
df = spark.readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", kafka_bootstrap_servers) \
    .option("subscribe", "stock-data") \
    .load()

print("Successfully connected to Kafka and started reading data")

# Parse the 'key' (symbol) and 'value' (JSON payload)
print("Parsing Kafka messages...")
df_parsed = df.select(
    col("key").cast("string").alias("symbol_key"),  # Rename the key to avoid conflict
    from_json(col("value").cast("string"), message_schema).alias("data")
).select("symbol_key", "data.*")  # Flatten the structure

print("Successfully parsed Kafka messages")

# Transform the data
print("Transforming data...")
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

print("Data transformation complete")

# Configure S3 (MinIO) access
print("Configuring Hadoop S3A settings for MinIO...")
spark._jsc.hadoopConfiguration().set("fs.s3a.endpoint", minio_endpoint)
spark._jsc.hadoopConfiguration().set("fs.s3a.access.key", minio_access_key)
spark._jsc.hadoopConfiguration().set("fs.s3a.secret.key", minio_secret_key)
spark._jsc.hadoopConfiguration().set("fs.s3a.path.style.access", "true")
spark._jsc.hadoopConfiguration().set("fs.s3a.connection.ssl.enabled", "false")
spark._jsc.hadoopConfiguration().set("fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
spark._jsc.hadoopConfiguration().set("com.amazonaws.services.s3.enableV4", "true")
spark._jsc.hadoopConfiguration().set("fs.s3a.aws.credentials.provider", "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider")

print("Hadoop S3A configuration for MinIO set successfully")

# Write to MinIO
print(f"Starting to write data to MinIO bucket: {minio_bucket}/stock-data/")
query = df_transformed.writeStream \
    .format("parquet") \
    .option("path", f"s3a://{minio_bucket}/stock-data/") \
    .option("checkpointLocation", checkpoint_location) \
    .outputMode("append") \
    .start()

print("Write stream started successfully")

# Await termination
print("Awaiting termination of the streaming query...")
try:
    query.awaitTermination()
except KeyboardInterrupt:
    print("Streaming query terminated by user")
except Exception as e:
    print(f"Streaming query terminated with exception: {e}")
finally:
    spark.stop()
    print("Spark Session stopped")
