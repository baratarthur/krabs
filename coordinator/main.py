from flask import Flask, request, jsonify
from sqlalchemy.orm import Session
from sqlalchemy import select
from cronjob import create_cron_job

from models import engine, InfrastructureManager, Cluster, Application

app = Flask(__name__)
manager = InfrastructureManager(engine)

# --- Endpoints de Clusters ---

@app.route('/clusters', methods=['POST'])
def create_cluster():
    data = request.json

    if not data or 'name' not in data or 'ip_address' not in data:
        return jsonify({"error": "Campos 'name' e 'ip_address' são obrigatórios."}), 400

    try:
        cluster = manager.create_cluster(data['name'], data['ip_address'])
        cluster_info = cluster.to_dict()
        create_cron_job(cluster_info["name"], cluster_info["ip_address"])

        return jsonify(cluster_info), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/clusters/<name>', methods=['DELETE'])
def delete_cluster(name):
    try:
        # Usa o Manager criado anteriormente
        cluster = manager.delete_cluster(name)
        return jsonify(cluster.to_dict()), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/clusters', methods=['GET'])
def list_clusters():
    with Session(engine) as session:
        stmt = select(Cluster)
        clusters = session.scalars(stmt).all()
        return jsonify([c.to_dict() for c in clusters]), 200
    
@app.route('/clusters/<name>', methods=['GET'])
def get_cluster(name):
    with Session(engine) as session:
        stmt = select(Cluster).where(Cluster.name == name)
        cluster = session.scalar(stmt)
        if not cluster:
            return jsonify({"error": "Cluster não encontrado."}), 404
        return jsonify(cluster.to_dict()), 200

# --- Endpoints de Applications ---

@app.route('/applications', methods=['POST'])
def deploy_app():
    data = request.json
    
    if not data or 'name' not in data or 'cluster_name' not in data or 'port' not in data or 'config' not in data:
        return jsonify({"error": "Campos 'name', 'cluster_name', 'port' e 'config' são obrigatórios."}), 400

    try:
        app_obj = manager.deploy_application(data['name'], data['cluster_name'], data['port'], data['config'])
        
        if not app_obj:
            return jsonify({"error": "Cluster não encontrado."}), 404
        
        create_cron_job(app_obj.name, f"{app_obj.cluster.ip_address}:{app_obj.port}", type='adapt', cluster_name=app_obj.cluster.name)

        return jsonify(app_obj.to_dict()), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/applications/<name>', methods=['PUT'])
def update_app(name):
    data = request.json
    
    if not data or 'num_replicas' not in data or 'config' not in data:
        return jsonify({"error": "Campos 'num_replicas' e 'config' são obrigatórios."}), 400

    try:
        app_obj = manager.update_application(name, data['num_replicas'], data['config'])
        if not app_obj:
            return jsonify({"error": "Aplicação ou Cluster não encontrado."}), 404

        return jsonify(app_obj.to_dict()), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/applications/<name>', methods=['DELETE'])
def delete_app(name):
    with Session(engine) as session:
        stmt = select(Application).where(Application.name == name)
        app_obj = session.scalar(stmt)

        if not app_obj:
            return jsonify({"error": "Aplicação não encontrada."}), 404

        session.delete(app_obj)
        session.commit()
        return jsonify(app_obj.to_dict()), 200

@app.route('/applications', methods=['GET'])
def list_apps():
    with Session(engine) as session:
        stmt = select(Application)
        apps = session.scalars(stmt).all()
        return jsonify([a.to_dict() for a in apps]), 200
    
@app.route('/applications/<name>', methods=['GET'])
def get_app(name):
    with Session(engine) as session:
        stmt = select(Application).where(Application.name == name)
        app_obj = session.scalar(stmt)
        if not app_obj:
            return jsonify({"error": "Aplicação não encontrada."}), 404
        return jsonify(app_obj.to_dict()), 200
    
# --- Endpoints de Telemetria ---

@app.route('/telemetry', methods=['POST'])
def create_telemetry():
    data = request.json
    
    if not data or 'target' not in data or 'type' not in data or 'value' not in data:
        return jsonify({"error": "Campos 'target', 'type' e 'value' são obrigatórios."}), 400

    try:
        telemetry = manager.create_telemetry(data['target'], data['value'], data['type'])
        
        if not telemetry:
            return jsonify({"error": "Cluster não encontrado."}), 404
            
        return jsonify(telemetry.to_dict()), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/telemetry', methods=['GET'])
def list_telemetry():
    try:
        target = request.args.get('target')  # ?target=cluster1 | ?target=app1
        telemetry_type = request.args.get('type')  # ?type=cpu | ?type=latency
        minutes = request.args.get('minutes', type=int)  # ?minutes=60
        
        telemetry_list = manager.list_telemetry(target=target, telemetry_type=telemetry_type, minutes=minutes)
        return jsonify(telemetry_list), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Debug=True para auto-reload durante desenvolvimento
    app.run(host='0.0.0.0', port=5002, debug=True)