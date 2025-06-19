#!/bin/bash

function print_endpoint(){
    TITLE="${1}"
    PORT="${2}"
    URL_PATH="${3}"
    IP="$(ip route get 8.8.8.8 | head -1 | cut -d' ' -f7)"
    echo "${TITLE}: http://${IP}:${PORT}${URL_PATH}"
}

function install_helm(){
    curl -s https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash 2> /dev/null
}

function node-exporter() {
    install_helm
    
    helm repo add prometheus-community https://prometheus-community.github.io/helm-charts 2> /dev/null && helm repo update 2> /dev/null
    helm install -g -f node-exporter_config.yaml prometheus-community/prometheus-node-exporter 2> /dev/null

    print_endpoint "Node exporter" "32000" "/metrics"
}

function prometheus() {
    install_helm

    helm repo add prometheus-community https://prometheus-community.github.io/helm-charts 2> /dev/null && helm repo update 2> /dev/null
    helm install -g -f prometheus_config.yaml prometheus-community/prometheus 2> /dev/null

    print_endpoint "Prometheus" "32001"
}

function grafana() {
    install_helm

    helm repo add grafana https://grafana.github.io/helm-charts 2> /dev/null && helm repo update 2> /dev/null
    helm install -g -f grafana_config.yaml grafana/grafana 2> /dev/null

    print_endpoint "Grafana" "32002" "/d/rYdddlPWk/node-exporter-full"
}

ACTION="${1}"
HOST="${2}"
TARGET_HOST="${3}"

[ -z "${ACTION}" ] && echo "ERROR: action is missing" && exit 1
[ -z "${HOST}" ] && echo "ERROR: host is missing" && exit 1

if [[ "${ACTION}" == "node-exporter" ]]; then
    scp -r node-exporter_config.yaml "${HOST}":~/node-exporter_config.yaml
    ssh "${HOST}" "set -x; $(typeset -f); node-exporter"
elif [[ "${ACTION}" == "prometheus" ]]; then
    target_host="${TARGET_HOST}":32000 yq -i '.serverFiles."prometheus.yml".scrape_configs.[].static_configs.[].targets.[]= env(target_host)' prometheus_config.yaml
    scp -r prometheus_config.yaml "${HOST}":~/prometheus_config.yaml
    ssh "${HOST}" "set -x; $(typeset -f); prometheus"
    target_host=target_host yq -i '.serverFiles."prometheus.yml".scrape_configs.[].static_configs.[].targets.[]= env(target_host)' prometheus_config.yaml
elif [[ "${ACTION}" == "grafana" ]]; then
    target_host="http://${TARGET_HOST}":32001 yq -i '.datasources."datasources.yaml".datasources.[].url= env(target_host)' grafana_config.yaml
    scp -r grafana_config.yaml "${HOST}":~/grafana_config.yaml
    ssh "${HOST}" "set -x; $(typeset -f); grafana"
    target_host=target_host yq -i '.datasources."datasources.yaml".datasources.[].url= env(target_host)' grafana_config.yaml
else
    echo "ERROR: invalid action: ${ACTION}"
    exit 1
fi
