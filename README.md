


## Steps for creating test VMs on aws
### Provisioning Steps

1. **Optionally create a VM**  
   You can create a VM for your environment using ansible aws cloudformation wrapper.

   - **A. Configure the environment:**  
     Edit the configuration in `ec2/create-vm-<ENV-NAME>.yaml` to match your requirements.

   - **B. Run the EC2 VM creation playbook:**  
     Use the following command to create the VM:  
     ```
     ./run.sh create <ENV-NAME>
     ```
     *Note: If the VM is not created using the `./run.sh create` automation, you can provide an Ansible inventory file manually for subsequent steps.*

    **Example: Creating an "upstream" VM**

    To create a VM for the "upstream" environment, run: `./run.sh create upstream`


## Running the CI Provisioning Playbook

### Provisioning a VM

Provisioning a VM means running a set of configuration tasks on that VM to prepare it for testing or development. This process can use a VM that was previously created (for example, using AWS CloudFormation stacks), or a VM specified in an Ansible inventory file.

The provisioning step applies the necessary setup for a specific pull request (PR), such as:
- Installing required packages
- Configuring services
- Setting up the environment

To start the provisioning process for a given PR using Ansible automation, use the following command:
```
PR_NUMBER=5041 ./run.sh provision <ENV-NAME> [-i inventory/filename]
```
> **Note:**  
> `<ENV-NAME>` refers to the environment name you want to provision (for example, `upstream`, `ci-pr`, etc).  
> When you run `./run.sh provision <ENV-NAME>`, it executes the Ansible tasks defined in `./provision/<ENV-NAME>/main.yaml` to set up that environment.

## Handling Long-Running and Interactive Tasks

Some provisioning or setup tasks may take a long time to complete, or may require user interaction (for example, providing Red Hat Subscription Management (RHSM) registration credentials). If a task is expected to require user input, this will be indicated in the task name or description shown in the Ansible output. In these cases, the automation may start a process in a remote `tmux` session on the VM.

**How to Connect to a Remote tmux Session:**

1. **SSH into the VM:**
   Use your SSH key to connect to the VM. For example:
   ```
   ssh -i /path/to/your/key.pem ec2-user@<VM_PUBLIC_IP>
   ```

2. **List Available tmux Sessions:**
   Once connected, list the running tmux sessions:
   ```
   tmux ls
   ```
   You should see a session name related to the provisioning task (e.g., `provision`, `setup`, or similar).

3. **Attach to the tmux Session:**
   Attach to the session to view progress or provide input:
   ```
   tmux attach-session -t <session_name>
   ```
   Replace `<session_name>` with the actual name from the previous step.

4. **Provide Required Input:**
   If prompted (for example, for RHSM credentials), enter the required information directly in the tmux session.

5. **Detach from tmux (Optional):**
   To leave the session running in the background, press `Ctrl+b` then `d`.

**Notes:**
- The automation will typically print instructions or the tmux session name in the Ansible output if user interaction is required.
- You can re-attach to the tmux session at any time to check progress or provide further input.

This approach ensures that long-running or interactive tasks do not block the automation and can be completed at your convenience.
