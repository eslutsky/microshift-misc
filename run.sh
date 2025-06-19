#!/bin/bash
# Function to run the playbook with specified tags

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"



# Source the venv using the script's directory
source "${SCRIPT_DIR}/venv/bin/activate"

# Initialize inventory_file_arg
inventory_file_arg=""
# Parse options using getopts
# The leading colon in ":i:" enables silent error handling for getopts.
# 'i:' means -i takes an argument.
while getopts ":i:" opt; do
  case ${opt} in
    i )
      inventory_file_arg=$OPTARG
      ;;
    \? )
      echo "Invalid option: -$OPTARG" 1>&2
      exit 1
      ;;
    : )
      echo "Option -$OPTARG requires an argument." 1>&2
      exit 1
      ;;
  esac
done
shift $((OPTIND -1)) # Shift off the processed options and their arguments

run_playbook() {
  local playbook="$1" # Second parameter, defaults to --ci
  local current_extra_args="$2" # Renamed to avoid conflict with global extra_args
  local inventory_override="$3"
  local inventory_to_use=""
  local temp_inventory_created=false

  if [ -n "$inventory_override" ]; then
    if [ -f "$inventory_override" ]; then
      inventory_to_use="$inventory_override"
      echo "Using provided inventory file: $inventory_to_use"
    else
      echo "Error: Provided inventory file '$inventory_override' not found." >&2
      exit 1
    fi
  else
    # Dynamic inventory generation
    echo "Attempting to dynamically generate inventory from AWS EC2 instances..."
    instances=$(aws ec2 describe-instances --filters "Name=instance-state-name,Values=running" --query "Reservations[*].Instances[*].[PublicDnsName,KeyName]" --output json)
    inventory_to_use=$(mktemp)
    temp_inventory_created=true
    echo "Dynamically generated inventory file: $inventory_to_use"

    echo "[aws_hosts]" >> "$inventory_to_use"
    jq -r '.[] | .[] | @tsv' <<< "$instances" | while IFS=$'\t' read -r public_dns_name key_name; do
      if [ -n "$key_name" ] && [ "$key_name" != "null" ]; then
        echo "$public_dns_name ansible_ssh_user=ec2-user ansible_ssh_private_key_file=/path/to/your/keys/$key_name.pem" >> "$inventory_to_use"
      else
        echo "$public_dns_name ansible_ssh_user=ec2-user # Key name not available or null" >> "$inventory_to_use"
      fi
    done
  fi

  # Set ANSIBLE_ROLES_PATH to include the directory relative to the script
  export ANSIBLE_ROLES_PATH="${SCRIPT_DIR}/ansible_roles:${ANSIBLE_ROLES_PATH}"
  echo "ANSIBLE_ROLES_PATH set to: ${ANSIBLE_ROLES_PATH}"

  set -o pipefail
  ansible-playbook -i "$inventory_to_use" "$playbook" ${current_extra_args}  2>&1 | while IFS= read -r line; do printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$line"; done
  
  if [ "$temp_inventory_created" = true ] && [ -f "$inventory_to_use" ]; then
    rm "$inventory_to_use"
  fi
}

# Positional arguments (after options have been shifted by getopts)
mode="${1:-provision}"
env="${2:-upstream}"

# Shift away mode and env to get the remaining extra_args
_argc_after_opts=$#
if [ "$_argc_after_opts" -gt 0 ]; then
  shift # remove mode (or what was $1 after options)
fi
if [ "$_argc_after_opts" -gt 1 ]; then # Check original count of remaining args
  shift # remove env (or what was $2 after options)
fi
extra_args="$@" # The rest are extra_args

echo "Executing with mode: ${mode}, env: ${env}"
if [ -n "$inventory_file_arg" ]; then
  echo "Inventory specified by -i: ${inventory_file_arg}"
fi

case "$mode" in
  "create")
    playbook="${SCRIPT_DIR}/ec2/create-vm-${env}.yaml"
    ;;
  "destroy")
    playbook="${SCRIPT_DIR}/ec2/destroy-vm.yaml"
    ;;
  "cleanup")
    playbook="${SCRIPT_DIR}/ec2/cleanup-old.yaml"
    echo "cleanup mode"
    ;;
  "env")
    export KUBECONFIG=${SCRIPT_DIR}/provision/upstream/fetched_kubeconfigs/kubeconfig
    oc get pods
    exit 0
    ;;
  *)
    playbook="${SCRIPT_DIR}/${mode}/${env}/main.yaml"
    echo "running: $mode ."
    ;;
esac

if [ ! -f "$playbook" ]; then
  echo "Error: Playbook file not found at ${playbook}" >&2
  exit 1
fi

run_playbook "${playbook}" "${extra_args}" "${inventory_file_arg}"
