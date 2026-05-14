# Seccomp for BHS

Production deployments should pass an explicit seccomp profile to Docker/Podman:

- Default Docker seccomp is a reasonable baseline; export it with:
  `docker run --rm debian:bookworm-slim cat /proc/self/attr/seccomp` is not the JSON profile.
- Generate a reference JSON (Linux) via `containerd`/`runc` docs, or start from
  [Moby `default.json`](https://github.com/moby/moby/blob/master/profiles/seccomp/default.json).

This repository does **not** vendor the full default profile (large). Set:

```bash
export BHS_SECCOMP_PROFILE=/path/to/seccomp.json
```

The `SandboxRunner` appends `--security-opt seccomp=...` only when the file exists.
