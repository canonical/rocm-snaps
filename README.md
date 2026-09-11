# rocm-snaps

Reusable snap packaging for the latest components of [the ROCm stack](https://github.com/ROCm/TheRock).

## rocm-inference

As the name implies, this snap packages rocm components needed for AI/ML inference.

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
export LD_LIBRARY_PATH="$ROCM_PATH/lib:$ROCM_PATH/lib/llvm/lib:$ROCM_PATH/lib/rocm_sysdeps/lib:${LD_LIBRARY_PATH:-}"
```
