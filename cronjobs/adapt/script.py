import os
import requests
import sys
import time
from sklearn.linear_model import LinearRegression
import numpy as np

APP_CICLE = 3 # em minutos

target_app = os.getenv('TARGET', 'localhost')
target_app_ip = os.getenv('TARGET_IP', '0.0.0.0:5002')
cluster_name = os.getenv('CLUSTER_NAME', 'unknown')

def fetch_data(url):
    try:
        response = requests.get(url, verify=False) 
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Erro de conexão ao buscar dados: {e}")
        return None

cluster_usage = fetch_data(f"http://krabs-service:5002/telemetry?type=usage&minutes={APP_CICLE}&target={cluster_name}")
if cluster_usage is None:
    print("Falha ao obter dados do cluster. Encerrando.")
    sys.exit(1)

app_latency = fetch_data(f"http://krabs-service:5002/telemetry?type=latency&minutes={APP_CICLE}&target={target_app}")
if app_latency is None:
    print("Falha ao obter dados de latência. Encerrando.")
    sys.exit(1)

app_latency.sort(key=lambda x: x['created_at'], reverse=True)
app_latency_sorted_by_creation = np.array([int(latency.get("value", "0")) for latency in app_latency])
cluster_order = np.array([[i] for i in range(len(app_latency))])
model = LinearRegression()
model.fit(cluster_order, app_latency_sorted_by_creation)

slope = model.coef_[0]

if slope > 0:
    print("Latência aumentando, sinal de que o cluster pode estar sobrecarregado. Considerar reduzir carga ou escalar.")
elif slope < 0:
    print("Latência diminuindo, sinal de que o cluster pode estar subutilizado.")
else:
    print("Latência estável.")

# if current cluster is occupied, send telemetry to app to reduce load
# all_clusters = fetch_data("http://krabs-service:5002/clusters")
# if all_clusters is None:
#     print("Falha ao obter lista de clusters. Encerrando.")
#     sys.exit(1)