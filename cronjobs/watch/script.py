import os
import requests
import sys
import time
from functools import reduce

# Pega variáveis de ambiente
target_cluster = os.getenv('TARGET', 'localhost')
target_cluster_ip = os.getenv('TARGET_IP', '0.0.0.0')
time_window_in_seconds = 20
frequency_of_measurement = (60 // time_window_in_seconds) - 1

# Define a URL (Verifique se o nome 'monitor-service' está correto no seu k8s)
if 'local' in target_cluster:
    monitor_service_url = "http://monitor-service-kube-prome-prometheus:9090/api/v1/query"
else:
    monitor_service_url = f"http://{target_cluster_ip}:30090/api/v1/query"

query_params = {
    "query": f'sum by (pod) (rate(container_cpu_usage_seconds_total[{time_window_in_seconds}s]))'
}

print(monitor_service_url)

def fetch_data(url, params):
    try:
        response = requests.get(url, params=params, verify=False, timeout=10)
        response.raise_for_status()
        return response.json() 
    except Exception as e:
        print(f"Erro de conexão ao buscar dados: {e}")
        return None

for _ in range(frequency_of_measurement):
    data = fetch_data(monitor_service_url, query_params)

    if data is None:
        print("Falha crítica: Não foi possível contatar o Prometheus.")
        sys.exit(1)

    try:
        print("data: ", data.get('data', {}))
        results = data.get('data', {}).get('result', [])
        
        if not results:
            print("Aviso: Query executada, mas o Prometheus não retornou dados de CPU.")
            sys.exit(0)
        
        cpu_value = reduce(lambda a, b: a + b, map(lambda obj: float(obj['value'][1]), results))
        
        print("Total cpu usage: ", cpu_value)

        telemetry = {
            "target": target_cluster,
            "type": "usage",
            "value": str(cpu_value),
            "cluster_name": target_cluster,
        }
        
        # Envia para o seu serviço Krabs
        print(f"Enviando telemetria: {telemetry}")
        post_res = requests.post(
            "http://krabs-service:5002/telemetry", 
            json=telemetry, 
            timeout=5
        )
        post_res.raise_for_status()
        print(f"Sucesso! Status: {post_res.status_code}")
    except Exception as e:
        print(f"Erro durante o processamento/envio: {e}")
        sys.exit(1)
    
    time.sleep(time_window_in_seconds)