import os
from api_helper import fetch_data, create_data, update_data, delete_data
from dto.adaptation_info import AdaptationInfo

TARGET_APP = os.getenv('TARGET', 'social-media-app')
CLUSTER_NAME = os.getenv('CLUSTER_NAME', 'unknown')
KRABS_URL = os.getenv('KRABS_URL', 'http://krabs-service:5002')

CLUSTERS_URL = f'{KRABS_URL}/clusters'
CURRENT_CLUSTER_INFO_URL = f'{KRABS_URL}/clusters/{CLUSTER_NAME}'
APP_INFO_URL = f'{KRABS_URL}/applications/{TARGET_APP}'
COMPONENTS_URL = f'{KRABS_URL}/components'

CLUSTER_INFO_BY_ID_URL = lambda id: f'{KRABS_URL}/clusters/by-id/{id}'
LATENCY_RETREIVE_URL = lambda ip, port: f'http://{ip}:{port}/current-latency'
LATENCY_CHECK_URL = lambda ip: f'http://{ip}:30003/check-latency'
POD_CREATOR_URL = lambda ip: f'http://{ip}:30001'

REMOTE_IMAGE = "my.private-registry.lan:5000/dana-remote:latest"
TRESHOLD_LATENCY = 200 # ms
CONFIG = 4
DEFAULT_PROXY_CONFIG = 4
MONOLITH_PROXY_CONFIG = 0

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

        is_same_latency = last_latency == current_latency
        greater_than_upper_latency_treshold = current_latency > TRESHOLD_LATENCY
        lower_than_lower_latency_threshold = current_latency < (TRESHOLD_LATENCY / 2)
        print(f"threshhold calc: {TRESHOLD_LATENCY / 2}")
        print(f"current latency: {current_latency}, last latency: {last_latency}, upper threshhold: {greater_than_upper_latency_treshold}, lower threshold: {lower_than_lower_latency_threshold}")

        if is_same_latency:
            counter = int(app_info['last_latency_counter']) + 1
            print(f"stability counter incremented: {counter}")

            if counter >= 3: # adapt to monolith config
                CONFIG = MONOLITH_PROXY_CONFIG
                adaptation_url = f"http://{cluster_info['ip_address']}:{app_info['port']}/adapt/{CONFIG}"
                create_data(adaptation_url, body=[])
                update_data(APP_INFO_URL, body={"num_replicas": 0, "config": CONFIG, "last_latency_counter": None, "last_latency_check": None})
            else: # increase stability counter at krabs 
                update_data(APP_INFO_URL, body={"num_replicas": app_info['num_replicas'], "config": app_info['config'],
                                "last_latency_counter": counter, "last_latency_check": current_latency})
            return # finish adaptation algorithm
        
        adaptation_info = AdaptationInfo(app_info, cluster_info)

        # verify adaptation need and set parameters replicas and configuration
        if greater_than_upper_latency_treshold:
            print("INFO: latency increasing.")
            is_first_adaptation = adaptation_info.current_num_replicas < 2
            num_replicas = 2 if is_first_adaptation else adaptation_info.current_num_replicas + 1
            CONFIG = DEFAULT_PROXY_CONFIG

            all_clusters = fetch_data(CLUSTERS_URL, params={})
            available_clusters = list(filter(has_available_resources_factory(2 if is_first_adaptation else 1), all_clusters))
            print(f"Available clusters with enough resources: {available_clusters}")
            if len(available_clusters) == 0: print("No available clusters, can't do anything"); return # no available clusters, can't do anything
            
            clusters_ips = list(map(lambda c: c['ip_address'], available_clusters))
            clusters_latency = create_data(LATENCY_CHECK_URL(cluster_info['ip_address']), {'targets': clusters_ips})
            print(f"Latency for available clusters: {clusters_latency}")
            clusters_ip_latency_correlation = {c['target']: c['latency_ms'] for c in clusters_latency['metrics']}
            print(f"Clusters latency correlation: {clusters_ip_latency_correlation}")
            all_cluster_data = [{**c, 'latency_ms': clusters_ip_latency_correlation.get(c['ip_address'])} for c in available_clusters]
            sorted_clusters = sorted(all_cluster_data, key=lambda c: c['latency_ms'])
            print(f"Available clusters sorted by latency: {sorted_clusters}")

            selected_cluster = sorted_clusters[0]
            print(f"Selected cluster for adaptation: {selected_cluster}")

            # once the cluster is selected, follow the adaptation
            namespace = f"{adaptation_info.initial_name}-components"
            create_data(f'{POD_CREATOR_URL(selected_cluster["ip_address"])}/namespaces', body={"name": namespace})
            print(f"Namespace created: {namespace}")

            if is_first_adaptation:
                for i in range(2): # create 2 replicas in the first adaptation
                    new_remote = {
                        "pod_name": f'{adaptation_info.initial_name}-{i}',
                        "namespace": namespace,
                        "image_name": REMOTE_IMAGE,
                        "app_port": adaptation_info.initial_port + i, # unique port
                    }

                    create_data(f'{POD_CREATOR_URL(selected_cluster["ip_address"])}/create-pod', body=new_remote)
                    adaptation_info.add_remote(selected_cluster['ip_address'], new_remote['app_port'])
                    new_component = {
                        "name": new_remote['pod_name'],
                        "cluster_name": selected_cluster['name'],
                        "app_name": TARGET_APP,
                        "port": new_remote['app_port']
                    }
                    create_data(COMPONENTS_URL, body=new_component)
                    print(f"Request to create pod sent: {new_remote}")
            else:
                # map all remote components to clusters
                index = 0
                for remote in app_info['components']:
                    component_cluster = fetch_data(CLUSTER_INFO_BY_ID_URL(remote['cluster_id']), params={})
                    component_port = remote['port']
                    adaptation_info.add_remote(component_cluster['ip_address'], component_port)
                    index += 1

                new_remote = {
                    "pod_name": f'{adaptation_info.initial_name}-{index}',
                    "namespace": namespace,
                    "image_name": REMOTE_IMAGE,
                    "app_port": adaptation_info.initial_port + index, # unique port
                }

                create_data(f'{POD_CREATOR_URL(selected_cluster["ip_address"])}/create-pod', body=new_remote)
                adaptation_info.add_remote(selected_cluster['ip_address'], new_remote['app_port'])
                new_component = {
                    "name": new_remote['pod_name'],
                    "cluster_name": selected_cluster['name'],
                    "app_name": TARGET_APP,
                    "port": new_remote['app_port']
                }
                create_data(COMPONENTS_URL, body=new_component)
                print(f"Request to create pod sent: {new_remote}")

            # adaptation url and request the creation of a namespace to handle application remotes
            adaptation_url = f"http://{cluster_info['ip_address']}:{app_info['port']}/adapt/{CONFIG}"
            print(f"Remotes created: {adaptation_info.remotes}")
            create_data(adaptation_url, body=adaptation_info.remotes)
            print(f"App adapted to configuration {CONFIG} with {num_replicas} replicas.")
            
            new_app_information = {"num_replicas": num_replicas, "config": CONFIG, "last_latency_counter": 0, "last_latency_check": current_latency}
            print(f"App update body = {new_app_information}")
            update_data(APP_INFO_URL, body=new_app_information)

        # Only decrease components if latency is above homeostasis area
        elif lower_than_lower_latency_threshold:
            print("INFO: latency decreasing.")
            should_delete_all_remotes = adaptation_info.current_num_replicas < 3
            num_replicas = 0 if should_delete_all_remotes else adaptation_info.current_num_replicas - 1
            CONFIG = MONOLITH_PROXY_CONFIG if should_delete_all_remotes else DEFAULT_PROXY_CONFIG

            if should_delete_all_remotes:
                # adaptation url and request the creation of a namespace to handle application remotes
                adaptation_url = f"http://{cluster_info['ip_address']}:{app_info['port']}/adapt/{CONFIG}"
                print(f"Remotes created: {adaptation_info.remotes}")
                create_data(adaptation_url, body=[])

                for remote in app_info['components']:
                    cluster_of_component = fetch_data(CLUSTER_INFO_BY_ID_URL(remote['cluster_id']), params={})
                    delete_data(f'{POD_CREATOR_URL(cluster_of_component["ip_address"])}/delete-pod/{remote["name"]}')
                    delete_data(f'{COMPONENTS_URL}/{remote["name"]}')
                    print(f"Component deleted: {remote['name']}")
            else:
                print(f"Components left: {app_info['components'][:-1]}")
                for remote in app_info['components'][:-1]:  # exclude the last component
                    component_cluster = fetch_data(CLUSTER_INFO_BY_ID_URL(remote['cluster_id']), params={})
                    adaptation_info.add_remote(component_cluster['ip_address'], remote['port'])
                
                # adaptation url and request the creation of a namespace to handle application remotes
                adaptation_url = f"http://{cluster_info['ip_address']}:{app_info['port']}/adapt/{CONFIG}"
                print(f"Remotes created: {adaptation_info.remotes}")
                create_data(adaptation_url, body=adaptation_info.remotes)

                component_te_delete = app_info['components'][-1] # get the last component created, which is the one to be deleted
                cluster_of_component_to_delete = fetch_data(CLUSTER_INFO_BY_ID_URL(component_te_delete['cluster_id']), params={})
                delete_data(f'{POD_CREATOR_URL(cluster_of_component_to_delete["ip_address"])}/delete-pod/{component_te_delete["name"]}')
                delete_data(f'{COMPONENTS_URL}/{component_te_delete["name"]}')
                print(f"Component deleted: {component_te_delete['name']}")

        print("Adaptation complete.")

    except Exception as e:
        print(f"Erro ao processar modelo matemático: {e}")

def has_available_resources_factory(resources_needed: int):
    def has_available_resources(cluster):
        print(f"Amount f applications {len(cluster['applications'])}, amount of components {len(cluster['components'])}, cluster cores {cluster['cores']}, resources needed {resources_needed}")
        return cluster['cores'] >= (len(cluster['applications']) + len(cluster['components'])) + resources_needed
    return has_available_resources

if __name__ == "__main__":
    main()