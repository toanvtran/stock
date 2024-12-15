## Prerequisite

### Linux:
- `minikube`
- `kvm2`
- `cri-o` \
(see https://minikube.sigs.k8s.io/docs/start/?arch=%2Flinux%2Fx86-64%2Fstable%2Fbinary+download)
- `helm`
- `k9s`

## Start

```
minikube delete
minikube start --cpus 7 --memory 8192 --container-runtime=cri-o --addons=metrics-server --driver=kvm2
```
## Kafka
```
kubectl create namespace kafka
kubectl create -f 'https://strimzi.io/install/latest?namespace=kafka' -n kafka
```
Wait until up and running

```
kubectl apply -f kafka/kafka_1.yaml -n kafka
```
Wait until up and running

### Producer
```
kubectl apply -f kafka/producer-deployment.yaml -n kafka 
```

## Influxdb
```
kubectl create namespace influxdb 
kubectl apply -f spark_to_influxdb/influxdb-deployment.yaml -n influxdb
kubectl apply -f spark_to_influxdb/influxdb-service.yaml -n influxdb
```
Wait until up and running

Get url and token:
```
# Get Node IP
NODE_IP=$(kubectl get nodes -o jsonpath='{.items[0].status.addresses[?(@.type=="InternalIP")].address}')
NODE_PORT=32086
INFLUXDB_URL="http://${NODE_IP}:${NODE_PORT}"

# Get Pod Name
POD_NAME=$(kubectl get pods -n influxdb -l app=influxdb -o jsonpath='{.items[0].metadata.name}')

# Get Token
TOKEN=$(kubectl exec -n influxdb $POD_NAME -- influx auth list --json | jq -r '.[0].token')

echo "InfluxDB URL: $INFLUXDB_URL"
echo "InfluxDB Token: $TOKEN"
```

Access influxdb in `$INFLUXDB_URL` with username `admin` and password `password123`. (this is optional)

Paste `$INFLUXDB_URL` to `INFLUXDB_URL` field in `spark_to_influxdb/spark-streaming-deployment.yaml`.

## Spark Streaming to Influxdb

```
kubectl apply -f spark_to_influxdb/spark-streaming-deployment.yaml -n kafka
```

Wait until writing data into influxdb. (see in `k9s`)

## Grafana

```
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update

helm install grafana grafana/grafana --namespace monitoring --create-namespace
```

Get Grafana password:

```
kubectl get secret --namespace monitoring grafana -o jsonpath="{.data.admin-password}" | base64 --decode ; echo
```

Use this password and username `admin` to access Grafana with:
```
export POD_NAME=$(kubectl get pods --namespace monitoring -l "app.kubernetes.io/name=grafana,app.kubernetes.io/instance=grafana" -o jsonpath="{.items[0].metadata.name}")
kubectl --namespace monitoring port-forward $POD_NAME 3000
```

In Grafana / connections / data sources, choose `Add data source`. Choose `Influxdb`. Choose `flux` as query language, type in `$INFLUX_URL` as URL, turn on `basic auth`, and type in `basic auth` `username` and `password` of Influxdb.

Type in `my-org` for organization, `my-influxdb-token` for token, and `my-bucket` for default bucket.

Press `Save & Test`

Build a dashboard with this query for testing:
```
from(bucket: "my-bucket")
|> range(start: -1h)
|> filter(fn: (r) => r["_measurement"] == "stock_measurements")
|> filter(fn: (r) => r["_field"] == "priceUsd")
|> filter(fn: (r) => r["symbol"] == "bitcoin") 
```

## batch layer

```
kubectl create -f spark_to_minio/minio-pvc.yaml -n batch
kubectl create -f spark_to_minio/minio-deployment.yaml -n batch
kubectl create -f spark_to_minio/tminio-service.yaml -n batch
kubectl apply -f spark_to_minio/checkpoint-pvc.yaml -n batch
```

Access minio WebUI at `http://<minikube-ip>:9001` (same ip for accessing influxdb) with username `minio` and password `minio123`

Create a bucket, type in `your-bucket` as name.

Run Spark Streaming job for writing data into minio:
```
kubectl apply -f spark_to_minio/spark-streaming-deployment.yaml
```

See data in minio WebUI at `Object browser`.