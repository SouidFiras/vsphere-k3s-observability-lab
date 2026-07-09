#!/usr/bin/env python3
import ssl
import time
import os
from pyVim.connect import SmartConnect, Disconnect
from pyVmomi import vim
from prometheus_client import start_http_server, Gauge

# --- Config (env vars, so credentials aren't hardcoded in the script) ---
ESXI_HOST = os.environ.get("ESXI_HOST")
ESXI_USER = os.environ.get("ESXI_USER", "root")
ESXI_PASSWORD = os.environ.get("ESXI_PASSWORD")
SCRAPE_INTERVAL = int(os.environ.get("SCRAPE_INTERVAL", "30"))
EXPORTER_PORT = int(os.environ.get("EXPORTER_PORT", "9272"))

# --- Prometheus metrics ---
vm_cpu_usage = Gauge('vsphere_vm_cpu_usage_mhz', 'VM CPU usage in MHz', ['vm_name'])
vm_memory_usage = Gauge('vsphere_vm_memory_usage_mb', 'VM memory usage in MB', ['vm_name'])
vm_power_state = Gauge('vsphere_vm_power_state', 'VM power state (1=on, 0=off)', ['vm_name'])
datastore_free_bytes = Gauge('vsphere_datastore_free_bytes', 'Datastore free space in bytes', ['datastore_name'])
datastore_capacity_bytes = Gauge('vsphere_datastore_capacity_bytes', 'Datastore total capacity in bytes', ['datastore_name'])
host_cpu_usage = Gauge('vsphere_host_cpu_usage_mhz', 'Host CPU usage in MHz', ['host_name'])
host_memory_usage = Gauge('vsphere_host_memory_usage_mb', 'Host memory usage in MB', ['host_name'])


def connect():
    context = ssl._create_unverified_context()
    return SmartConnect(host=ESXI_HOST, user=ESXI_USER, pwd=ESXI_PASSWORD, sslContext=context)


def collect_metrics(si):
    content = si.RetrieveContent()

    # --- VMs ---
    container = content.viewManager.CreateContainerView(content.rootFolder, [vim.VirtualMachine], True)
    for vm in container.view:
        name = vm.name
        power_state = 1 if vm.runtime.powerState == 'poweredOn' else 0
        vm_power_state.labels(vm_name=name).set(power_state)

        if vm.runtime.powerState == 'poweredOn' and vm.summary.quickStats:
            vm_cpu_usage.labels(vm_name=name).set(vm.summary.quickStats.overallCpuUsage or 0)
            vm_memory_usage.labels(vm_name=name).set(vm.summary.quickStats.guestMemoryUsage or 0)
    container.Destroy()

    # --- Datastores ---
    ds_container = content.viewManager.CreateContainerView(content.rootFolder, [vim.Datastore], True)
    for ds in ds_container.view:
        datastore_free_bytes.labels(datastore_name=ds.name).set(ds.summary.freeSpace)
        datastore_capacity_bytes.labels(datastore_name=ds.name).set(ds.summary.capacity)
    ds_container.Destroy()

    # --- Hosts ---
    host_container = content.viewManager.CreateContainerView(content.rootFolder, [vim.HostSystem], True)
    for host in host_container.view:
        if host.summary.quickStats:
            host_cpu_usage.labels(host_name=host.name).set(host.summary.quickStats.overallCpuUsage or 0)
            host_memory_usage.labels(host_name=host.name).set(host.summary.quickStats.overallMemoryUsage or 0)
    host_container.Destroy()


def main():
    if not ESXI_HOST or not ESXI_PASSWORD:
        raise SystemExit("ESXI_HOST and ESXI_PASSWORD environment variables must be set")

    start_http_server(EXPORTER_PORT)
    print(f"vSphere exporter running on port {EXPORTER_PORT}")

    while True:
        try:
            si = connect()
            collect_metrics(si)
            Disconnect(si)
        except Exception as e:
            print(f"Error collecting metrics: {e}")
        time.sleep(SCRAPE_INTERVAL)


if __name__ == "__main__":
    main()
