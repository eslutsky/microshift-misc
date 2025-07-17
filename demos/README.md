- #### Create EC2  Centos instance
	- `./run.sh create upstream`
	  ```
	  Executing with mode: create, env: upstream
	  Attempting to dynamically generate inventory from AWS EC2 instances...
	  Dynamically generated inventory file: /tmp/tmp.XRoRYBfsNi
	  ANSIBLE_ROLES_PATH set to: /home/eslutsky/dev/microshift-misc/ansible_roles:
	  [2025-07-17 07:50:58] [WARNING]: provided hosts list is empty, only localhost is available. Note that
	  [2025-07-17 07:50:58] the implicit localhost does not match 'all'
	  [2025-07-17 07:50:58] 
	  [2025-07-17 07:50:58] PLAY [localhost] ***************************************************************
	  [2025-07-17 07:50:58] 
	  [2025-07-17 07:50:58] TASK [download microshift latest RPMs from github] *****************************
	  [2025-07-17 07:50:58] included: create-vm for localhost
	  [2025-07-17 07:50:58] 
	  [2025-07-17 07:50:58] TASK [create-vm : creating VM with the following parameters using CloudFormation] ***
	  [2025-07-17 07:50:58] ok: [localhost] => {
	  [2025-07-17 07:50:58]     "msg": [
	  [2025-07-17 07:50:58]         "Region: eu-west-1",
	  [2025-07-17 07:50:58]         "Stack Name: eslutsky-stack",
	  [2025-07-17 07:50:58]         "Instance Type: m4.4xlarge",
	  [2025-07-17 07:50:58]         "AMI ID: ami-0377415b3fa05f234",
	  [2025-07-17 07:50:58]         "Public Key Path: /home/eslutsky/.ssh/id_rsa.pub",
	  [2025-07-17 07:50:58]         "CloudFormation Template File: template/aws-template.yaml",
	  [2025-07-17 07:50:58]         "Host Device Name: /dev/xvdc"
	  [2025-07-17 07:50:58]     ]
	  [2025-07-17 07:50:58] }
	  [2025-07-17 07:50:58] 
	  [2025-07-17 07:50:58] TASK [create-vm : Create CloudFormation stack] *********************************
	  [2025-07-17 07:53:36] [DEPRECATION WARNING]: Param 'template' is deprecated. See the module docs for 
	  [2025-07-17 07:53:36] more information. This feature will be removed from amazon.aws in a release 
	  [2025-07-17 07:53:36] after 2026-05-01. Deprecation warnings can be disabled by setting 
	  [2025-07-17 07:53:36] deprecation_warnings=False in ansible.cfg.
	  [2025-07-17 07:53:36] changed: [localhost]
	  [2025-07-17 07:53:36] 
	  [2025-07-17 07:53:36] TASK [create-vm : Wait for stack creation to complete] *************************
	  [2025-07-17 07:53:36] changed: [localhost]
	  [2025-07-17 07:53:36] 
	  [2025-07-17 07:53:36] TASK [create-vm : Describe CloudFormation stack] *******************************
	  [2025-07-17 07:53:37] changed: [localhost]
	  [2025-07-17 07:53:37] 
	  [2025-07-17 07:53:37] TASK [create-vm : Extract instance ID] *****************************************
	  [2025-07-17 07:53:37] ok: [localhost]
	  [2025-07-17 07:53:37] 
	  [2025-07-17 07:53:37] TASK [create-vm : Wait for instance status to be OK] ***************************
	  [2025-07-17 07:54:39] changed: [localhost]
	  [2025-07-17 07:54:39] 
	  [2025-07-17 07:54:39] TASK [create-vm : Get public IP address] ***************************************
	  [2025-07-17 07:54:40] ok: [localhost]
	  [2025-07-17 07:54:40] 
	  [2025-07-17 07:54:40] TASK [create-vm : Display public IP address] ***********************************
	  [2025-07-17 07:54:40] ok: [localhost] => {
	  [2025-07-17 07:54:40]     "msg": "Public IP address: 3.254.84.226"
	  [2025-07-17 07:54:40] }
	  [2025-07-17 07:54:40] 
	  [2025-07-17 07:54:40] TASK [create-vm : Set public IP as a fact for later use] ***********************
	  [2025-07-17 07:54:40] ok: [localhost]
	  [2025-07-17 07:54:40] 
	  [2025-07-17 07:54:40] PLAY RECAP *********************************************************************
	  [2025-07-17 07:54:40] localhost                  : ok=10   changed=4    unreachable=0    failed=0    skipped=0    rescued=0    ignored=0   
	  [2025-07-17 07:54:40] 
	  
	  ```
