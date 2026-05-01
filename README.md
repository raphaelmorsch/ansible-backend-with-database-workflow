# Ansible Automation Platform and Terraform integration

This repository demonstrates **integration between Ansible Automation Platform (AAP)** and **Terraform**, so automation can orchestrate infrastructure workflows alongside configuration and operational tasks.

Typical use cases include triggering Terraform runs from Ansible (for example against **Terraform Enterprise** or **HCP Terraform**), then consuming outputs or coordinating follow-up playbooks.

## Repository layout

| Path | Purpose |
|------|---------|
| `playbooks/terraform/start-run.yaml` | Ansible playbook that starts a Terraform run via the Terraform Cloud/Enterprise API (`POST /api/v2/runs`). |
| `playbooks/hcl/main.tf` | Sample Terraform configuration exposing outputs for a database-related EC2 instance (public IP, private IP, SSH user). |

## Prerequisites

- **Ansible** (or run the playbook from AAP with appropriate credentials and execution environment).
- A **Terraform Cloud / Enterprise** API token in the environment variable `TFE_TOKEN`.
- Terraform organization URL and a target **workspace ID** configured in the playbook (replace placeholders in `start-run.yaml`).

## Using the Terraform trigger playbook

1. Export your API token:

   ```bash
   export TFE_TOKEN="<your-terraform-cloud-api-token>"
   ```

2. Edit `playbooks/terraform/start-run.yaml` and set:

   - `tfe_url` — your Terraform Cloud hostname (for example `https://app.terraform.io`) or Terraform Enterprise base URL.
   - `workspace_id` — the workspace where the run should be queued.

3. Run the playbook from the repository root (adjust inventory if you use more than `localhost`):

   ```bash
   ansible-playbook playbooks/terraform/start-run.yaml
   ```

The playbook registers the created run and sets `run_id` from the API response for use in later tasks or workflows.

## Terraform configuration

`playbooks/hcl/main.tf` is intended to live in or mirror the Terraform workspace you target from Ansible. Apply it with your normal Terraform workflow (`terraform init`, `plan`, `apply`) or let the run triggered by Ansible execute in your remote backend.

## Contributing

Improvements to playbooks, variables (for example moving secrets and IDs into AAP **credentials** or **survey** fields), and documentation are welcome. Keep sensitive values out of git; use environment variables or AAP’s secret storage.
