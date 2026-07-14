#!/usr/bin/env python3
import requests
import os

PROMETHEUS_URL = os.environ.get("PROMETHEUS_URL", "http://localhost:9090")

# Static reference table — us-east-1, Linux On-Demand, verified June 2026
# Source: AWS EC2 on-demand pricing page (manually sourced, documented here for transparency)
INSTANCE_TYPES = [
    {"name": "t3.xlarge",  "vcpu": 4, "ram_mb": 16384, "monthly_usd": 121.47},
    {"name": "t4g.nano",   "vcpu": 2, "ram_mb": 512,   "monthly_usd": 3.07},
    {"name": "t3.micro",   "vcpu": 2, "ram_mb": 1024,  "monthly_usd": 7.59},
    {"name": "t3.small",   "vcpu": 2, "ram_mb": 2048,  "monthly_usd": 15.18},
    {"name": "t3.medium",  "vcpu": 2, "ram_mb": 4096,  "monthly_usd": 30.37},
    {"name": "t3.large",   "vcpu": 2, "ram_mb": 8192,  "monthly_usd": 60.74},
    {"name": "m5.large",   "vcpu": 2, "ram_mb": 8192,  "monthly_usd": 70.08},
    {"name": "m5.xlarge",  "vcpu": 4, "ram_mb": 16384, "monthly_usd": 140.16},
    {"name": "m5.2xlarge", "vcpu": 8, "ram_mb": 32768, "monthly_usd": 280.32},
]


def query_prometheus(metric):
    r = requests.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": metric}, timeout=10)
    r.raise_for_status()
    return r.json()["data"]["result"]


def get_vm_specs():
    cpu_data = query_prometheus("vsphere_vm_num_cpu")
    mem_data = query_prometheus("vsphere_vm_memory_size_mb")

    vms = {}
    for entry in cpu_data:
        name = entry["metric"]["vm_name"]
        vms[name] = {"vcpu": int(float(entry["value"][1]))}
    for entry in mem_data:
        name = entry["metric"]["vm_name"]
        vms.setdefault(name, {})["ram_mb"] = int(float(entry["value"][1]))
    return vms


def match_instance(vcpu, ram_mb):
    candidates = [i for i in INSTANCE_TYPES if i["vcpu"] >= vcpu and i["ram_mb"] >= ram_mb]
    if not candidates:
        return None
    return min(candidates, key=lambda i: i["monthly_usd"])


def main():
    vms = get_vm_specs()
    if not vms:
        print("No VM data returned from Prometheus. Check PROMETHEUS_URL and that vsphere-exporter is scraped.")
        return

    total = 0.0
    print(f"{'VM':<15} {'vCPU':<6} {'RAM(MB)':<10} {'Best EC2 Match':<16} {'Monthly $':<10}")
    print("-" * 60)
    for name, specs in sorted(vms.items()):
        vcpu = specs.get("vcpu")
        ram_mb = specs.get("ram_mb")
        if vcpu is None or ram_mb is None:
            continue
        match = match_instance(vcpu, ram_mb)
        if match:
            print(f"{name:<15} {vcpu:<6} {ram_mb:<10} {match['name']:<16} ${match['monthly_usd']:<10.2f}")
            total += match["monthly_usd"]
        else:
            print(f"{name:<15} {vcpu:<6} {ram_mb:<10} {'no match found':<16} {'-':<10}")

    print("-" * 60)
    print(f"Estimated total monthly cost (EC2 equivalent, On-Demand): ${total:.2f}")
    print("\nNote: pricing is a static us-east-1 Linux On-Demand snapshot (June 2026).")
    print("A production version would query the AWS Price List API directly for live rates.")


if __name__ == "__main__":
    main()
