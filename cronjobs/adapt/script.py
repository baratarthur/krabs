import os
import requests
import sys
import numpy as np
from sklearn.linear_model import LinearRegression

APP_CICLE = int(os.getenv('APP_CICLE', 3))
TARGET_APP = os.getenv('TARGET', 'social-media-app')
TELEMETRY_URL = os.getenv('TELEMETRY_URL', 'http://krabs-service:5002/telemetry')
CLUSTER_NAME = os.getenv('CLUSTER_NAME', 'unknown')
CLUSTERS_URL = os.getenv('CLUSTERS_URL', 'http://krabs-service:5002/clusters')
CURRENT_CLUSTER_INFO_URL = os.getenv('CLUSTER_INFO_URL', f'http://krabs-service:5002/clusters/{CLUSTER_NAME}')
APP_INFO_URL = os.getenv('APP_INFO_URL', f'http://krabs-service:5002/applications/{TARGET_APP}')
LATENCY_CHECK_URL = lambda ip: f'http://{ip}:30001/check-latency'

def fetch_data(url, params, body=None):
    try:
        if body is not None:
            response = requests.post(url, params=params, json=body, verify=False, timeout=10)
        else:
            response = requests.get(url, params=params, verify=False, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Erro de conexão ao buscar dados ({params.get('type')}): {e}")
        return None

def main():
    latency_params = {'type': 'latency', 'minutes': APP_CICLE, 'target': TARGET_APP}
    app_latency = fetch_data(TELEMETRY_URL, latency_params)

    if not app_latency:
        print(f"Aviso: Nenhuma latência encontrada para '{TARGET_APP}' nos últimos {APP_CICLE} min. Encerrando ciclo.")
        return

    print(f"Dados recebidos: {len(app_latency)} registros de latência.")

    app_latency.sort(key=lambda x: x['created_at'])
    
    try:
        y = np.array([float(latency.get("value", 0)) for latency in app_latency])
        X = np.arange(len(y)).reshape(-1, 1)

        if len(y) < 2:
            print("Dados insuficientes para calcular tendência (mínimo 2 pontos).")
            return

        model = LinearRegression()
        model.fit(X, y)
        slope = model.coef_[0]

        print(f"Tendência da Latência (Slope): {slope:.4f}")

        current_app_info = fetch_data(APP_INFO_URL, params={})
        print(f"Config atual da aplicação '{TARGET_APP}': {current_app_info}")

        if slope > 0.5:
            print("INFO: Latência subindo.")
            current_cluster = fetch_data(CURRENT_CLUSTER_INFO_URL, params={})
            clusters = fetch_data(CLUSTERS_URL, params={})
            ips = [cluster['ip_address'] for cluster in clusters if cluster['name'] != CLUSTER_NAME]
            latency_checks = fetch_data(LATENCY_CHECK_URL(current_cluster['ip_address']), params={}, body={"targets": ips})
            print(f"Latências para outros clusters: {latency_checks}")
        elif slope < -0.5:
            print("INFO: Latência em queda.")

    except Exception as e:
        print(f"Erro ao processar modelo matemático: {e}")

if __name__ == "__main__":
    main()