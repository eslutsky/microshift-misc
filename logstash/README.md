## installation
### install ELK on running k8s cluster
```
./run.sh

```
- will deploy the required manifests
- expose elastic running on nodePort 30200


### accessing the kibana dashboard
```bash
oc port-forward service/quickstart-kb-http 5601
```
- username: elastic
- password `oc get secret quickstart-es-elastic-user -n default -o jsonpath='{.data.elastic}' | base64 --decode; echo`

### loading junits example data to elastic
load junit XMLs files, parse them using logstash parser and sent the errors to elasticsearch.
```bash
podman run -ti -v ./data:/opt/data:Z -v ./logstash.conf:/usr/share/logstash/pipeline/logstash.conf:Z \
-v ./logstash.yml:/usr/share/logstash/config/logstash.yml:Z \
 9c8234d47a7e
```

