# Human to Agent rename design

## Goal

Rename the operational workspace from Harness Foundry to **Human to Agent** without leaving split branding in executable code, generated release artifacts, or normative pilot assets.

## Naming contract

| Surface | New value |
|---|---|
| Product and prose name | `Human to Agent` |
| Repository/project/distribution name | `human-to-agent` |
| Python import package | `human_to_agent` |
| CLI executable | `hta` |
| Reference-pilot slug | `human-to-agent-pilot` |
| Reference-pilot IDs | `workspace.human-to-agent-pilot`, `task-contract.human-to-agent`, and corresponding `human-to-agent` identifiers |

The rename is intentionally breaking. The project does not retain `hf`, `harness_foundry`, or `harness-foundry` aliases because an alias would keep two public identities and weaken source-to-release consistency.

## Scope

Rename all active source, tests, schemas, CLI usage, package metadata, Skills, Agents, templates, examples, documentation, traceability records, state, pilot source, and committed release output. Regenerate canonical artifact indexes and deterministic release manifests after the normative pilot rename.

The supplied `PR/` source files and the historical `docs/superpowers/*harness-foundry*` design/plan documents remain byte-for-byte historical evidence. References that explicitly identify that original source may retain the old wording only in a clearly marked source-locator context. Git history and old commit messages are outside repository content scope.

## Migration sequence

1. Add tests that assert the new package/CLI/name surfaces and explicitly allow old names only in historical-source locations.
2. Rename the Python package directory and imports, project metadata, executable, test imports, CLI messages, and wheel smoke test.
3. Rename the pilot directory, identifiers, event scope, artifact paths, examples, release path, generated golden checksum, and all active prose.
4. Rebuild artifact index through `hta record-change`, rebuild the deterministic release, and regenerate the golden checksum.
5. Update CI, documentation, traceability, Skills, Agents, adapters, templates, and state references.
6. Verify the new CLI, validation, event chain, deterministic build, wheel install, full test suite, and clean worktree.

## Compatibility and safety

The migration changes only repository-local files. It does not rename `E:\Harness Foundry` itself because that would move the workspace the user opened and was not requested. The workspace's internal identity changes to `human-to-agent`.

Historical source material is exempt from the no-old-name scan; all active files must use the new identity. A dedicated test enforces that exemption boundary.
