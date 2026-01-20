import requests
import sys # Importante para sair com código de erro correto

def fetch_data(url):
    try:
        # DICA: Se for serviço interno do k8s, geralmente é HTTP, não HTTPS.
        # Se for HTTPS mesmo com certificado self-signed, use verify=False
        response = requests.get(url, verify=False) 
        response.raise_for_status()
        return response.json() # Já retorna o objeto Python (dict ou list)
    except requests.exceptions.RequestException as e:
        print(f"Erro de conexão ao buscar dados: {e}")
        return None

# 1. Removemos o .json() extra aqui
data = fetch_data("http://krabs-service:5002/applications") # Mudei para http (teste isso)

# 2. Verificação de segurança se data for None
if data is None:
    print("Falha ao obter dados. Encerrando.")
    sys.exit(1) # Sai com erro para o K8s saber que falhou

applications = data

if len(applications) == 0:
    print("Nenhuma aplicação encontrada.")
    sys.exit(0) # Sai com sucesso (0) pois não é um erro de script, apenas não tinha trabalho

try:
    telemetry = {
        "name": "usage", 
        "value": 2, 
        "cluster_name": applications[0].get("cluster", "unknown")
    }
    
    # Adicionado timeout e verify
    response = requests.post(
        "http://krabs-service:5002/telemetry", 
        json=telemetry, 
        verify=False
    )
    response.raise_for_status()
    print(f"Telemetria enviada com sucesso! Status: {response.status_code}")

except Exception as e:
    print(f"Erro ao enviar telemetria: {e}")
    sys.exit(1)