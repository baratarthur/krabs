from kubernetes import client, config

def create_cron_job(target, url, type = 'watch'):
    # 1. Carrega a configuração (lê o ~/.kube/config localmente)
    # Se estiver rodando DENTRO do cluster, usaria config.load_incluster_config()
    config.load_incluster_config()

    # 2. Define a API que lida com CronJobs (BatchV1)
    batch_v1 = client.BatchV1Api()

    # 3. Definindo o Container (O nível mais baixo)
    container = client.V1Container(
        name=f"{type}-{target}-cronjob",
        image=f"{type}:latest",
        image_pull_policy="IfNotPresent",
        env=[client.V1EnvVar(name="TARGET", value=target), client.V1EnvVar(name="TARGET_URL", value=url)]
    )

    # 4. Definindo o Pod Template (Spec do Pod)
    pod_template = client.V1PodTemplateSpec(
        metadata=client.V1ObjectMeta(labels={"app": f"{type}-{target}-cronjob"}),
        spec=client.V1PodSpec(
            restart_policy="OnFailure",
            containers=[container]
        )
    )

    # 5. Definindo o Job Template (Spec do Job)
    job_template = client.V1JobTemplateSpec(
        spec=client.V1JobSpec(
            template=pod_template,
            backoff_limit=2
        )
    )

    # 6. Definindo o CronJob Spec (Agendamento + Job Template)
    cron_spec = client.V1CronJobSpec(
        schedule="*/1 * * * *",  # A cada minuto
        job_template=job_template,
        successful_jobs_history_limit=1
    )

    # 7. O Objeto CronJob Final (Metadata + Spec)
    cron_job = client.V1CronJob(
        api_version="batch/v1",
        kind="CronJob",
        metadata=client.V1ObjectMeta(name=f"cronjob-{type}-{target}"),
        spec=cron_spec
    )

    # 8. Enviando para o Cluster
    namespace = "default"
    try:
        api_response = batch_v1.create_namespaced_cron_job(
            namespace=namespace,
            body=cron_job
        )
        print(f"CronJob criado com sucesso. Status: {api_response.status}")
    except client.exceptions.ApiException as e:
        print(f"Erro ao criar CronJob: {e}")