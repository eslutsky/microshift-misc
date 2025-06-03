#!/bin/bash

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

export KUBECONFIG=${SCRIPT_DIR}/../provision/upstream/fetched_kubeconfigs/kubeconfig

cat <<EOF | oc apply -f -
apiVersion: v1
data:
  Corefile: |
    .:5353 {
        bufsize 1232
        errors
        log . {
            class error
        }
        health {
            lameduck 20s
        }
        ready
        kubernetes cluster.local in-addr.arpa ip6.arpa {
            pods insecure
            fallthrough in-addr.arpa ip6.arpa
        }
        prometheus 127.0.0.1:9153
        forward . 8.8.8.8 {
            policy sequential
        }
        cache 900 {
            denial 9984 30
        }
        reload
    }
    hostname.bind:5353 {
        chaos
    }
kind: ConfigMap
metadata:
  labels:
    dns.operator.openshift.io/owning-dns: default
  name: dns-default
  namespace: openshift-dns
EOF


cat <<EOF | oc apply -f -
kind: PersistentVolumeClaim
apiVersion: v1
metadata:
  name: elasticsearch-data-quickstart-es-default-0
spec:
  accessModes:
  - ReadWriteOnce
  resources:
    requests:
      storage: 1Gi
  storageClassName: topolvm-provisioner
EOF



# source https://surajsoni3332.medium.com/setting-up-elk-stack-on-kubernetes-a-step-by-step-guide-227690eb57f4

oc create -f https://download.elastic.co/downloads/eck/2.2.0/crds.yaml
oc apply -f https://download.elastic.co/downloads/eck/2.2.0/operator.yaml

cat <<EOF | oc apply -f -
apiVersion: elasticsearch.k8s.elastic.co/v1
kind: Elasticsearch
metadata:
  name: quickstart
spec:
  version: 8.13.4
  nodeSets:
  - name: default
    count: 1
    config:
      node.store.allow_mmap: false
EOF


# oc port-forward service/quickstart-es-http 9200
# oc port-forward service/quickstart-kb-http 5601


cat <<EOF | oc apply -f -
apiVersion: kibana.k8s.elastic.co/v1
kind: Kibana
metadata:
  name: quickstart
spec:
  version: 8.13.4
  count: 1
  elasticsearchRef:
    name: quickstart
EOF

cat <<EOF | oc apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: logstash
  labels:
    app.kubernetes.io/name: elasticsearch-logstash
    app.kubernetes.io/component: logstash
spec:
  replicas: 1
  selector:
    matchLabels:
      app.kubernetes.io/name: elasticsearch-logstash
      app.kubernetes.io/component: logstash
  template:
    metadata:
      labels:
        app.kubernetes.io/name: elasticsearch-logstash
        app.kubernetes.io/component: logstash
    spec:
      containers:
        - name: logstash
          image: docker.elastic.co/logstash/logstash:8.13.4
          ports:
            - name: "tcp-beats"
              containerPort: 5044
          env:
            - name: ES_HOSTS
              value: "https://quickstart-es-http.default.svc:9200"
            - name: ES_USER
              value: "elastic"
            - name: ES_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: quickstart-es-elastic-user
                  key: elastic
          volumeMounts:
            - name: config-volume
              mountPath: /usr/share/logstash/config
            - name: pipeline-volume
              mountPath: /usr/share/logstash/pipeline
            # - name: ca-certs
            #   mountPath: /etc/logstash/certificates
            #   readOnly: true
      volumes:
        - name: config-volume
          configMap:
            name: logstash-config
        - name: pipeline-volume
          configMap:
            name: logstash-pipeline
        # - name: ca-certs
        #   secret:
        #     secretName: elasticsearch-es-http-certs-public
 
---
 
apiVersion: v1
kind: Service
metadata:
  name: logstash
  labels:
    app.kubernetes.io/name: elasticsearch-logstash
    app.kubernetes.io/component: logstash
spec:
  ports:
    - name: "tcp-beats"
      port: 5044
      targetPort: 5044
  selector:
    app.kubernetes.io/name: elasticsearch-logstash
    app.kubernetes.io/component: logstash
EOF


cat <<EOF | oc apply -f -
apiVersion: v1
kind: ConfigMap
metadata:
  name: logstash-config
  labels:
    app.kubernetes.io/name: elasticsearch-logstash
    app.kubernetes.io/component: logstash
data:
  logstash.yml: |
    http.host: 0.0.0.0
    pipeline.ecs_compatibility: disabled
  pipelines.yml: |
    - pipeline.id: logstash
      path.config: "/usr/share/logstash/pipeline/logstash.conf"
 
  log4j2.properties: |
    logger.logstashpipeline.name = logstash.inputs.beats
    logger.logstashpipeline.level = error
 
