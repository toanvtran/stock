start:
    minikube delete
    minikube start --cpus 7 --memory 16384 --container-runtime=cri-o --addons=metrics-server --driver=kvm2 

set up kafka:
    kubectl create namespace kafka
    kubectl create -f 'https://strimzi.io/install/latest?namespace=kafka' -n kafka
        (wait until up and running (e.g. see in k9s))
    kubectl apply -f kafka_1.yaml -n kafka
        (wait until up and running) 

set up producer
    kubectl apply -f producer-deployment.yaml -n kafka 

set up influxdb
    kubectl create namespace influxdb 
    kubectl apply -f influxdb-deployment.yaml -n influxdb
    kubectl apply -f influxdb-service.yaml -n influxdb

    get ip: minikube ip

    access influxdb: http://<ip>:32086
        username: admin
        password: password123

    go to load data / api tokens, generate api token (all access), copy (don't press "copy to clipboard", do it manually) and paste it into INFLUXDB_TOKEN in spark-streaming-deployment.yaml  (remember to save the token for later use)

    also paste http://<ip>:32086 to INFLUXDB_URL in spark-streaming-deployment.yaml
    
set up spark: 
  
    kubectl apply -f spark-streaming-deployment.yaml -n kafka
    (wait until writing data into influxdb)
 
set up grafana
    helm repo add grafana https://grafana.github.io/helm-charts
    helm repo update

    helm install grafana grafana/grafana --namespace monitoring --create-namespace

    get password: 
        kubectl get secret --namespace monitoring grafana -o jsonpath="{.data.admin-password}" | base64 --decode ; echo

    forward port and access (with username `admin`): 
        export POD_NAME=$(kubectl get pods --namespace monitoring -l "app.kubernetes.io/name=grafana,app.kubernetes.io/instance=grafana" -o jsonpath="{.items[0].metadata.name}")
        kubectl --namespace monitoring port-forward $POD_NAME 3000

    in connections/data sources, choose "add data source"

    choose influxdb
    
    choose flux as query language, type in influxdb_url, turn on basic auth, type in basic auth username and password (influxdb)

    type "my-org" for organization, the influxdb token before, and "my-bucket" for default bucket

    press save & test

    build a dashboard with this query for testing:
    ```
    from(bucket: "my-bucket")
    |> range(start: -1h)
    |> filter(fn: (r) => r["_measurement"] == "stock_measurements")
    |> filter(fn: (r) => r["_field"] == "priceUsd")
    |> filter(fn: (r) => r["symbol"] == "bitcoin") 

    ``` 