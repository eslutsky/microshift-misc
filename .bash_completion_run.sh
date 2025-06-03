# Bash completion for run.sh

_run_sh_completions() {
    local cur prev words cword
    _get_comp_words_by_ref -n : cur prev words cword

    local cmd_path="${words[0]}" # The command being completed (e.g., ./run.sh)
    local SCRIPT_DIR_FOR_COMPLETION
    local cmd_path_resolved

    # Resolve the actual script directory
    if [[ "${cmd_path}" == */* ]]; then # Command contains a slash (e.g., ./run.sh or /path/to/run.sh)
        # Resolve to an absolute path first
        cmd_path_resolved="$(cd "$(dirname "${cmd_path}")" &>/dev/null && pwd)/$(basename "${cmd_path}")"
    else # Command does not contain a slash (e.g., run.sh, needs to be found in PATH or CWD)
        local resolved_in_path
        resolved_in_path=$(type -P "${cmd_path}") # Check PATH
        if [[ -n "${resolved_in_path}" ]]; then
            cmd_path_resolved="${resolved_in_path}"
        elif [ -f "./${cmd_path}" ]; then # Fallback: command not in PATH. Check if it's a file in the current directory.
             cmd_path_resolved="$(pwd)/${cmd_path}"
        else
            # Cannot reliably determine script path to resolve its directory
            return 1
        fi
    fi

    # Now resolve SCRIPT_DIR_FOR_COMPLETION from the actual script file, handling symlinks
    if [ -L "${cmd_path_resolved}" ]; then # If it's a symlink
        local actual_script_path
        actual_script_path=$(readlink -f "${cmd_path_resolved}")
        SCRIPT_DIR_FOR_COMPLETION="$(cd "$(dirname "${actual_script_path}")" &>/dev/null && pwd)"
    elif [ -f "${cmd_path_resolved}" ]; then # If it's a regular file (or symlink target if -f follows symlinks on your system)
        SCRIPT_DIR_FOR_COMPLETION="$(cd "$(dirname "${cmd_path_resolved}")" &>/dev/null && pwd)"
    else # Script not found or not a file/symlink after resolution
        return 1
    fi

    if [ ! -d "${SCRIPT_DIR_FOR_COMPLETION}" ]; then
        # Could not determine SCRIPT_DIR_FOR_COMPLETION, cannot proceed
        return 1
    fi

  #  echo "DEBUG: SCRIPT_DIR_FOR_COMPLETION='${SCRIPT_DIR_FOR_COMPLETION}'" >&2

    # Mode completion (first argument)
    if [ "$cword" -eq 1 ]; then
        # Static modes from the case statement in run.sh, plus 'provision' (default)
        local modes_list=("create" "destroy" "cleanup" "env" "provision")

        # Dynamically add other directories from SCRIPT_DIR_FOR_COMPLETION as potential modes
        # These are directories that would fit the ${SCRIPT_DIR}/${mode}/${env}/main.yaml pattern
        if [ -d "${SCRIPT_DIR_FOR_COMPLETION}" ]; then
            for item in "${SCRIPT_DIR_FOR_COMPLETION}"/*; do
                if [ -d "${item}" ]; then
                    local dir_name
                    dir_name=$(basename "${item}")
                    # Exclude known non-mode directories and already listed ones
                    if [[ "$dir_name" != "ec2" && "$dir_name" != "venv" && \
                          ! " ${modes_list[*]} " =~ " ${dir_name} " ]]; then
                        # Check if this directory likely contains env subdirs with main.yaml
                        if compgen -G "${SCRIPT_DIR_FOR_COMPLETION}/${dir_name}/*/main.yaml" > /dev/null; then
                             modes_list+=("$dir_name")
                        fi
                    fi
                fi
            done
        fi
        
        local unique_modes_str
        unique_modes_str=$(printf "%s\n" "${modes_list[@]}" | sort -u | xargs)
        COMPREPLY=( $(compgen -W "${unique_modes_str}" -- "${cur}") )

       #return 0
    fi

    # Env completion (second argument)
    if [ "$cword" -eq 2 ]; then
        local current_mode="${words[1]}"
        local env_suggestions=()

        # Always add 'upstream' as it's a common default and explicitly mentioned in run.sh
        env_suggestions+=("upstream")

        case "$current_mode" in
            "create")
                # Playbook: ${SCRIPT_DIR}/ec2/create-vm-${env}.yaml
                if [ -d "${SCRIPT_DIR_FOR_COMPLETION}/ec2" ]; then
                    local found_envs
                    # Extracts 'xxx' from 'create-vm-xxx.yaml'
                    found_envs=$(find "${SCRIPT_DIR_FOR_COMPLETION}/ec2" -maxdepth 1 -name "create-vm-*.yaml" -printf "%f\n" 2>/dev/null | \
                                 sed -n 's/^create-vm-\(.*\)\.yaml$/\1/p')
                    for env_val in $found_envs; do
                         env_suggestions+=("$env_val")
                    done
                fi
                ;;
            "destroy"|"cleanup"|"env")
                # These modes default 'env' to 'upstream' in run.sh.
                # 'upstream' is already added to suggestions.
                ;;
            *) # Default case for modes like "provision" or other custom modes
               # Playbook: ${SCRIPT_DIR}/${mode}/${env}/main.yaml
               # List subdirectories of ${SCRIPT_DIR_FOR_COMPLETION}/${current_mode} that contain main.yaml
                if [ -d "${SCRIPT_DIR_FOR_COMPLETION}/${current_mode}" ]; then
                    for item in "${SCRIPT_DIR_FOR_COMPLETION}/${current_mode}"/*; do
                        if [ -d "${item}" ]; then # Check if item is a directory
                            if [ -f "${item}/main.yaml" ]; then # And contains main.yaml
                                local env_candidate
                                env_candidate=$(basename "${item}")
                                env_suggestions+=("$env_candidate")
                            fi
                        fi
                    done
                fi
                ;;
        esac
        
        local unique_env_suggestions_str
        unique_env_suggestions_str=$(printf "%s\n" "${env_suggestions[@]}" | sort -u | xargs)
        COMPREPLY=( $(compgen -W "${unique_env_suggestions_str}" -- "${cur}") )
        #echo "DEBUG: COMPREPLY for modes: '${COMPREPLY[*]}'" >&2
        return 0
    fi
    
    # Completion for extra_args (arguments after mode and env)
    if [ "$cword" -gt 2 ]; then
        # Suggest common ansible-playbook options
        local ansible_common_opts="--tags= --skip-tags= -e --limit= --check --diff -v -vv -vvv"
        COMPREPLY=( $(compgen -W "${ansible_common_opts}" -- "${cur}") )
        #echo "DEBUG: COMPREPLY for modes: '${COMPREPLY[*]}'" >&2

        return 0
    fi

  #  return 0
}

# Register the completion function for your script
# You can add more ways you call the script (e.g., if it's in your PATH as 'run.sh')
complete -F _run_sh_completions ./run.sh run.sh /home/eslutsky/dev/microshift-misc/run.sh
