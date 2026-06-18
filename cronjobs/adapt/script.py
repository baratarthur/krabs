import os
import time
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
STARTUP_TIME = 20 # s
CONFIG = 4
INITIAL_NUM_REPLICAS = 2
DEFAULT_PROXY_CONFIG = 4
MONOLITH_PROXY_CONFIG = 0

def main():
    app_info = fetch_data(APP_INFO_URL)
    cluster_info = fetch_data(CURRENT_CLUSTER_INFO_URL)
    if not app_info or not cluster_info:
        print("Não foi possível obter as informações da aplicação. Encerrando o processo de adaptação.")
        return
    
    app_meta = fetch_data(LATENCY_RETREIVE_URL(cluster_info['ip_address'], app_info['port']))
    app_components = app_info['components']

    print(f"Informações da aplicação: {app_info}")
    print(f"Informações do cluster: {cluster_info}")
    print(f"Latência atual da aplicação: {app_meta['latency']} ms")

    adaptation_info = AdaptationInfo(app_info, cluster_info)
    namespace = f"{adaptation_info.initial_name}-components"
    current_latency = round(float(app_meta['latency']), 2)
    greater_than_upper_latency_treshold = current_latency > TRESHOLD_LATENCY
    lower_than_lower_latency_threshold = current_latency < (TRESHOLD_LATENCY / 2)
    current_num_replicas = len(app_components)

    print(f"current latency: {current_latency}, upper threshhold: {greater_than_upper_latency_treshold}, lower threshold: {lower_than_lower_latency_threshold}")

    try:
        # verify adaptation need and set parameters replicas and configuration
        if greater_than_upper_latency_treshold:
            '''
                1 -> get all available clusters
                2 -> measure distance
                3 -> mapp cluster information
                4 -> select cluster
                5 -> goto line 94
            '''
            print("\n =============== INFO: latency increasing. ===============\n")
            print(f"Current components: {app_info['components']}")
            
            is_first_adaptation = current_num_replicas < INITIAL_NUM_REPLICAS
            next_num_replicas = INITIAL_NUM_REPLICAS if is_first_adaptation else current_num_replicas + 1
            CONFIG = DEFAULT_PROXY_CONFIG

            print(f"adaptation params > remotes: {current_num_replicas}, first adaptation: {is_first_adaptation}, next_num_replicas: {next_num_replicas}")

            # get clusters and  and filter for the ones that have available resources
            all_clusters = fetch_data(CLUSTERS_URL)
            available_clusters = list(filter(has_available_resources_factory(INITIAL_NUM_REPLICAS if is_first_adaptation else 1), all_clusters))
            print(f"Available clusters with enough resources: {available_clusters}")
            if len(available_clusters) == 0: print("No available clusters, can't do anything"); return # no available clusters, can't do anything
            
            # fetch cluster distance from current middleware
            clusters_ips = list(map(get_key_factory('ip_address'), available_clusters))
            clusters_latency = create_data(LATENCY_CHECK_URL(cluster_info['ip_address']), {'targets': clusters_ips})
            print(f"Latency for available clusters: {clusters_latency}")
            clusters_ip_latency_correlation = {c['target']: c['latency_ms'] for c in clusters_latency['metrics']}
            print(f"Clusters latency correlation: {clusters_ip_latency_correlation}")
            all_cluster_data = [{**c, 'latency_ms': clusters_ip_latency_correlation.get(c['ip_address'])} for c in available_clusters]
            sorted_clusters = sorted(all_cluster_data, key=lambda c: c['latency_ms'])
            print(f"Available clusters sorted by latency: {sorted_clusters}")

            selected_cluster = sorted_clusters[0]
            print(f"Selected cluster for adaptation: {selected_cluster}")

            print("\n============ Adaptation start ================\n\n")

            # once the cluster is selected, follow the adaptation
            create_data(f'{POD_CREATOR_URL(selected_cluster["ip_address"])}/namespaces', body={"name": namespace})
            print(f"Namespace created: {namespace}")

            if is_first_adaptation:
                '''
                    1 -> create 2 components at selcted cluster
                '''
                for i in range(INITIAL_NUM_REPLICAS): # create 2 replicas in the first adaptation
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
                '''
                    1 -> create one component at selcted cluster
                '''
                # map all remote components to clusters
                print(f"Current components: {app_components}")
                index = 0
                for remote in app_components:
                    component_cluster = fetch_data(CLUSTER_INFO_BY_ID_URL(remote['cluster_id']))
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
                print(f"Request to create pod sent: {new_remote}")

                adaptation_info.add_remote(selected_cluster['ip_address'], new_remote['app_port'])
                new_component = {
                    "name": new_remote['pod_name'],
                    "cluster_name": selected_cluster['name'],
                    "app_name": TARGET_APP,
                    "port": new_remote['app_port']
                }
                create_data(COMPONENTS_URL, body=new_component)
                print(f"Request to create component sent: {new_component}")

            # adaptation url and request the creation of a namespace to handle application remotes
            adaptation_endpoint = f"http://{cluster_info['ip_address']}:{app_info['port']}/adapt"
            print("Adapting to monolith to wait remote components startup")
            monolith_adaptation_url = f'{adaptation_endpoint}/0'
            create_data(monolith_adaptation_url, body=[])

            print("Sleep for 15 seconds")
            time.sleep(STARTUP_TIME)

            adaptation_url = f'{adaptation_endpoint}/{CONFIG}'
            print(f"Adaptation url: {adaptation_url}")
            print(f"Remotes created: {adaptation_info.remotes}")
            create_data(adaptation_url, body=adaptation_info.remotes)
            print(f"App adapted to configuration {CONFIG} with {len(adaptation_info.remotes)} replicas.")
            
            new_app_information = {"num_replicas": next_num_replicas, "config": CONFIG, "last_latency_counter": 0, "last_latency_check": current_latency}
            print(f"App update body = {new_app_information}")
            update_data(APP_INFO_URL, body=new_app_information)

        # Only decrease components if latency is above homeostasis area
        elif lower_than_lower_latency_threshold:
            print("\n ======================= INFO: latency decreasing. =======================\n")
            
            if current_num_replicas < 1:
                print("nothing to do here!")
                return

            should_delete_all_remotes = current_num_replicas < 3
            next_num_replicas = 0 if should_delete_all_remotes else current_num_replicas - 1
            CONFIG = MONOLITH_PROXY_CONFIG if should_delete_all_remotes else DEFAULT_PROXY_CONFIG

            print(f"current num replicas: {adaptation_info.current_num_replicas}, should delete all remotes: {should_delete_all_remotes}, next num replicas: {next_num_replicas}, next conifg: {CONFIG}")

            if should_delete_all_remotes:
                '''
                1 -> change application to monolith
                2 -> delete remote components
                3 -> delete components from krabs
                '''
                # adaptation url and request the creation of a namespace to handle application remotes
                adaptation_url = f"http://{cluster_info['ip_address']}:{app_info['port']}/adapt/{CONFIG}"
                print(f"Adaptation url: {adaptation_url}")
                create_data(adaptation_url, body=[])

                for remote in app_info['components']:
                    cluster_of_component = fetch_data(CLUSTER_INFO_BY_ID_URL(remote['cluster_id']))
                    delete_data(f'{POD_CREATOR_URL(cluster_of_component["ip_address"])}/delete-pod/{namespace}/{remote["name"]}')
                    delete_data(f'{COMPONENTS_URL}/{remote["name"]}')
                    print(f"Component deleted: {remote['name']}")
            else:
                '''
                1 -> get last component
                2 -> create a list without the last component
                3 -> adapt to the new list without the last component
                4 -> delete pod of last component
                5 -> delete last component from krabs
                '''
                component_to_delete = app_components[-1] # get the last component created, which is the one to be deleted
                components_to_maintain = app_components[:-1]
                print(f"Components left: {components_to_maintain}")
                print(f"Adaptation info: {adaptation_info}")

                for remote in components_to_maintain:  # exclude the last component
                    component_cluster = fetch_data(CLUSTER_INFO_BY_ID_URL(remote['cluster_id']), params={})
                    adaptation_info.add_remote(component_cluster['ip_address'], remote['port'])
                
                # adaptation url and request the creation of a namespace to handle application remotes
                adaptation_url = f"http://{cluster_info['ip_address']}:{app_info['port']}/adapt/{CONFIG}"
                create_data(adaptation_url, body=adaptation_info.remotes)
                print(f"Remotes created: {adaptation_info.remotes}")

                cluster_of_component_to_delete = fetch_data(CLUSTER_INFO_BY_ID_URL(component_to_delete['cluster_id']))
                delete_data(f'{POD_CREATOR_URL(cluster_of_component_to_delete["ip_address"])}/delete-pod/{namespace}/{component_to_delete["name"]}')
                delete_data(f'{COMPONENTS_URL}/{component_to_delete["name"]}')
                print(f"Component deleted: {component_to_delete['name']}")

        print("Adaptation complete.")

    except Exception as e:
        print(f"Erro ao processar modelo matemático: {e}")

def has_available_resources_factory(resources_needed: int):
    def has_available_resources(cluster):
        print(f"Amount f applications {len(cluster['applications'])}, amount of components {len(cluster['components'])}, cluster cores {cluster['cores']}, resources needed {resources_needed}")
        return cluster['cores'] >= (len(cluster['applications']) + len(cluster['components'])) + resources_needed
    return has_available_resources

def get_key_factory(key):
    def get_key(el):
        return el[key]
    return get_key

if __name__ == "__main__":
    main()