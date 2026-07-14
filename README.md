# vSphere + k3s Observability Lab

A self-hosted virtualization, orchestration, and observability lab — built to explore how a VMware vSphere environment, a lightweight Kubernetes cluster, and a full monitoring stack fit together, end to end.

![Grafana Dashboard](docs/screenshots/grafana-node-exporter.png)

## Context

This project started during an internship at **Société Monétique Tunisie (SMT)**, Tunisia's national interbank switching company. The internship came without an assigned project or access to production systems — a reasonable constraint, given SMT's environment runs live banking infrastructure (a VMware vSphere/ESXi stack of roughly 600 VMs, monitored via SolarWinds).

Rather than wait for direction, I built a self-contained lab mirroring the same architectural pattern — hypervisor, orchestration, monitoring — on my own hardware. The goal was to actually understand the full stack hands-on, not just watch it exist.

**Note on this README:** I used AI (Claude) to help organize and structure this document  deciding what to cover and how to lay it out , and also some parts of the project like aws-cost-mapping and the ansible playbook . The content itself  the architecture, the decisions, the debugging, the code is mine, built and tested on infrastructure I set up and run myself on my personal device.

## Architecture

![Architecture Diagram](docs/architecture.png)

**Stack summary:**
- **Host:** Windows 11 → VMware Workstation Pro → nested ESXi 7.0.3 (evaluation license, standalone — no vCenter)
- **4 VMs on ESXi:**
  - `ubuntu` — k3s control-plane
  - `k3s-node-1`, `k3s-node-2` — k3s workers
  - `monitoring` — Prometheus, Grafana (via Docker Compose), Ansible control node, custom vSphere exporter
- **Orchestration:** k3s (lightweight Kubernetes), chosen for its small footprint given hardware constraints
- **Observability:** three independent layers feeding one Prometheus instance:
  - `node-exporter` — system-level metrics (CPU/RAM/disk/network) per VM
  - `kube-state-metrics` — Kubernetes object-level metrics (pod status, deployments, node conditions)
  - custom `vsphere-exporter` (this repo) — vSphere-layer metrics (per-VM CPU/memory, datastore capacity, host stats) via `pyvmomi`
- **Automation:** Ansible (configuration management across all 3 k3s nodes), Terraform (intended provisioning layer — see limitation below)

## Key engineering decisions

**Why k3s instead of full Kubernetes.** Given the hardware budget (24GB RAM shared across nested ESXi, guest VMs, and the Windows host), k3s's lightweight footprint made a multi-node cluster feasible at all. It's still full, production-grade Kubernetes — this mirrors how k3s is actually used in real edge/resource-constrained deployments.

**Why Terraform is present but not the active provisioning tool.** Terraform's `vsphere_virtual_machine` resource supports cloning VMs via a `clone` block — but this feature requires **vCenter Server**; it is not available against standalone ESXi, even under an evaluation license. This was discovered directly (`Error: use of the clone sub-resource block requires vCenter`) rather than assumed. The Terraform configuration is kept in [`terraform/`](terraform/) as the intended design for a vCenter-managed environment — it would work unmodified if pointed at real vCenter. In this lab, node provisioning is instead handled by [`scripts/clone_node.sh`](scripts/clone_node.sh), a POSIX shell script run directly on the ESXi host via `vmkfstools` (disk clone) and `vim-cmd solo/registervm` (VM registration) — the CLI-level equivalent of what Terraform would otherwise automate.

**Why monitoring runs externally, not in-cluster.** Prometheus and Grafana run on a dedicated VM outside the k3s cluster, via Docker Compose, rather than deployed inside the cluster (e.g. via the kube-prometheus-stack Helm chart). This keeps monitoring independent of the health of the thing it's observing — if the cluster has issues, the monitoring stack watching it isn't also at risk — and was lighter on resources for this lab's constraints.

**Why a custom exporter instead of relying only on community tooling.** `node-exporter` and `kube-state-metrics` cover the system and Kubernetes layers, but neither exposes vSphere-level state (VM power state, datastore capacity, host resource usage as seen by the hypervisor). [`vsphere-exporter/vsphere_exporter.py`](vsphere-exporter/vsphere_exporter.py) fills that gap — it connects directly to the ESXi host's vSphere API via `pyvmomi` (the same API vCenter is built on) and exposes the results in Prometheus format, giving three layers of observability: **vSphere → Kubernetes → System**.

## Repository structure

```
├── terraform/              
├── ansible/                 
│   ├── inventory.ini.example
│   ├── ansible.cfg
│   ├── node_exporter.yml
│   ├── ufw_setup.yml
│   └── ...
├── vsphere-exporter/       
│   ├── vsphere_exporter.py
│   └── vsphere-exporter.service
├── aws-cost-mapping/       
│   └── cost_mapping.py
├── scripts/
│   └── clone_node.sh        
├── monitoring/
│   ├── docker-compose.yml
│   └── prometheus/
│       └── prometheus.yml
└── docs/
    ├── architecture.png
    └── screenshots/
```

