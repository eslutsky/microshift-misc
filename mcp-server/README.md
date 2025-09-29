# MicroShift MCP Server

## Description

The MicroShift MCP (Model Context Protocol) Server is an intelligent automation tool that provides seamless creation and configuration of MicroShift instances on AWS EC2. This server acts as a bridge between development environments and cloud infrastructure, enabling developers to quickly spin up MicroShift environments for various purposes.

## Key Features

### Infrastructure Management
- **EC2 Instance Provisioning**: Automated creation and configuration of EC2 instances optimized for MicroShift
- **Ansible Integration**: Leverages Ansible playbooks for consistent and repeatable infrastructure setup
- **Git Source Support**: Create instances directly from Git repositories and pull requests
  - Build and deploy from specific commits or branches
  - Support for testing pull requests before merging
  - Automated CI/CD pipeline integration

### Agentic Environment Creation
- **Multi-Purpose Environments**: Supports different environment types for various use cases:
  - **QE (Quality Engineering)**: Testing and validation environments
  - **DEV (Development)**: Development and experimentation environments  
  - **DOC (Documentation)**: Documentation and demo environments
- **Intelligent Provisioning**: AI-driven decision making for optimal resource allocation
- **Environment Lifecycle Management**: Automated cleanup and resource optimization

### IDE Integration
- **Cursor IDE Support**: Native integration with Cursor IDE for seamless development workflow
- **MCP Protocol**: Implements Model Context Protocol for enhanced AI-assisted development
- **Real-time Feedback**: Provides status updates and logs directly in the development environment
- **One-Click Deployment**: Deploy MicroShift environments with simple commands from your IDE

## Benefits

- **Rapid Prototyping**: Quickly create isolated MicroShift environments for testing new features
- **Cost Optimization**: Intelligent resource management and automated cleanup
- **Developer Productivity**: Reduces setup time from hours to minutes
- **Consistent Environments**: Ensures reproducible setups across different use cases
- **CI/CD Integration**: Seamlessly integrates with existing development workflows

## Use Cases

- Testing MicroShift features and configurations
- Validating pull requests in isolated environments
- Creating demo environments for documentation
- Developing and testing MicroShift-based applications
- Training and educational purposes