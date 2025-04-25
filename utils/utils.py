import docker

def get_exposed_port(container_name):
    try:
        client = docker.DockerClient(base_url='unix://var/run/docker.sock')
        container = client.containers.get(container_name)
        ports = container.attrs['NetworkSettings']['Ports']
        for container_port, host_bindings in ports.items():
            if host_bindings:
                return host_bindings[0]['HostPort']
    except docker.errors.NotFound:
        print(f"Container '{container_name}' not found.")
    except docker.errors.DockerException as e:
        print(f"Docker error: {e}")
    return None
