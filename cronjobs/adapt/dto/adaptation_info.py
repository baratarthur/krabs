import os

TARGET_APP = os.getenv('TARGET', 'social-media-app')

class AdaptationInfo:
    def __init__(self, app_info, cluster_info):
        self.initial_port = 30400
        self.current_num_replicas = int(app_info['num_replicas'])
        self.initial_name = f'dana-remote-{TARGET_APP}'
        self.remotes = []
        self.available_cores = int(cluster_info['cores']) - len(cluster_info['components']) - len(cluster_info['applications'])

    def add_remote(self, ip_address, app_port):
        self.remotes.append({"name": ip_address, "port": app_port})
