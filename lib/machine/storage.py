import shutil
import os

from .utils import get, run_command, command_exists
from ..config import config


class Storage:

	@staticmethod
	def get_usage():
		filesystems = {}

		if config.get("machine", "custom_storage"):
			storage = config.get("machine", "storage")
			for item in storage:
				filesystems[item] = [storage[item], nice_path(storage[item])[1]]

		else:
			mounts = get("/proc/mounts").split("\n")
			listed_devices = []
			for mount in mounts:
				if mount.startswith("/dev/"):
					line = mount.split(" ")
					stuff = nice_path(line[1])
					if config.get("machine", "hide_boot_partition"):
						if line[1].startswith("/boot"):
							continue
					if config.get("machine", "enable_storage_blacklist"):
						if line[1] in config.get("machine", "storage_blacklist"):
							continue
					if line[0] not in listed_devices:
						filesystems[stuff[0]] = [line[1], stuff[1], line[2]]
					listed_devices.append(line[0])

		result = {}

		for fs in filesystems:
			try:
				usage = os.statvfs(filesystems[fs][0])

			except PermissionError:
				continue

			# ext4 fs dirty-improvement to show nicely rounded storage size
			inode_overhead = 0
			if filesystems[fs][2] == "ext4":
				inode_size = 256		# Default for mkfs.ext4
				correction = 1.2
				inode_overhead = inode_size * usage.f_files * correction

			result[fs] = {
				"icon": filesystems[fs][1],
				"total": usage.f_bsize * usage.f_blocks + inode_overhead,
				"available": usage.f_bsize * usage.f_bavail
			}

		# Add ZFS pools
		zfs_pools = get_zfs_pools()
		for pool_name, pool_data in zfs_pools.items():
			result[pool_name] = pool_data

		return result



def get_zfs_pools():
	"""Get ZFS pool information using zpool list command.
	
	Returns empty dict if ZFS is not installed or accessible.
	Never raises exceptions - fails gracefully.
	"""
	pools = {}
	
	try:
		# Check if zpool command exists before trying to use it
		if not command_exists("zpool"):
			return pools
		
		# Execute zpool list with -H (no headers) and -p (parseable/numeric values)
		output = run_command(["zpool", "list", "-H", "-p"])
		
		if not output:
			return pools
		
		for line in output.split("\n"):
			if not line.strip():
				continue
			
			parts = line.split()
			if len(parts) < 4:  # Need at least name, size, alloc, free
				continue
			
			try:
				name = parts[0]
				size = int(parts[1])  # Total size in bytes
				alloc = int(parts[2])  # Allocated space in bytes
				free = int(parts[3])   # Free space in bytes
				
				pools[name] = {
					"icon": "database",
					"total": size,
					"available": free
				}
			except (ValueError, IndexError):
				# Skip malformed lines
				continue
		
	except Exception:
		# Catch any unexpected errors and return empty dict
		# This ensures the app never crashes due to ZFS issues
		pass
	
	return pools


def nice_path(path):
	if path == "/":
		return ["OS", "settings"]

	elif path.startswith("/boot"):
		return ["Boot", "sprint"]

	return [path.split("/")[-1].title(), "folder"]
