import os
from flask import Flask, request, jsonify
from kubernetes import client, config

app = Flask(__name__)

# --- Configuração do Cliente Kubernetes ---
try:
    config.load_incluster_config()
except config.ConfigException:
    config.load_kube_config()

core_v1_api = client.CoreV1Api()


@app.route('/create-pod', methods=['POST'])
def create_pod_handler():
    data = request.get_json()
    if not data or 'pod_name' not in data or 'image_name' not in data:
        return jsonify({"error": "Requisição inválida. Forneça 'pod_name' e 'image_name'."}), 400

    pod_name = data['pod_name']
    image_name = data['image_name']
    app_port = data.get('app_port', 80) # Porta padrão 80 se não for fornecida
    namespace = os.getenv("POD_NAMESPACE", "default")
    
    # Label único para conectar o Pod e o Service
    pod_labels = {"app": pod_name}

    # --- Manifesto do Pod (com label) ---
    pod_manifest = {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {
            "name": pod_name,
            "labels": pod_labels
        },
        "spec": {
            "containers": [{
                "name": f"{pod_name}-container",
                "image": image_name,
                "imagePullPolicy": "IfNotPresent",
                "ports": [{"containerPort": app_port}], # Expor a porta é uma boa prática
                "env": [{"name": "PORT", "value": str(app_port)}]
            }]
        }
    }

    # --- Manifesto do Service ---
    service_manifest = {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {"name": pod_name}, # Nome do Service igual ao do Pod
        "spec": {
            "selector": pod_labels, # Encontra pods com este label
            "ports": [{
                "protocol": "TCP",
                "port": app_port, # Porta do serviço
                "targetPort": app_port # Porta do contêiner
            }],
            "type": "ClusterIP" # Tipo para comunicação interna
        }
    }

    try:
        # Criar o Pod
        print(f"Criando o pod '{pod_name}' no namespace '{namespace}'")
        core_v1_api.create_namespaced_pod(namespace=namespace, body=pod_manifest)
        
        # Criar o Service
        print(f"Criando o service '{pod_name}' no namespace '{namespace}'")
        core_v1_api.create_namespaced_service(namespace=namespace, body=service_manifest)

    except client.ApiException as e:
        if e.status == 409:
             return jsonify({"error": f"Recurso '{pod_name}' já existe."}), 409
        print(f"Erro na API do Kubernetes: {e.body}")
        return jsonify({"error": "Falha ao criar recursos no Kubernetes.", "details": e.body}), 500

    # Construir a URL de DNS interna
    # O formato curto (<service-name>:<port>) funciona dentro do mesmo namespace
    internal_url = f"http://{pod_name}:{app_port}"

    return jsonify({
        "message": "Pod e Service criados com sucesso!",
        "pod_name": pod_name,
        "internal_url": internal_url,
        "full_dns_name": f"{pod_name}.{namespace}.svc.cluster.local"
    }), 201


@app.route('/delete-pod/<string:pod_name>', methods=['POST'])
def delete_pod_handler(pod_name):
    """Deleta um pod e seu service correspondente."""
    namespace = os.getenv("POD_NAMESPACE", "default")
    
    try:
        # Deletar o Service primeiro
        print(f"Tentando deletar o service '{pod_name}' no namespace '{namespace}'")
        core_v1_api.delete_namespaced_service(name=pod_name, namespace=namespace)
        
        # Deletar o Pod
        print(f"Tentando deletar o pod '{pod_name}' no namespace '{namespace}'")
        core_v1_api.delete_namespaced_pod(name=pod_name, namespace=namespace)
        
        return jsonify({"message": f"Pod e Service '{pod_name}' deletados com sucesso."}), 200
        
    except client.ApiException as e:
        if e.status == 404:
            return jsonify({"error": f"Recurso '{pod_name}' não encontrado."}), 404
        
        print(f"Erro na API do Kubernetes ao deletar: {e.body}")
        return jsonify({"error": "Falha ao deletar recursos.", "details": e.body}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)