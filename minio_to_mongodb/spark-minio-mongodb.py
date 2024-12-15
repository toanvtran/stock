from pyspark.sql import SparkSession
import os
 

# MinIO configuration
minio_endpoint = os.environ.get('MINIO_ENDPOINT', 'http://minio-service.batch.svc.cluster.local:9000')
minio_bucket = os.environ.get('MINIO_BUCKET', 'your-bucket')
minio_access_key = os.environ.get('MINIO_ACCESS_KEY', 'minio')
minio_secret_key = os.environ.get('MINIO_SECRET_KEY', 'minio123')

# MongoDB configuration 
mongo_database = os.environ.get('MONGO_DATABASE', 'your_database')  # Replace 'your_database' with your DB name
mongo_collection = os.environ.get('MONGO_COLLECTION', 'your_collection')  # Replace 'your_collection' with your collection name
mongo_user = os.environ.get('MONGO_USER', 'root')
mongo_password = os.environ.get('MONGO_PASSWORD', '') 
mongo_host = os.environ.get('MONGO_HOST', 'mongodb.mongodb.svc.cluster.local')
mongo_port = os.environ.get('MONGO_PORT', '27017')
mongo_uri = f"mongodb://{mongo_user}:{mongo_password}@{mongo_host}:{mongo_port}/?authSource=admin"

print("mongo pass", mongo_password)

spark = SparkSession.builder \
    .appName('MinIOToMongo') \
    .config("spark.mongodb.write.connection.uri", mongo_uri) \
    .getOrCreate()

print("Spark Session Created")

# Configure Spark for MinIO
spark._jsc.hadoopConfiguration().set("fs.s3a.endpoint", minio_endpoint)
spark._jsc.hadoopConfiguration().set("fs.s3a.access.key", minio_access_key)
spark._jsc.hadoopConfiguration().set("fs.s3a.secret.key", minio_secret_key)
spark._jsc.hadoopConfiguration().set("fs.s3a.path.style.access", "true")
spark._jsc.hadoopConfiguration().set("fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")

# Read data from MinIO
minio_path = f"s3a://{minio_bucket}/stock-data/"
df = spark.read.parquet(minio_path)

# Write data to MongoDB
df.write \
    .format("mongodb") \
    .option("uri", mongo_uri) \
    .option("database", mongo_database) \
    .option("collection", mongo_collection) \
    .mode("overwrite") \
    .save()

print("Data transfer completed successfully.")
spark.stop()
