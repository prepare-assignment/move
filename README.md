# Move

This action moves files/directories. The action is modeled after the linux `mv` command. For more information see the [man page](https://linux.die.net/man/1/mv).

Like `mv`, an existing destination is overwritten; set `force: false` to fail instead.

## Options

The following options are available:

```yaml
source:
  description: "Files/directories to move (glob)"
  required: true
destination:
  description: "Destination to move to"
  required: true
force:
  description: "Force the move (overwrite)"
  type: boolean
  default: true
allow-outside-working-directory:
  description: "Allow destination/matched files to be outside the working directory"
  type: boolean
  default: false
include-hidden:
  description: "Also match hidden files and directories (starting with a '.') with wildcards such as '*' and '**'"
  type: boolean
  default: false
```

- `source`: a glob that can match a file, multiple files or a directory
- `destination`: a glob that can be a file (rename) or directory
- `force`: overwrite if the destination file already exists, default to `true` to mimic the `mv` command

## How files and directories are moved

- A **file** is moved into the destination if it's an existing directory, otherwise to the destination itself (e.g. to rename it).
- If the glob matches **several paths**, the destination must be an existing directory.
- A **directory** is moved into the destination if it's an existing directory (`in` → `out/in`), or renamed to the destination if it doesn't exist.
- With `force` (the default) an existing destination is overwritten; with `force: false` the task fails instead. A file never replaces a directory and a directory never replaces a file, like `mv`.
- Everything is checked before anything is moved, so a failing task doesn't leave half of the files moved.
- **Symbolic links** are moved themselves; files inside a linked directory are not moved (they belong to the link's target).

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

## Releases

Releases are automated with [semantic-release](https://semantic-release.gitbook.io/). Pull requests are squash merged, so the PR title becomes the commit on `main` and must follow [Conventional Commits](https://www.conventionalcommits.org/) (checked on every PR):

| PR title | Release |
|----------|---------|
| `fix: ...`, `perf: ...` | patch (1.2.3 → 1.2.4) |
| `feat: ...` | minor (1.2.3 → 1.3.0) |
| `!` after the type (e.g. `feat!: ...`, `refactor!: ...`) or a `BREAKING CHANGE:` footer | major (1.2.3 → 2.0.0) |
| `docs:`, `chore:`, `ci:`, `build:`, `refactor:`, `test:`, `style:`, `revert:` | no release |

On every merge to `main` the next version is determined, tagged (`vX.Y.Z`) and a GitHub release is created. The major tag (e.g. `v1`) is moved to the new release, so `uses: move@v1` always gets the newest 1.x version.

Because the major tag moves, `git pull` in an existing clone can fail with `! [rejected] v1 -> v1 (would clobber existing tag)`. Update the tags once with `git fetch --tags --force` and pull again.
