import os
from urllib import response
import requests
import sys
import time

APP_CICLE = int(os.getenv('APP_CICLE', 3))
TARGET_APP = os.getenv('TARGET', 'social-media-app')
TELEMETRY_URL = os.getenv('TELEMETRY_URL', 'http://krabs-service:5002/telemetry')
CLUSTER_NAME = os.getenv('CLUSTER_NAME', 'unknown')
CLUSTERS_URL = os.getenv('CLUSTERS_URL', 'http://krabs-service:5002/clusters')
CURRENT_CLUSTER_INFO_URL = os.getenv('CLUSTER_INFO_URL', f'http://krabs-service:5002/clusters/{CLUSTER_NAME}')
APP_INFO_URL = os.getenv('APP_INFO_URL', f'http://krabs-service:5002/applications/{TARGET_APP}')
LATENCY_CHECK_URL = lambda ip: f'http://{ip}:30003/check-latency'
POD_CREATOR_URL = lambda ip: f'http://{ip}:30001'
LATENCY_TRESHOLD = int(os.getenv('LATENCY_THRESHOLD', 200))
LOW_LATENCY_TRESHOLD = int(os.getenv('LOW_LATENCY_THRESHOLD', 100))
CONFIG = 4

def fetch_data(url, params):
    try:
        response = requests.get(url, params=params, verify=False, timeout=45)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Erro de conexão ao buscar dados ({params.get('type')}): {e}")
        return None
    
def create_data(url, body):
    try:
        response = requests.post(url, json=body, verify=False, timeout=45)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.JSONDecodeError:
        print(f"Aviso: O recurso foi criado, mas a resposta não era JSON. Resposta: {response.text}")
        return {"status": "sucesso", "texto": response.text}
        
    except requests.exceptions.RequestException as e:
        print(f"Erro de conexão ao criar recurso: {e}")
        return None
    
def update_data(url, body):
    try:
        response = requests.put(url, json=body, verify=False, timeout=45)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Erro de conexão ao atualizar recurso: {e}")
        return None

def main():
    latency_params = {'type': 'latency', 'minutes': APP_CICLE, 'target': TARGET_APP}
    app_latency = fetch_data(TELEMETRY_URL, latency_params)

    if not app_latency:
        print(f"Aviso: Nenhuma latência encontrada para '{TARGET_APP}' nos últimos {APP_CICLE} min. Encerrando ciclo.")
        return

    print(f"Dados recebidos: {len(app_latency)} registros de latência.")
    
    try:
        high_latency_counter = sum(1 for entry in app_latency if int(entry['value']) > LATENCY_TRESHOLD)
        low_latency_counter = sum(1 for entry in app_latency if int(entry['value']) < LOW_LATENCY_TRESHOLD)

        print(f"Contador de Alta Latência: {high_latency_counter}")
        print(f"Contador de Baixa Latência: {low_latency_counter}")

        current_app_info = fetch_data(APP_INFO_URL, params={})
        print(f"Config atual da aplicação '{TARGET_APP}': {current_app_info}")

        if high_latency_counter > (0.5 * len(app_latency)):
            print("INFO: Latência subindo.")
            current_cluster = fetch_data(CURRENT_CLUSTER_INFO_URL, params={})
            # clusters = fetch_data(CLUSTERS_URL, params={})
            # ips = [cluster['ip_address'] for cluster in clusters]
            # latency_checks = fetch_data(LATENCY_CHECK_URL(current_cluster['ip_address']), params={}, body={"targets": ips})
            # latency_checks.sort(key=lambda x: x['latency_ms'])
            # print(f"Latências ordenadas: {latency_checks}")
            # next_cluster_ip = latency_checks[0]['ip_address']
            initial_port = 30300
            current_num_replicas = int(current_app_info['num_replicas'])
            num_replicas = 2 if current_num_replicas < 2 else current_num_replicas + 1
            initial_name = f'dana-remote-{TARGET_APP}'
            namespace = f"{initial_name}-ns-{num_replicas}-replicas" # different namespaces for each number of replicas to avoid conflicts
            remotes = []
            create_data(f'{POD_CREATOR_URL(current_cluster["ip_address"])}/namespaces', body={"name": namespace})
            print(f"Namespace criado: {namespace}")

            for i in range(num_replicas):
                new_remote = {
                    "pod_name": f'{initial_name}-{i}',
                    "namespace": namespace,
                    "image_name": "my.private-registry.lan:5000/dana-remote:latest",
                    "app_port": initial_port + (10*num_replicas) + i, # unique port for each replica according to number of total replicas to avoid conflicts
                }
                create_data(f'{POD_CREATOR_URL(current_cluster["ip_address"])}/create-pod', body=new_remote)
                print(f"Solicitação de criação de pod enviada: {new_remote}")
                remotes.append({"address": current_cluster['ip_address'], "port": new_remote['app_port']})

            time.sleep(30)
            print(f"Remotes criados: {remotes}")
            adaptation_url = f"http://{current_cluster['ip_address']}:{current_app_info['port']}/adapt/{CONFIG}"
            create_data(adaptation_url, body=remotes)
            print(f"App adaptado")
            update_data(APP_INFO_URL, body={"num_replicas": num_replicas, "config": CONFIG})

        elif low_latency_counter > (0.5 * len(app_latency)):
            print("INFO: Latência em queda.")

    except Exception as e:
        print(f"Erro ao processar modelo matemático: {e}")

if __name__ == "__main__":
    main()