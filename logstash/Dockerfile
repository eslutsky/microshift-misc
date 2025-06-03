FROM docker.elastic.co/logstash/logstash:8.7.1

USER root
RUN apt-get update && \
  apt-get install netcat -y --no-install-recommends && \
  apt-get clean && \
  rm -rf /var/lib/apt/lists/*

USER logstash