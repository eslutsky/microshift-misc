#!/bin/bash
# Function to run the playbook with specified tags

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Source the venv using the script's directory
source "${SCRIPT_DIR}/venv/bin/activate"

run_playbook() {
  local mode="$1"
  local playbook="${SCRIPT_DIR}/upstream/install-microshift-okd.yaml"
  local tags=""
  local instance_ids=""

  case "$mode" in
    "provision")
      playbook="${SCRIPT_DIR}/ec2/provision-vm.yaml"
      ;;
    "deprovision")
      playbook="${SCRIPT_DIR}/ec2/deprovision-vm.yaml"
      ;;
    "cleanup")
      playbook="${SCRIPT_DIR}/ec2/cleanup-old.yaml"
      echo "cleanup mode"
      ;;
    *)
      echo "Invalid mode: $mode.  Defaulting to configure."
      ;;
  esac

  # Get instance information from AWS (only for configure mode)
  if [ "$mode" == "configure" ]; then
    instances=$(aws ec2 describe-instances --filters "Name=instance-state-name,Values=running" --query "Reservations[*].Instances[*].[PublicDnsName,KeyName]" --output json)

    # Create a temporary inventory file
    inventory_file=$(mktemp)

    # Write the inventory to the file
    echo "[aws_hosts]" > "$inventory_file"
    jq -r '.[] | .[] | @tsv' <<< "$instances" | while IFS=$'\t' read -r public_dns_name key_name; do
      echo "$public_dns_name ansible_ssh_private_key_file=/path/to/your/keys/$key_name.pem" >> "$inventory_file"
    done
    ansible-playbook -i "$inventory_file" "$playbook" 
    rm "$inventory_file"
  elif [ "$mode" == "cleanup" ]; then
    DEPROVISION_INSTANCE_IDS=$instance_ids ansible-playbook "$playbook"
  else


    ansible-playbook "$playbook"
  fi
}

# Get the mode from the first argument, default to "configure"
mode="${1:-configure}"
run_playbook "$mode"
