import docker



def get_exposed_port(container_name):
    client = docker.from_env()
    try:
        # Get the container by its name
        container = client.containers.get(container_name)
    except docker.errors.NotFound:
        print(f"Container '{container_name}' not found.")
        return None

    # Retrieve port mapping details from the container's attributes
    ports = container.attrs['NetworkSettings']['Ports']
    for container_port, host_bindings in ports.items():
        if host_bindings:  # Check if port is exposed
            # Return the first host port found in the bindings
            return host_bindings[0]['HostPort']

    # If no exposed ports found, return None
    return None