- #### Provision Microshift Upsream
	- `./run.sh provision upstream`
	  ```
	  2025-07-17 08:02:45] TASK [microshift-okd-bootc : fetch kubeconfig from bootc container] ************
	  [2025-07-17 08:02:45] included: /home/eslutsky/dev/microshift-misc/provision/upstream/roles/microshift-okd-bootc/tasks/fetch-kubeconfig.yaml for ec2-3-254-84-226.eu-west-1.compute.amazonaws.com
	  [2025-07-17 08:02:45] 
	  [2025-07-17 08:02:45] TASK [microshift-okd-bootc : Define kubeconfig paths] **************************
	  [2025-07-17 08:02:45] ok: [ec2-3-254-84-226.eu-west-1.compute.amazonaws.com]
	  [2025-07-17 08:02:45] 
	  [2025-07-17 08:02:45] TASK [microshift-okd-bootc : Ensure local destination directory for kubeconfig exists] ***
	  [2025-07-17 08:02:46] ok: [ec2-3-254-84-226.eu-west-1.compute.amazonaws.com -> localhost]
	  [2025-07-17 08:02:46] 
	  [2025-07-17 08:02:46] TASK [microshift-okd-bootc : Copy kubeconfig from container to remote host's temporary location] ***
	  [2025-07-17 08:02:47] changed: [ec2-3-254-84-226.eu-west-1.compute.amazonaws.com]
	  [2025-07-17 08:02:47] 
	  [2025-07-17 08:02:47] TASK [microshift-okd-bootc : Ensure the destination directory for kubeconfig exists on the remote host] ***
	  [2025-07-17 08:02:49] changed: [ec2-3-254-84-226.eu-west-1.compute.amazonaws.com]
	  [2025-07-17 08:02:49] 
	  [2025-07-17 08:02:49] TASK [microshift-okd-bootc : Copy kubeconfig to its standard remote location on the MicroShift host] ***
	  [2025-07-17 08:02:50] changed: [ec2-3-254-84-226.eu-west-1.compute.amazonaws.com]
	  [2025-07-17 08:02:50] 
	  [2025-07-17 08:02:50] TASK [microshift-okd-bootc : Fetch kubeconfig from remote host to localhost] ***
	  [2025-07-17 08:02:52] changed: [ec2-3-254-84-226.eu-west-1.compute.amazonaws.com]
	  [2025-07-17 08:02:52] 
	  [2025-07-17 08:02:52] TASK [microshift-okd-bootc : Print KUBECONFIG] *********************************
	  [2025-07-17 08:02:52] ok: [ec2-3-254-84-226.eu-west-1.compute.amazonaws.com] => {
	  [2025-07-17 08:02:52]     "msg": "export KUBECONFIG=/home/eslutsky/dev/microshift-misc/provision/upstream/fetched_kubeconfigs/kubeconfig"
	  [2025-07-17 08:02:52] }
	  [2025-07-17 08:02:52] 
	  [2025-07-17 08:02:52] PLAY RECAP *********************************************************************
	  [2025-07-17 08:02:52] ec2-3-254-84-226.eu-west-1.compute.amazonaws.com : ok=47   changed=19   unreachable=0    failed=0    skipped=3    rescued=0    ignored=1
	  ```
- #### Provision ELK Stack
	- `./run.sh provision elk`
	  ```
	  2025-07-17 08:35:45] TASK [elk-stack : Display access information] **********************************
	  [2025-07-17 08:35:45] ok: [localhost] => {
	  [2025-07-17 08:35:45]     "msg": [
	  [2025-07-17 08:35:45]         "ELK Stack has been deployed successfully!",
	  [2025-07-17 08:35:45]         "Elasticsearch is available at: https://ec2-3-254-84-226.eu-west-1.compute.amazonaws.com:30020",
	  [2025-07-17 08:35:45]         "Kibana is available at: https://ec2-3-254-84-226.eu-west-1.compute.amazonaws.com:30021",
	  [2025-07-17 08:35:45]         "Username: elastic",
	  [2025-07-17 08:35:45]         "Password: XXXXXXX"
	  [2025-07-17 08:35:45]     ]
	  [2025-07-17 08:35:45] }
	  [2025-07-17 08:35:45] 
	  [2025-07-17 08:35:45] PLAY RECAP *********************************************************************
	  [2025-07-17 08:35:45] localhost                  : ok=23   changed=16   unreachable=0    failed=0    skipped=0    rescued=0    ignored=0
	  ```
	-
	- kibana is publicly available  at https://ec2-3-254-84-226.eu-west-1.compute.amazonaws.com:30021
	  with the generated Password.  
	-
- #### Download the junit data from PROW
- #### Load the junit data into the dashboard
	- `cd logstash/ && ./run.sh`
	  ```
	  Extracted Elasticsearch host: ec2-3-254-84-226.eu-west-1.compute.amazonaws.com
	  Updated logstash configuration files with host: ec2-3-254-84-226.eu-west-1.compute.amazonaws.com
	  Extracting Elasticsearch password...
	  Successfully extracted Elasticsearch password
	  Updated logstash configuration files with new password
	  Using bundled JDK: /usr/share/logstash/jdk
	  Sending Logstash logs to /usr/share/logstash/logs which is now configured via log4j2.properties
	  [2025-07-17T07:00:01,431][INFO ][logstash.runner          ] Log4j configuration path used is: /usr/share/logstash/config/log4j2.properties
	  [2025-07-17T07:00:01,434][INFO ][logstash.runner          ] Starting Logstash {"logstash.version"=>"8.7.1", "jruby.version"=>"jruby 9.3.10.0 (2.6.8) 2023-02-01 107b2e6697 OpenJDK 64-Bit Server VM 17.0.7+7 on 17.0.7+7 +indy +jit [x86_64-linux]"}
	  
	  ```
	- it will run the logstash container and load the data in ./data folder
	- logstash will continue running at the background monitoring for new junits in ./data folder
	- parsing configuration is found in logstash/logstash.conf

    - Important Fields
        - job_id
            - as it appear at prow
        - classname
            - name of the test as it extracted from RF framework
-
