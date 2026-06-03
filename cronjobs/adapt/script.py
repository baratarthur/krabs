import os
from api_helper import fetch_data, create_data, update_data, delete_data
from dto.adaptation_info import AdaptationInfo

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

def main():
    app_info = fetch_data(APP_INFO_URL, params={})
    cluster_info = fetch_data(CURRENT_CLUSTER_INFO_URL, params={})
    if not app_info or not cluster_info:
        print("Não foi possível obter as informações da aplicação. Encerrando o processo de adaptação.")
        return
    
    app_meta = fetch_data(LATENCY_RETREIVE_URL(cluster_info['ip_address'], app_info['port']), params={})

    print(f"Informações da aplicação: {app_info}")
    print(f"Informações do cluster: {cluster_info}")
    print(f"Latência atual da aplicação: {app_meta['latency']} ms")

    try:
        last_latency = round(float(app_info['last_latency_check']), 2)
        current_latency = round(float(app_meta['latency']), 2)

        if last_latency == current_latency:
            print("INFO: Stable latency.")
            counter = int(app_info['last_latency_counter']) + 1
            print(f"Counter de estabilidade incrementado: {counter}")

            if counter >= 3: # means no more requests for 3 or more rounds
                CONFIG = 0
                adaptation_url = f"http://{cluster_info['ip_address']}:{app_info['port']}/adapt/{CONFIG}"
                create_data(adaptation_url, body=[])
                update_data(APP_INFO_URL, body={"num_replicas": 0, "config": CONFIG, "last_latency_counter": None, "last_latency_check": None})
            else:
                update_data(APP_INFO_URL, body={"num_replicas": app_info['num_replicas'], "config": app_info['config'],
                                "last_latency_counter": counter, "last_latency_check": current_latency})
            return
        
        adaptation_info = AdaptationInfo(app_info, cluster_info)

        # verify adaptation need and set parameters replicas and configuration
        if current_latency > TRESHOLD_LATENCY:
            print("INFO: latency increasing.")
            num_replicas = 2 if adaptation_info.current_num_replicas < 2 else adaptation_info.current_num_replicas + 1
            CONFIG = 4
        else:
            print("INFO: latency decreasing.")
            num_replicas = 0 if adaptation_info.current_num_replicas < 3 else adaptation_info.current_num_replicas - 1
            CONFIG = 0 if num_replicas < 3 else 4

        # adaptation url and request the creation of a namespace to handle application remotes
        adaptation_url = f"http://{cluster_info['ip_address']}:{app_info['port']}/adapt/{CONFIG}"
        
        namespace = f"{adaptation_info.initial_name}-replicas"
        create_data(f'{POD_CREATOR_URL(cluster_info["ip_address"])}/namespaces', body={"name": namespace})
        print(f"Namespace created: {namespace}")

        for i in range(num_replicas):
            new_remote = {
                "pod_name": f'{adaptation_info.initial_name}-{i}',
                "namespace": namespace,
                "image_name": "my.private-registry.lan:5000/dana-remote:latest",
                "app_port": adaptation_info.initial_port + i, # unique port for each replica according to number of total replicas to avoid conflicts
            }
            create_data(f'{POD_CREATOR_URL(cluster_info["ip_address"])}/create-pod', body=new_remote)
            print(f"Request to create pod sent: {new_remote}")
            adaptation_info.add_remote(cluster_info['ip_address'], new_remote['app_port'])

        print(f"Remotes created: {adaptation_info.remotes}")
        create_data(adaptation_url, body=adaptation_info.remotes)
        print(f"App adapted to configuration {CONFIG} with {num_replicas} replicas.")
        
        new_app_information = {"num_replicas": num_replicas, "config": CONFIG, "last_latency_counter": 0, "last_latency_check": current_latency}
        print(f"App update body = {new_app_information}")
        update_data(APP_INFO_URL, body=new_app_information)

        print("Delete old namespaces and pods to free cpu capacity in cluster.")
        old_namespace = f"{adaptation_info.initial_name}-ns-{adaptation_info.current_num_replicas}-replicas" # different namespaces for each number of replicas to avoid conflicts
        delete_data(f'{POD_CREATOR_URL(cluster_info["ip_address"])}/namespaces/{old_namespace}')

        print("Adaptation complete.")

    except Exception as e:
        print(f"Erro ao processar modelo matemático: {e}")

if __name__ == "__main__":
    main()