---
 
apiVersion: v1
kind: ConfigMap
metadata:
  name: logstash-pipeline
  labels:
    app.kubernetes.io/name: elasticsearch-logstash
    app.kubernetes.io/component: logstash
data:
  logstash.conf: |
    input {
      beats {
        port => 5044
      }
    }
    filter {
      json {
        source => "message"
      }
      prune {
        whitelist_names => [ "msg" ]
      }
      mutate {
        rename => { "msg" => "message" }
      }
    }
    output {
      if [message]  =~ "admission" {
        elasticsearch {
          index => "logstashadmission-%{+YYYY.MM.dd}"
          hosts => [ "\${ES_HOSTS}" ]
          user => "\${ES_USER}"
          password => "\${ES_PASSWORD}"
        }
      }
    }
EOF


cat <<EOF | oc apply -f -
apiVersion: beat.k8s.elastic.co/v1beta1
kind: Beat
metadata:
  name: quickstart
spec:
  type: filebeat
  version: 8.13.4
  # elasticsearchRef:
  #   name: quickstart
  # kibanaRef:
  #   name: kibana
  config:
    filebeat.inputs:
    - type: container
      paths:
      - /var/log/containers/*.log
      processors:
        - add_kubernetes_metadata:
            host: \${NODE_NAME}
            matchers:
            - logs_path:
                logs_path: "/var/log/containers/"
        - drop_event.when:
            or:
            - equals:
                kubernetes.namespace: "kube-system"
            - equals:
                kubernetes.namespace: "kube-public"  
            - equals:
                kubernetes.namespace: "quickstart"
            - equals:
                kubernetes.namespace: "kube-node-lease"
            - equals:
                kubernetes.namespace: "elastic-system"
    output.logstash:
      hosts: ["logstash.default.svc:5044"]
  daemonSet:
    podTemplate:
      spec:
        serviceAccountName: filebeat
        automountServiceAccountToken: true
        terminationGracePeriodSeconds: 30
        tolerations:
        - key: dedicated
          operator: Exists
          effect: NoSchedule       
        dnsPolicy: ClusterFirstWithHostNet
        hostNetwork: true # Allows to provide richer host metadata
        containers:
        - name: filebeat
          securityContext:
            runAsUser: 0
            # If using Red Hat OpenShift uncomment this:
            #privileged: true
          volumeMounts:
          - name: varlogcontainers
            mountPath: /var/log/containers
          - name: varlogpods
            mountPath: /var/log/pods
          - name: varlibdockercontainers
            mountPath: /var/lib/docker/containers
          env:
            - name: NODE_NAME
              valueFrom:
                fieldRef:
                  fieldPath: spec.nodeName
          resources:
            limits:
              cpu: 500m
              memory: 2000Mi
            requests:
              cpu: 100m
              memory: 200Mi
        volumes:
        - name: varlogcontainers
          hostPath:
            path: /var/log/containers
        - name: varlogpods
          hostPath:
            path: /var/log/pods
        - name: varlibdockercontainers
          hostPath:
            path: /var/lib/docker/containers
 
---
 
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: filebeat
rules:
- apiGroups: [""] # "" indicates the core API group
  resources:
  - namespaces
  - pods
  - nodes
  verbs:
  - get
  - watch
  - list
 
---
 
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: filebeat
subjects:
- kind: ServiceAccount
  name: filebeat
  namespace: elk-test
roleRef:
  kind: ClusterRole
  name: filebeat
  apiGroup: rbac.authorization.k8s.io
 
---
 
apiVersion: v1
kind: ServiceAccount
metadata:
  name: filebeat
EOF

cat <<EOF | oc apply -f -
apiVersion: v1
kind: Service

spec:
  type: NodePort
  selector:
    ingresscontroller.operator.openshift.io/deployment-ingresscontroller: default
  ports:
    - name: elastic
      port: 9200
      targetPort: 9200
      nodePort: 30200
EOF

cat <<EOF | oc apply -f -
apiVersion: v1
kind: Service
metadata:
  labels:
    app: es-default-node
  name: es-default-node
  namespace: default
spec:
  ports:
  - name: "9200"
    nodePort: 30020
    port: 9200
    protocol: TCP
    targetPort: 9200
  selector:
    common.k8s.elastic.co/type: elasticsearch
    elasticsearch.k8s.elastic.co/cluster-name: quickstart
  sessionAffinity: None
  type: NodePort
status:
  loadBalancer: {}
EOF