#!/bin/sh

#since i cant use terraform on this project without vcenter, i created this script to clone the ubuntu server vm and create new vms for the k3s nodes. you can use this script to create as many nodes as you want, 

set -e

SRC_VM_DIR="/vmfs/volumes/datastore1/ubuntu server"
SRC_VMDK="${SRC_VM_DIR}/ubuntu server.vmdk"
SRC_VMX="${SRC_VM_DIR}/ubuntu server.vmx"

NODE_NAME="$1"
if [ -z "$NODE_NAME" ]; then
  echo "Usage: $0 <node-name>  e.g. $0 k3s-node-1"
  exit 1
fi

DEST_DIR="/vmfs/volumes/datastore1/${NODE_NAME}"
DEST_VMDK="${DEST_DIR}/${NODE_NAME}.vmdk"
DEST_VMX="${DEST_DIR}/${NODE_NAME}.vmx"

echo ">>> Creating destination folder: $DEST_DIR"
mkdir -p "$DEST_DIR"

echo ">>> Cloning disk..."
vmkfstools -i "$SRC_VMDK" "$DEST_VMDK" -d thin

echo ">>> Copying and adjusting .vmx..."
cp "$SRC_VMX" "$DEST_VMX"

sed -i "s/displayName = .*/displayName = \"${NODE_NAME}\"/" "$DEST_VMX"
sed -i "s|scsi0:0.fileName = .*|scsi0:0.fileName = \"${NODE_NAME}.vmdk\"|" "$DEST_VMX"
sed -i "/uuid.bios/d" "$DEST_VMX"
sed -i "/ethernet0.generatedAddress/d" "$DEST_VMX"
sed -i "/uuid.location/d" "$DEST_VMX"

echo ">>> Registering VM..."
VMID=$(vim-cmd solo/registervm "$DEST_VMX")

echo ">>> Done. New VM ID: $VMID (name: $NODE_NAME)"
