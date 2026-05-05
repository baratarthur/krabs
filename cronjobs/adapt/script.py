import os
import requests
import sys
import numpy as np
from sklearn.linear_model import LinearRegression

# Configurações via Environment Variables
APP_CICLE = int(os.getenv('APP_CICLE', 3))
TARGET_APP = os.getenv('TARGET', 'social-media-app')
# Usando a URL que você mencionou anteriormente ou o serviço interno
TELEMETRY_URL = os.getenv('TELEMETRY_URL', 'http://krabs-service:5002/telemetry')
CLUSTER_NAME = os.getenv('CLUSTER_NAME', 'unknown')

def fetch_data(url, params):
    try:
        response = requests.get(url, params=params, verify=False, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Erro de conexão ao buscar dados ({params.get('type')}): {e}")
        return None

def main():
    # 1. Busca dados de Uso do Cluster
    usage_params = {'type': 'usage', 'minutes': APP_CICLE, 'target': CLUSTER_NAME}
    cluster_usage = fetch_data(TELEMETRY_URL, usage_params)
    
    # 2. Busca dados de Latência
    latency_params = {'type': 'latency', 'minutes': APP_CICLE, 'target': TARGET_APP}
    app_latency = fetch_data(TELEMETRY_URL, latency_params)

    # Validação Crítica: Se a API falhou ou retornou lista vazia
    if not app_latency:
        print(f"Aviso: Nenhuma latência encontrada para '{TARGET_APP}' nos últimos {APP_CICLE} min. Encerrando ciclo.")
        return # Sai graciosamente para o CronJob tentar na próxima vez

    print(f"Dados recebidos: {len(app_latency)} registros de latência.")

    # 3. Processamento de Dados
    # Ordenar por criação (mais antigo para o mais novo para ver a tendência)
    app_latency.sort(key=lambda x: x['created_at'])
    
    try:
        # Extração de valores garantindo que sejam numéricos
        y = np.array([float(latency.get("value", 0)) for latency in app_latency])
        # X precisa ser 2D para o sklearn: [[0], [1], [2]...]
        X = np.arange(len(y)).reshape(-1, 1)

        # 4. Modelo de Regressão
        if len(y) < 2:
            print("Dados insuficientes para calcular tendência (mínimo 2 pontos).")
            return

        model = LinearRegression()
        model.fit(X, y)
        slope = model.coef_[0]

        print(f"Tendência da Latência (Slope): {slope:.4f}")

        if slope > 0.5: # Threshold opcional para evitar alarmes falsos por ruído
            print("ALERTA: Latência em subida consistente.")
        elif slope < -0.5:
            print("INFO: Latência em queda.")
        else:
            print("ESTÁVEL: Latência sem variações significativas.")

    except Exception as e:
        print(f"Erro ao processar modelo matemático: {e}")

if __name__ == "__main__":
    main()