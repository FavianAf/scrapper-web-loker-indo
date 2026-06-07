import os
import shutil
import subprocess
import time

SRC = os.path.join(os.environ["LOCALAPPDATA"], "Docker", "wsl")
DST = r"D:\DockerData\wsl"

print(f"SRC: {SRC}")
print(f"DST: {DST}")
print(f"SRC exists: {os.path.exists(SRC)}")

# Stop Docker
print("\n1. Stopping Docker Desktop...")
subprocess.run(
    [
        "powershell",
        "-NoProfile",
        "-Command",
        "Stop-Process -Name 'Docker Desktop' -Force -ErrorAction SilentlyContinue; "
        "Stop-Process -Name 'com.docker.backend' -Force -ErrorAction SilentlyContinue; "
        "Stop-Process -Name 'com.docker.proxy' -Force -ErrorAction SilentlyContinue",
    ],
    capture_output=True,
    text=True,
)
time.sleep(3)

# Shutdown WSL
print("2. Shutting down WSL...")
subprocess.run(["wsl", "--shutdown"], capture_output=True, text=True)
time.sleep(3)

# Check processes
result = subprocess.run(["tasklist", "/FO", "CSV"], capture_output=True, text=True)
docker_procs = [
    l for l in result.stdout.splitlines() if "docker" in l.lower() or "wsl" in l.lower()
]
print(f"3. Remaining Docker/WSL processes: {len(docker_procs)}")
for p in docker_procs:
    print(f"   {p}")

# Check if SRC is a junction already
if os.path.islink(SRC) or os.path.ismount(SRC):
    print(f"\n{SRC} is already a junction/symlink!")
    target = os.readlink(SRC) if os.path.islink(SRC) else "?"
    print(f"Target: {target}")
    exit(0)

# Check SRC size
total_size = 0
for dp, dn, fn in os.walk(SRC):
    for f in fn:
        fp = os.path.join(dp, f)
        try:
            total_size += os.path.getsize(fp)
        except OSError:
            pass
print(f"\n4. SRC size: {total_size / 1e9:.2f} GB")

# Move
print(f"\n5. Moving {SRC} -> {DST}...")
if os.path.exists(DST):
    print(f"   DST already exists, removing...")
    shutil.rmtree(DST, ignore_errors=True)

shutil.move(SRC, DST)
print(f"   Moved. DST exists: {os.path.exists(DST)}")

# Create junction
print(f"\n6. Creating junction: {SRC} -> {DST}")
subprocess.run(["cmd", "/c", "mklink", "/J", SRC, DST], capture_output=True, text=True)
print(f"   Junction created: {os.path.exists(SRC)}")

# Verify
print(f"\n7. Verification:")
print(f"   SRC is junction: {os.path.isdir(SRC)}")
print(f"   DST exists: {os.path.isdir(DST)}")
dst_files = os.listdir(DST)
print(f"   DST contents: {dst_files}")

print("\nDone! Docker data moved to D: drive.")
