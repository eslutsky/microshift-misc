#!/bin/bash
# Function to run the playbook with specified tags

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"



# Source the venv using the script's directory
source "${SCRIPT_DIR}/venv/bin/activate"

run_playbook() {
  local playbook="$1" # Second parameter, defaults to --ci
  local extra_args="$2"
  instances=$(aws ec2 describe-instances --filters "Name=instance-state-name,Values=running" --query "Reservations[*].Instances[*].[PublicDnsName,KeyName]" --output json)

  # Create a temporary inventory file
  inventory_file=$(mktemp)

  # Write the inventory to the file
  echo "[aws_hosts]" > "$inventory_file"
  jq -r '.[] | .[] | @tsv' <<< "$instances" | while IFS=$'\t' read -r public_dns_name key_name; do
    echo "$public_dns_name ansible_ssh_private_key_file=/path/to/your/keys/$key_name.pem" >> "$inventory_file"
  done
  ansible-playbook -i "$inventory_file" "$playbook" ${extra_args}
  rm "$inventory_file"
}

# Get the mode from the first argument, default to "configure"
# Get the upstream type from the second argument. If not provided, it will be empty,
# and the function's default will apply.
mode="${1:-provision}"
env="${2:-upstream}"
shift 2
extra_args="$@"


  echo "Executing with mode: ${mode}, env: ${env}"

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


run_playbook "${playbook}" "${extra_args}"
