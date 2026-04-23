import os
import time
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)


@app.route('/', methods=['GET'])
def root_handler():
    return jsonify({"message": "Latency Check API"})

@app.route('/create-pod', methods=['POST'])
def create_pod_handler():
    data = request.get_json()
    if not data or 'targets' not in data:
        return jsonify({"error": "Requisição inválida. Forneça 'targets'."}), 400

    targets = data['targets'] # expects a list of target ips or domains
    metrics = []

    for target in targets:
        start_time_in_ns = time.time_ns()
        try:
            response = requests.get(f'http://{target}:30001', timeout=5)
            latency_in_ms = (time.time_ns() - start_time_in_ns) / 1_000_000
            metrics.append({
                "target": target,
                "latency_ms": latency_in_ms,
                "status_code": response.status_code
            })
        except requests.exceptions.RequestException as e:
            latency_in_ms = (time.time_ns() - start_time_in_ns) / 1_000_000
            metrics.append({
                "target": target,
                "latency_ms": latency_in_ms,
                "error": str(e)
            })


    return jsonify({
        "message": "success",
        "metrics": metrics
    }), 201

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5003)