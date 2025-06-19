# Ansible Role: Monitoring

This role installs and configures a monitoring stack consisting of Node Exporter, Prometheus, and Grafana using Helm.

## Requirements

- Helm 3 installed on the target machine (this role can install it).
- `community.kubernetes` Ansible collection (`ansible-galaxy collection install community.kubernetes`).
- `community.general` Ansible collection for `helm_repository` if not using a newer `community.kubernetes` version that includes it directly.

## Role Variables

Available variables are listed in `defaults/main.yml`. Key variables include:

- `monitoring_target_host_ip`: (Required) The IP address of the host where Node Exporter is running. This is used to configure Prometheus to scrape Node Exporter and Grafana to connect to Prometheus.
- `monitoring_host_ip`: The IP address of the current host, defaults to `ansible_default_ipv4.address`. Used for displaying endpoint URLs.
- `helm_install_dir`: Directory to install Helm binary.
- `helm_version`: Version of Helm to install.
- `node_exporter_chart_version`: Version of the Node Exporter Helm chart.
- `node_exporter_release_name`: Helm release name for Node Exporter.
- `node_exporter_namespace`: Kubernetes namespace for Node Exporter.
- `node_exporter_values_file`: Path to the Node Exporter values file within the role.
- `node_exporter_service_nodeport`: NodePort for Node Exporter service.
- `prometheus_chart_version`: Version of the Prometheus Helm chart.
- `prometheus_release_name`: Helm release name for Prometheus.
- `prometheus_namespace`: Kubernetes namespace for Prometheus.
- `prometheus_service_nodeport`: NodePort for Prometheus service.
- `grafana_chart_version`: Version of the Grafana Helm chart.
- `grafana_release_name`: Helm release name for Grafana.
- `grafana_namespace`: Kubernetes namespace for Grafana.
- `grafana_service_nodeport`: NodePort for Grafana service.
- `grafana_admin_password`: Default admin password for Grafana.
- `grafana_dashboard_path`: Default path for the Node Exporter dashboard in Grafana.

## Dependencies

None.

## Example Playbook

```yaml
- hosts: monitoring_servers
  become: yes
  roles:
    - role: monitoring
  vars:
    monitoring_target_host_ip: "192.168.1.100" # IP of the machine running node-exporter
```

## Tags

- `helm`: Tasks related to Helm installation and repository management.
- `node-exporter`: Tasks related to Node Exporter deployment.
- `prometheus`: Tasks related to Prometheus deployment.
- `grafana`: Tasks related to Grafana deployment.
