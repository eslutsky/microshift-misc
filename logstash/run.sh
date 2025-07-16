#!/bin/bash

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
KUBECONFIG_PATH="${SCRIPT_DIR}/../provision/upstream/fetched_kubeconfigs/kubeconfig"

# Set KUBECONFIG environment variable
export KUBECONFIG="$KUBECONFIG_PATH"

# Extract hostname from kubeconfig server URL
if [ -f "$KUBECONFIG_PATH" ]; then
    # Extract server URL from kubeconfig and remove https:// and port
    ELASTICSEARCH_HOST=$(grep -E "^\s*server:" "$KUBECONFIG_PATH" | head -1 | sed 's/.*server: *https\?:\/\///' | sed 's/:[0-9]*$//')
    
    if [ -n "$ELASTICSEARCH_HOST" ]; then
        echo "Extracted Elasticsearch host: $ELASTICSEARCH_HOST"
        
        # Update logstash.conf with the correct host
        sed -i "s|hosts => \[\"https://[^\"]*\"\]|hosts => [\"https://${ELASTICSEARCH_HOST}:30020\"]|g" logstash.conf
        
        # Update logstash.yml with the correct host
        sed -i "s|xpack.monitoring.elasticsearch.hosts: \[ \"https://[^\"]*\" \]|xpack.monitoring.elasticsearch.hosts: [ \"https://${ELASTICSEARCH_HOST}:30020\" ]|g" logstash.yml
        
        echo "Updated logstash configuration files with host: $ELASTICSEARCH_HOST"
    else
        echo "Warning: Could not extract hostname from kubeconfig"
    fi
else
    echo "Warning: Kubeconfig file not found at $KUBECONFIG_PATH"
fi

# Extract Elasticsearch password from Kubernetes secret
echo "Extracting Elasticsearch password..."
ELASTICSEARCH_PASSWORD=$(oc get secret quickstart-es-elastic-user -n default -o jsonpath='{.data.elastic}' | base64 --decode)

if [ -n "$ELASTICSEARCH_PASSWORD" ]; then
    echo "Successfully extracted Elasticsearch password"
    
    # Update logstash.conf with the correct password
    sed -i "s|password => \"[^\"]*\"|password => \"${ELASTICSEARCH_PASSWORD}\"|g" logstash.conf
    
    # Update logstash.yml with the correct password
    sed -i "s|xpack.monitoring.elasticsearch.password: \"[^\"]*\"|xpack.monitoring.elasticsearch.password: \"${ELASTICSEARCH_PASSWORD}\"|g" logstash.yml
    
    echo "Updated logstash configuration files with new password"
else
    echo "Warning: Could not extract Elasticsearch password from secret"
fi

podman run -ti -v ./data:/opt/data:Z -v ./logstash.conf:/usr/share/logstash/pipeline/logstash.conf:Z \
-v ./logstash.yml:/usr/share/logstash/config/logstash.yml:Z \
 9c8234d47a7e