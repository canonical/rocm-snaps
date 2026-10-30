# rocm-snaps

Reusable snap packaging for the latest components of [the ROCm stack](https://github.com/ROCm/TheRock).

## rocm-inference

As the name implies, this snap packages rocm components needed for AI/ML inference.

Snapcraft stages packages from AMD's signed Ubuntu 26.04 stable APT repository
rather than compiling TheRock. The `common` and `dev` parts provide the ROCm
host runtime, libraries, compiler, device bitcode, and development headers;
the `gfx1151`, `gfx1100`, and `gfx950` parts provide their respective BLAS/RAND
device payloads and the solver/sparse packages required by AMD's BLAS DEBs.
The recipe selects ROCm 10.0 package names but follows their latest stable
Debian revision. It does not include TheRock's benchmark or sample binaries.
For a new ROCm series, update the snap version, content identifier, and
selected package names together.

Snapcraft moves the payloads from AMD's `/opt/rocm/core-10.0` prefix directly
into `$SNAP/opt/rocm`, so `bin`, `lib`, `include`, `share`, and `.kpack` are
real directories. Debian maintainer scripts are not run, and no host
`/opt/rocm` alternatives are installed.

It exposes its complete `/opt/rocm` tree through the read-only `runtime` content slot, with a `rocm-inference-{MAJOR}-{MINOR}-{UBUNTU_BASE}` content identifier as ABI and build-environment contract; incompatible ROCm or Ubuntu revisions will use a new identifier.

In order to use the snap as a build dependency:

```yaml
parts:
  consumer-application-part:
    build-snaps:
      - on amd64 to amd64:
          - rocm-inference/latest/beta
    build-environment:
      - ROCM_PATH: /snap/rocm-inference/current/opt/rocm
      - HIP_PATH: $ROCM_PATH
      - HIP_LIB_PATH: $ROCM_PATH/lib
      - HIPCXX: $ROCM_PATH/lib/llvm/bin/clang++
      - PATH: $ROCM_PATH/bin:$ROCM_PATH/lib/llvm/bin:$PATH
      - LD_LIBRARY_PATH: $ROCM_PATH/lib:$ROCM_PATH/lib/llvm/lib:$ROCM_PATH/lib/rocm_sysdeps/lib:$LD_LIBRARY_PATH
```

You also need to declare the matching content plug in the consumer snap:

```yaml
plugs:
  rocm:
    interface: content
    content: rocm-inference-10-0-2604
    target: $SNAP/opt/rocm

apps:
  application:
    command: bin/application
    plugs:
      - rocm
```

Then, connect them accordingly after both are installed:

```shell
sudo snap connect ${CONSUMER_SNAP}:rocm rocm-inference:runtime
```

The runtime can then find ROCm libraries beneath `$SNAP/opt/rocm`.
A wrapper could be used to add these directories to its library search path:

```shell
export ROCM_PATH="$SNAP/opt/rocm"
export HIP_PATH="$ROCM_PATH"
export HIP_LIB_PATH="$ROCM_PATH/lib"
export LD_LIBRARY_PATH="$ROCM_PATH/lib:$ROCM_PATH/lib/llvm/lib:$ROCM_PATH/lib/rocm_sysdeps/lib:${LD_LIBRARY_PATH:-}"
```