## Observability stack

Prometheus scrapes three independent target types:

| Job | Source | Port | What it exposes |
|---|---|---|---|
| `node-exporter` | all 3 k3s nodes | `9100` | CPU, memory, disk, network per VM |
| `kube-state-metrics` | k3s cluster (NodePort) | `30080` | Pod status, deployments, node conditions |
| `vsphere-exporter` | monitoring VM (this repo) | `9272` | VM CPU/memory, datastore capacity, host stats |

Grafana visualizes all three: the community "Node Exporter Full" dashboard (ID 1860) for system metrics, a Kubernetes cluster dashboard for kube-state-metrics, and a custom-built dashboard for the vSphere layer (queries in [`vsphere-exporter/`](vsphere-exporter/)).

## Automation with Ansible

Rather than configuring all 3 k3s nodes by hand, [`ansible/`](ansible/) contains playbooks for:
- `node_exporter.yml` — installs and configures node-exporter as a systemd service across all nodes, idempotently
- `ufw_setup.yml` — configures UFW firewall rules (SSH, k3s API, kubelet, Flannel overlay, node-exporter, NodePort range) with a safe default-deny incoming policy

Passwordless SSH (key-based auth) and passwordless sudo (`NOPASSWD`) on the target nodes allow these playbooks to run unattended, the same pattern used by real automation/CI systems.

## Setup (approximate reproduction steps)

This lab isn't a one-command deploy — reproducing it means: nested ESXi on VMware Workstation, a base Ubuntu Server VM converted into a clone source, 2 additional nodes cloned via `scripts/clone_node.sh`, k3s installed on all 3 (`curl -sfL https://get.k3s.io | sh -` on the control-plane, agent join on the workers), a separate monitoring VM running Docker Compose with the stack in `monitoring/`, and the exporter in `vsphere-exporter/` deployed as a systemd service with `ESXI_HOST`/`ESXI_USER`/`ESXI_PASSWORD` environment variables set.

## AWS cost mapping

This module answers a simple question: *if these VMs were lifted onto AWS, what would they roughly cost?*

**What it does:**
1. Queries Prometheus for each VM's *allocated* resources (vCPU count, RAM) — sourced from two metrics added to the custom `vsphere-exporter` (`vsphere_vm_num_cpu`, `vsphere_vm_memory_size_mb`), pulled directly from the vSphere API via `pyvmomi` (`vm.config.hardware.numCPU` / `.memoryMB`).
2. Matches each VM against a small reference table of common EC2 instance types, picking the cheapest instance type that meets or exceeds the VM's actual vCPU/RAM.
3. Sums the monthly on-demand cost across all VMs to produce a rough total.

**Sample output:**
```
VM              vCPU   RAM(MB)    Best EC2 Match   Monthly $
------------------------------------------------------------
k3s-node-1      2      2048       t3.small         $15.18
k3s-node-2      2      2048       t3.small         $15.18
monitoring      3      3072       t3.xlarge        $121.47
ubuntu server   2      2048       t3.small         $15.18
------------------------------------------------------------
Estimated total monthly cost (EC2 equivalent, On-Demand): $167.01
```

**Known simplifications:**
- Pricing is a static, manually-sourced reference table (us-east-1, Linux On-Demand, June 2026), not a live AWS Pricing API call — avoids both the ~8GB unfiltered bulk pricing dataset and the AWS credential requirement of the filtered Price List Query API.
- Matching is based on allocated vCPU/RAM only; a real rightsizing assessment would use actual utilization data (which the exporter also collects — `vsphere_vm_cpu_usage_mhz`, `vsphere_vm_memory_usage_mb`) to avoid over-provisioning recommendations, and would factor in storage/data-transfer costs, which this script does not.
- The instance-type reference table is intentionally small (8 entries); a sparse table can produce misleading matches — an early version of this script matched a 4-vCPU VM to `m5.xlarge` simply because no smaller-family option existed in the table, before `t3.xlarge` was added.

## Limitations & future work

- **vCenter Server** is not deployed (hardware constraints) — Terraform's clone workflow and vSphere CPI/CSI integration for Kubernetes both require it, and remain designed-for-but-not-implemented here.
- **AWS cost-mapping** currently uses a static pricing snapshot; a production version would query the AWS Price List API directly for live, region-specific rates.
- A 3rd k3s worker node was deliberately not added — with no real workloads to schedule, it would add resource cost without adding architectural value.

## Author

Built by Firas Souid during an internship at SMT, as a self-directed exploration of virtualization, orchestration, and observability .