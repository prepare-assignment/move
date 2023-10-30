# Move action

This action moves files/directories. The action is modeled after the linux `mv` command. For more information see the [man page](https://linux.die.net/man/1/mv).

However unlike the `mv` command, it will not overwrite files/directories by default.

## Options

The following options are available:

```yaml
source:
  description: "File to move (glob)"
  required: true
destination:
  description: "Destination to move to"
  required: true
force:
  description: "Force the move (overwrite)"
  type: boolean
  default: true
```

- `source`: a glob that can match a file, multiple files or a directory
- `destination`: a glob that can be a file (rename) or directory
- `force`: overwrite if the destination file already exists, default to `true` to mimic the `mv` command

## Outputs

The following outputs are available:

```yaml
paths:
  description: The new paths
  type: array
  items: string
```

- `files`: The new path(s) of moved files/directories

* > :warning: If a directory is moved, it will only list the new directory path, not all sub files/directories.