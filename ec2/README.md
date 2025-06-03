### ansible automation to provision ec2 instances 


## finding ami-ids for Centos
```bash
#!/bin/bash

# 1. Iterate through all AWS regions
for region in $(aws ec2 describe-regions --query 'Regions[].RegionName' --output text); do
  # 2. For each region, print the region name and then find the latest CentOS Stream 9 AMI
  echo "$region $(
    aws --region $region ec2 describe-images \
      --owners 125523088429 \
      --query 'Images[?starts_with(Name, `CentOS Stream 9 x86_64`) == `true`].[ImageId,Name,CreationDate]|reverse(sort_by(@,&[2]))[0:1]' \
      --output text
  )"
done
```
