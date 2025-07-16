# ELK Stack Ansible Role

This Ansible role deploys a complete ELK (Elasticsearch, Logstash, Kibana) stack on Kubernetes/OpenShift using the Elastic Cloud on Kubernetes (ECK) operator.

## Overview

The role deploys:
- **Elasticsearch** (8.13.4) - Document storage and search engine
- **Logstash** (8.13.4) - Log processing pipeline
- **Kibana** (8.13.4) - Data visualization dashboard
- **Filebeat** (8.13.4) - Log shipping agent running as DaemonSet
- **ECK Operator** - Manages Elastic Stack resources

## Features

- CoreDNS configuration for proper DNS resolution
- Persistent storage for Elasticsearch data
- Logstash configured to process logs from Filebeat
- Filebeat configured to collect container logs from Kubernetes
- NodePort services for external access to Elasticsearch and Kibana
- RBAC configuration for Filebeat
- Automatic waiting for services to be ready

## Requirements

- Kubernetes/OpenShift cluster
- `kubernetes.core` Ansible collection
- `oc` or `kubectl` CLI tool
- Storage class `topolvm-provisioner` available in the cluster

## Variables

All Kubernetes manifests are defined as variables in `defaults/main.yml`. Key variables include:

- `kubeconfig_path`: Path to kubeconfig file (default: "../provision/upstream/fetched_kubeconfigs/kubeconfig")
- `elasticsearch_version`: Elasticsearch version (default: "8.13.4")
- `filebeat_version`: Filebeat version (default: "8.13.4")
- `eck_crds_url`: ECK CRDs URL
- `eck_operator_url`: ECK Operator URL

All manifest definitions can be customized by overriding the respective variables:
- `coredns_configmap`
- `elasticsearch_pvc`
- `elasticsearch_manifest`
- `kibana_manifest`
- `logstash_deployment`
- `logstash_service`
- `logstash_config_configmap`
- `logstash_pipeline_configmap`
- `filebeat_manifest`
- `filebeat_cluster_role`
- `filebeat_cluster_role_binding`
- `filebeat_service_account`
- `elasticsearch_nodeport_service`
- `kibana_nodeport_service`

## Usage

### Basic Usage

```yaml
- hosts: localhost
  roles:
    - elk-stack
```

### With Custom Variables

```yaml
- hosts: localhost
  roles:
    - elk-stack
  vars:
    kubeconfig_path: "/path/to/your/kubeconfig"
    elasticsearch_version: "8.14.0"
```

### Example Playbook

```yaml
---
- name: Deploy ELK Stack
  hosts: localhost
  gather_facts: false
  roles:
    - role: elk-stack
      vars:
        kubeconfig_path: "{{ ansible_env.HOME }}/.kube/config"
```

## Access Information

After deployment:

- **Elasticsearch**: Available at `http://<node-ip>:30020`
- **Kibana**: Available at `http://<node-ip>:30021`

To get the elastic user password:
```bash
oc get secret quickstart-es-elastic-user -o go-template='{{.data.elastic | base64decode}}'
```

## Log Processing

The Logstash configuration is set to:
1. Receive logs from Filebeat on port 5044
2. Parse JSON messages
3. Filter and rename fields
4. Send logs containing "admission" to Elasticsearch with index pattern `logstashadmission-YYYY.MM.dd`

## Filebeat Configuration

Filebeat is configured to:
- Collect logs from `/var/log/containers/*.log`
- Add Kubernetes metadata
- Exclude logs from system namespaces (`kube-system`, `kube-public`, etc.)
- Send logs to Logstash

## Storage

The role creates a PersistentVolumeClaim for Elasticsearch using the `topolvm-provisioner` storage class with 1Gi of storage.

## Security

- Filebeat runs with appropriate RBAC permissions
- Elasticsearch uses internal authentication
- TLS is configured for internal communication

## Troubleshooting

1. Check if ECK operator is running:
   ```bash
   oc get pods -n elastic-system
   ```

2. Check Elastic resources status:
   ```bash
   oc get elasticsearch,kibana
   ```

3. Check Logstash logs:
   ```bash
   oc logs deployment/logstash
   ```

4. Check Filebeat status:
   ```bash
   oc get beat
   oc describe beat quickstart
   ```

## Dependencies

This role requires the `kubernetes.core` Ansible collection. Install it with:
```bash
ansible-galaxy collection install kubernetes.core
```

## Author

Converted from shell script to Ansible role for better maintainability and reusability. 