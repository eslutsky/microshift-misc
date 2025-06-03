#!/bin/bash


podman run -ti -v ./data:/opt/data:Z -v ./logstash.conf:/usr/share/logstash/pipeline/logstash.conf:Z \
-v ./logstash.yml:/usr/share/logstash/config/logstash.yml:Z \
 9c8234d47a7e