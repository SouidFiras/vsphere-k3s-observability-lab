variable "vsphere_host" {
  description = "ESXi host IP or hostname"
  type        = string
}

variable "vsphere_user" {
  description = "ESXi username"
  type        = string
  default     = "root"
}

variable "vsphere_password" {
  description = "ESXi password"
  type        = string
  sensitive   = true
}

variable "datastore_name" {
  default = "datastore1"
}

variable "network_name" {
  default = "VM Network"
}

variable "template_vm_name" {
  default = "ubuntu server"
}
