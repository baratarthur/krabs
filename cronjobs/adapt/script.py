import os
from urllib import response
import requests
import time

TARGET_APP = os.getenv('TARGET', 'social-media-app')
CLUSTER_NAME = os.getenv('CLUSTER_NAME', 'unknown')

TELEMETRY_URL = 'http://krabs-service:5002/telemetry'
CLUSTERS_URL = 'http://krabs-service:5002/clusters'
CURRENT_CLUSTER_INFO_URL = f'http://krabs-service:5002/clusters/{CLUSTER_NAME}'
APP_INFO_URL = f'http://krabs-service:5002/applications/{TARGET_APP}'
LATENCY_RETREIVE_URL = lambda ip, port: f'http://{ip}:{port}/current-latency'
LATENCY_CHECK_URL = lambda ip: f'http://{ip}:30003/check-latency'
POD_CREATOR_URL = lambda ip: f'http://{ip}:30001'
TRESHOLD_LATENCY = 200 # ms
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
    app_info = fetch_data(APP_INFO_URL, params={})
    cluster_info = fetch_data(CURRENT_CLUSTER_INFO_URL, params={})
    if not app_info or not cluster_info:
        print("Não foi possível obter as informações da aplicação. Encerrando o processo de adaptação.")
        return
    
    app_latency = fetch_data(LATENCY_RETREIVE_URL(cluster_info['ip_address'], app_info['port']), params={})

    print(f"Informações da aplicação: {app_info}")
    print(f"Informações do cluster: {cluster_info}")
    print(f"Latência atual da aplicação: {app_latency['latency']} ms")

    try:
        last_latency = round(float(app_info['last_latency_check']), 2)
        current_latency = round(float(app_latency['latency']), 2)

        if last_latency == current_latency:
            print("INFO: Stable latency.")
            counter = int(app_info['last_latency_counter']) + 1
            print(f"Counter de estabilidade incrementado: {counter}")

            if counter >= 3: # means no more requests for 3 or more rounds
                CONFIG = 0
                adaptation_url = f"http://{cluster_info['ip_address']}:{app_info['port']}/adapt/{CONFIG}"
                create_data(adaptation_url, body=[])
                update_data(APP_INFO_URL, body={"num_replicas": 0, "config": CONFIG, "last_latency_counter": None, "last_latency_check": None})
                return
            else:
                update_data(APP_INFO_URL, body={"num_replicas": app_info['num_replicas'], "config": app_info['config'],
                                "last_latency_counter": counter, "last_latency_check": current_latency})
                return

        if current_latency > TRESHOLD_LATENCY:
            print("INFO: Latência subindo.")
            initial_port = 30300
            current_num_replicas = int(app_info['num_replicas'])
            num_replicas = 2 if current_num_replicas < 2 else current_num_replicas + 1
            initial_name = f'dana-remote-{TARGET_APP}'
            namespace = f"{initial_name}-ns-{num_replicas}-replicas" # different namespaces for each number of replicas to avoid conflicts
            remotes = []
            create_data(f'{POD_CREATOR_URL(cluster_info["ip_address"])}/namespaces', body={"name": namespace})
            print(f"Namespace criado: {namespace}")

            for i in range(num_replicas):
                new_remote = {
                    "pod_name": f'{initial_name}-{i}',
                    "namespace": namespace,
                    "image_name": "my.private-registry.lan:5000/dana-remote:latest",
                    "app_port": initial_port + (10*num_replicas) + i, # unique port for each replica according to number of total replicas to avoid conflicts
                }
                create_data(f'{POD_CREATOR_URL(cluster_info["ip_address"])}/create-pod', body=new_remote)
                print(f"Solicitação de criação de pod enviada: {new_remote}")
                remotes.append({"address": cluster_info['ip_address'], "port": new_remote['app_port']})

            time.sleep(15)
            CONFIG = 4
            print(f"Remotes criados: {remotes}")
            adaptation_url = f"http://{cluster_info['ip_address']}:{app_info['port']}/adapt/{CONFIG}"
            create_data(adaptation_url, body=remotes)
            print(f"App adaptado para configuração {CONFIG} com {num_replicas} réplicas.")
            body = {"num_replicas": num_replicas, "config": CONFIG, "last_latency_counter": 0, "last_latency_check": current_latency}
            print(f"App update body {body}")
            update_data(APP_INFO_URL, body=body)

        elif current_latency < TRESHOLD_LATENCY:
            print("INFO: Latência em queda.")
            initial_port = 30300
            current_num_replicas = int(app_info['num_replicas'])
            num_replicas = 0 if current_num_replicas < 3 else current_num_replicas - 1
            initial_name = f'dana-remote-{TARGET_APP}'
            namespace = f"{initial_name}-ns-{num_replicas}-replicas" # different namespaces for each number of replicas to avoid conflicts
            remotes = []
            create_data(f'{POD_CREATOR_URL(cluster_info["ip_address"])}/namespaces', body={"name": namespace})
            print(f"Namespace criado: {namespace}")

            for i in range(num_replicas):
                new_remote = {
                    "pod_name": f'{initial_name}-{i}',
                    "namespace": namespace,
                    "image_name": "my.private-registry.lan:5000/dana-remote:latest",
                    "app_port": initial_port + (10*num_replicas) + i, # unique port for each replica according to number of total replicas to avoid conflicts
                }
                create_data(f'{POD_CREATOR_URL(cluster_info["ip_address"])}/create-pod', body=new_remote)
                print(f"Solicitação de criação de pod enviada: {new_remote}")
                remotes.append({"address": cluster_info['ip_address'], "port": new_remote['app_port']})

            time.sleep(15)
            print(f"Remotes criados: {remotes}")
            CONFIG = 0 if num_replicas < 3 else 4
            adaptation_url = f"http://{cluster_info['ip_address']}:{app_info['port']}/adapt/{CONFIG}"
            create_data(adaptation_url, body=remotes)
            body = {"num_replicas": num_replicas, "config": CONFIG, "last_latency_counter": 0, "last_latency_check": current_latency}
            print(f"App adaptado para configuração {CONFIG} com {num_replicas} réplicas.")
            print(f"App update body {body}")
            update_data(APP_INFO_URL, body=body)
    except Exception as e:
        print(f"Erro ao processar modelo matemático: {e}")

if __name__ == "__main__":
    main()