# Docker Disk ~385 GB follow-up (not done in pod cleanup)

## Why Disk ≠ RAM

- Docker Desktop **RAM** (~15 GB) = processes in the WSL/Kind VM (Running pods).
- Docker Desktop **Disk** (~385 GB / ~1007 GB limit) = `docker_data.vhdx` contents (images, layers, Kind node FS). Scaling pods to 0 does **not** reclaim Disk.

## Current blocker

`docker system df` / `docker images` fail with:

`invalid character '\x00' looking for beginning of value` on image descriptor digests.

The image graph is corrupted or partially zeroed; until that is repaired, we cannot safely list or selectively remove unused images.

## Safe next steps (separate approval)

1. Dig origin moved off this laptop (2026-11-08): env=dev Kind **`am-dev-apps`** now runs on Bluehost VPS `am-vps-dev` (`129.121.169.241`). Laptop F: / Docker Disk is **no longer dig SoT**.
2. Do **not** run `docker system prune -af` until laptop dig Kind/tunnel are confirmed stopped and Contabo dig URLs stay green on the VPS.
3. After backup / spare capacity: repair Docker Desktop image store (or Docker support “Clean / Troubleshoot”), then `docker system df -v` to see reclaimable layers.
4. Only then remove **unused** images (old Kind node / dig layers no longer needed on laptop).
5. Optional: `wsl --shutdown` + `Optimize-VHD` on `F:\DockerDesktop\disk\docker_data.vhdx` after real image deletion.

## Pod cleanup already done (2026-11-08)

- Deleted local NS `am-apps-preprod`, `am-agents-preprod` (were replicas=0).
- Deleted Succeeded debug pods in dig NS.
- Scaled non-core dig Deployments to 0; kept identity, qa-agents, market-data, api-gateway, gateway, infra (cloudflared, kubeapi-proxy, traefik) — then cut over dig to VPS.

## F: still full after pod cleanup (expected)

- F: free ≈ **2.8 GB**; `F:\DockerDesktop\disk\docker_data.vhdx` still ≈ **418 GB**.
- Pod scale-down frees **RAM**, not host disk. Compact VHDX without deleting image layers does not shrink allocated size (Optimize-VHD missing; diskpart compact no-op without admin / without reclaimable sparse blocks).
- After dig VPS cutover, laptop Kind dig can be stopped (Phase 7) so F: reclaim work is safe separately from dig availability.
