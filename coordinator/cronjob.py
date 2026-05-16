from kubernetes import client, config

def create_cron_job(target, ip, type = 'watch', cluster_name = None):
    config.load_incluster_config()

    batch_v1 = client.BatchV1Api()
    APP_CICLE = 1

    environment_vars = [
        client.V1EnvVar(name="TARGET", value=target),
        client.V1EnvVar(name="TARGET_IP", value=ip)]

    if cluster_name: environment_vars.append(client.V1EnvVar(name="CLUSTER_NAME", value=cluster_name))

    container = client.V1Container(
        name=f"{type}-{target}-cronjob",
        image=f"my.private-registry.lan:5000/{type}:latest",
        image_pull_policy="Always",
        env=environment_vars
    )

    pod_template = client.V1PodTemplateSpec(
        metadata=client.V1ObjectMeta(labels={"app": f"{type}-{target}-cronjob"}),
        spec=client.V1PodSpec(
            restart_policy="OnFailure",
            containers=[container]
        )
    )

    job_template = client.V1JobTemplateSpec(
        spec=client.V1JobSpec(
            template=pod_template,
            backoff_limit=3
        )
    )

    cron_spec = client.V1CronJobSpec(
        schedule=f"*/{APP_CICLE} * * * *",
        job_template=job_template,
        concurrency_policy="Forbid",
        failed_jobs_history_limit=5,
        successful_jobs_history_limit=3,
    )

    cron_job = client.V1CronJob(
        api_version="batch/v1",
        kind="CronJob",
        metadata=client.V1ObjectMeta(name=f"cronjob-{type}-{target}"),
        spec=cron_spec
    )

    namespace = "default"
    api_response = batch_v1.create_namespaced_cron_job(
        namespace=namespace,
        body=cron_job
    )
    print(f"CronJob criado com sucesso. Status: {api_response.status}")

def delete_cron_job(target, type = 'watch'):
    config.load_incluster_config()
    batch_v1 = client.BatchV1Api()
    namespace = "default"
    name = f"cronjob-{type}-{target}"
    try:
        api_response = batch_v1.delete_namespaced_cron_job(
            name=name,
            namespace=namespace,
            body=client.V1DeleteOptions()
        )
        print(f"CronJob '{name}' deletado com sucesso. Status: {api_response.status}")
    except client.exceptions.ApiException as e:
        if e.status == 404:
            print(f"CronJob '{name}' não encontrado. Nada para deletar.")
        else:
            print(f"Erro ao deletar CronJob '{name}': {e}")