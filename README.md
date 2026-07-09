# vSphere + k3s Observability Lab

A self-hosted virtualization, orchestration, and observability lab — built to explore how a VMware vSphere environment, a lightweight Kubernetes cluster, and a full monitoring stack fit together.

![Grafana Dashboard](docs/screenshots/grafana-node-exporter.png)

## Context

This project started during an internship at **Société Monétique Tunisie (SMT)**, Tunisia's national interbank switching company. The internship came without an assigned project or access to production systems which is a reasonable constraint given SMT's environment runs live banking infrastructure (a VMware vSphere/ESXi stack of roughly 600 VMs, monitored via SolarWinds).

Rather than wait for direction, I built a self-contained lab mirroring the same architectural pattern  hypervisor, orchestration, monitoring on my own hardware, with the goal of understanding the full stack hands-on rather than observing it from the outside. Everything here was designed, broken, debugged, and rebuilt independently.

## Architecture

![Architecture Diagram](docs/architecture.png)

**Stack summary:**
- **Host:** Windows 11 → VMware Workstation Pro → nested ESXi 7.0.3 (evaluation license, standalone — no vCenter)
- **4 VMs on ESXi:**
  - `ubuntu` the  k3s control-plane
  - `k3s-node-1`, `k3s-node-2` these are the  k3s workers
  - `monitoring` — Prometheus, Grafana (via Docker Compose), Ansible control node, custom vSphere exporter
- **Orchestration:** k3s (lightweight Kubernetes) chosen for its small footprint given hardware constraints
- **Observability:** three independent layers feeding one Prometheus instance:
  - `node-exporter` — system-level metrics (CPU/RAM/disk/network) per VM
  - `kube-state-metrics` — Kubernetes object-level metrics (pod status, deployments, node conditions)
  - custom `vsphere-exporter` (this repo)  vSphere-layer metrics (per-VM CPU/memory, datastore capacity, host stats) via `pyvmomi`
- **Automation:** Ansible (configuration management across all 3 k3s nodes), Terraform (intended provisioning layer you can check limitation below)

## Key engineering decisions

**Why k3s instead of full Kubernetes.** Given the hardware budget (24GB RAM on my personal machine shared across nested ESXi, guest VMs, and the Windows 11 host), k3s's lightweight footprint made a multi-node cluster feasible at all. Despite that , it still mirrors how k3s is used in production .

**Why Terraform is present but not the active provisioning tool.** Terraform's `vsphere_virtual_machine` resource supports cloning VMs via a `clone` block but this feature requires **vCenter Server**; it is not available against standalone ESXi, even under an evaluation license. This was discovered directly (`Error: use of the clone sub-resource block requires vCenter`) rather than assumed. The Terraform configuration is kept in [`terraform/`](terraform/) as the intended design for a vCenter-managed environment  it would work unmodified if pointed at real vCenter. In this lab, node provisioning is instead handled by [`scripts/clone_node.sh`](scripts/clone_node.sh), a POSIX shell script run directly on the ESXi host via `vmkfstools` (disk clone) and `vim-cmd solo/registervm` (VM registration) the CLI-level equivalent of what Terraform would otherwise automate.

**Why monitoring runs externally, not in-cluster.** Prometheus and Grafana run on a dedicated VM outside the k3s cluster, via Docker Compose, rather than deployed inside the cluster (e.g. via the kube-prometheus-stack Helm chart). This keeps monitoring independent of the health of the thing it's observing — if the cluster has issues, the monitoring stack watching it isn't also at risk git statusand was lighter on resources for this lab's constraints.

**Why a custom exporter instead of relying only on community tooling.** `node-exporter` and `kube-state-metrics` cover the system and Kubernetes layers, but neither exposes vSphere-level state (VM power state, datastore capacity, host resource usage as seen by the hypervisor). [`vsphere-exporter/vsphere_exporter.py`](vsphere-exporter/vsphere_exporter.py) closes that gap: it connects directly to the ESXi host's vSphere API via `pyvmomi` (the same API vCenter itself is built on) and exposes the results in Prometheus format, completing a genuine three-layer observability picture: **vSphere → Kubernetes → System**.

## Repository structure

```
├── terraform/              # Intended IaC design (vCenter-targeted; see limitation above)
├── ansible/                 # Playbooks
│   ├── inventory.ini.example
│   ├── ansible.cfg
│   ├── node_exporter.yml
│   ├── ufw_setup.yml
│   └── ...
├── vsphere-exporter/        # this is used to export vsphere metrics to prometheus
│   ├── vsphere_exporter.py
│   └── vsphere-exporter.service
├── scripts/
│   └── clone_node.sh        # i used this to clone the ubuntu vm as a vsphere workaround 
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
- `node_exporter.yml`  installs and configures node-exporter as a systemd service across all nodes, idempotently
- `ufw_setup.yml` configures UFW firewall rules (SSH, k3s API, kubelet, Flannel overlay, node-exporter, NodePort range) 

Passwordless SSH (key-based auth) and passwordless sudo (`NOPASSWD`) on the target nodes allow these playbooks to run unattended, the same pattern used by real automation/CI systems.

## Setup (approximate reproduction steps)

This lab isn't a one-command deploy . reproducing it means: nested ESXi on VMware Workstation , a base Ubuntu Server VM converted into a clone source for k3s nodes (and it serves as the control node too), 2 additional nodes cloned via `scripts/clone_node.sh`, k3s installed on all 3 nodes (maybe installed with the help of ansible in the future to remove the need for manual instalation ), a separate monitoring VM running Docker Compose with the stack in `monitoring/`, and the exporter in `vsphere-exporter/` deployed as a systemd service with `ESXI_HOST`/`ESXI_USER`/`ESXI_PASSWORD` environment variables set.

## Limitations 

- **vCenter Server** is not deployed (hardware constraints) since Terraform's clone workflow and vSphere CPI/CSI integration for Kubernetes both require it, and remain designed-for-but-not-implemented here.
- A 3rd k3s worker node was deliberately not added sincei didnt any real workloads to schedule, it would add resource cost without adding architectural value.

## Author

Built by Firas during an internship at SMT, as a self-directed exploration of virtualization, orchestration and observability .