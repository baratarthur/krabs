import requests

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
    
def delete_data(url):
    try:
        response = requests.delete(url, verify=False, timeout=45)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Erro de conexão ao deletar recurso: {e}")
        return None