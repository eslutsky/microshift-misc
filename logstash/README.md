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