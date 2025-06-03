#### running a elk deployment on k8s
- deployment
    run `./install-elk.sh"
- ports
    the script will expose the deployment running on a nodePort `30200`


#### Getting password for the elk
`oc get secret quickstart-es-elastic-user -n default -o jsonpath='{.data.elastic}' | base64 --decode; echo`