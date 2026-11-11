# Reusable recovery lessons

## Evidence levels

Metadata exposes identities and layout; native instructions support behavior; readable code is reconstruction; inferred names and intent remain interpretation. No export, successful parse, compilation or mocked test automatically proves native equivalence. Exact original source, comments, local names and optimized-away code are generally unavailable.

## Choose the route from the binary

Inspect container, splits, runtime version, architecture and feature flags before choosing tools. Unity IL2CPP, managed assemblies, Flutter AOT, native engines and web payloads need different routes. A tool's ARM64 support says nothing about ARM32. Recheck compatible alternatives before declaring a different build necessary; record the exact tool revision tested.

## Package lessons

- A single APK is often incomplete. Ask for the XAPK/APKS with the `config.arm64_v8a` split and the asset packs or OBB; Unity data and native code frequently live in splits.
- Some games ship only an ARM32 or only an ARM64 native split. Note which one you have before choosing tools.
- Check the package name and version against the store listing first. A mirror's search once returned a 2021 build under another publisher's package name, with a dead mediator, for a game whose live build was five years newer.
- Treat packages as hostile archives: refuse entries that would land outside the target folder, cap the bytes actually written (a few GB), and stop on a time budget.
- Splits can hold different files under the same path. In a Unity split-binary build the APK's `assets/bin/Data/data.unity3d` (18 MB: boot scene and global managers) and the OBB's (575 MB: every other scene and `resources.assets`) share a name. A "first file wins" merge dropped the OBB copy and the export read 7,851 objects instead of 370,664, with no error. Keep differing copies side by side and load them all; count the objects per bundle before trusting an export.
- Watch memory on Unity exports. UnityPy caches a decoded atlas on each file that asks for it, so a game split into hundreds of small files that share atlases can hold one 2048x2048 copy per file, over 10 GB. Clear the cache when the export moves to the next file. On macOS check "peak memory footprint" in `/usr/bin/time -l`: compressed memory hides this from the resident size.

## Asset lessons

- Unity: load `assets/bin/Data`, `assets/aa/**` and every AssetBundle in one UnityPy environment; otherwise reading textures, audio and meshes fails with "Resource file … not found" because their `.resS` and `.resource` streams do not resolve.
- Unity values (ScriptableObjects, MonoBehaviours) read directly only when type trees exist: AssetBundles keep them, player builds usually strip them. Generating them from the IL2CPP binary failed on Unity 6000.x, but Cpp2IL dummy assemblies work: pass them with `--dll-folder`. Build them with `--use-processor attributeanalyzer,attributeinjector`, or the trees stop at the base class because `[SerializeField]` is missing and reads end with "Expected to read N bytes, but only read 32".
- Unity meshes: export by usage (MeshFilter/SkinnedMeshRenderer references), skip collider hulls and duplicates, and convert handedness (UnityPy's OBJ export already mirrors X and flips winding). Rigs, animation clips, materials and scenes need AssetRipper.
- TextMeshPro fonts are usually SDF atlases without a TTF.
- Flutter draws its UI in code: there are no UI images to extract, so study layout and colors from screenshots and video.
- Contact sheets (thumbnail grids) are the fastest way to understand a game's art set before opening single files.

## Unity IL2CPP lessons

The pinned Cpp2IL base is b5ad444b82267cb1e4b88b8b373c008105bdea52; generic changes are in toolkit/cpp2il-recovery-v2.patch.

- Preserve parameter slots and separate general/FP argument registers; handle homogeneous aggregates explicitly.
- Resolve metadata indirection, field-address aliases, FP constants and proven barrier/exception helpers.
- Preserve Boolean types and IEEE754 flags, including unordered NaN comparisons and signed zero.
- Restore attributes from metadata rather than inventing annotations.
- Async/byref state machines, aggregate returns, exception regions, interface/generic dispatch and unknown instructions remain incomplete. Default structs after lost native returns are not recovered animation/gameplay behavior.

## Flutter/Dart AOT lessons

- AOT native code is not Dart bytecode. Names and library URIs can survive, but strings alone do not recover bodies.
- Match snapshot hash, runtime epoch, pointer compression, word size and architecture. Validate cluster bounds, reference ranges, instruction tables and field layouts; preserve skipped checks.
- Distinguish source-URI string offsets, instruction-image offsets, ELF file offsets and virtual addresses. Save the base mapping and actual native range for every reconstructed method.
- ARM32 code uses target-specific argument conventions, split 64-bit integers and tagged object pointers. Do not transplant ARM64 register names, pool offsets or dispatch-table origins.
- Decode pool doubles from their actual words and constant lists through object references. Do not guess thresholds, multipliers, enum identities or units.
- Resolve indirect calls using metadata and independent witnesses. Some tool presentation fields can retain architecture assumptions even when parsing succeeds; check the instruction displacement against the table yourself.
- Raw control-flow output can mix instructions with pseudo-Dart. Keep it as evidence; do not label it executable source. Small manual translations can be useful while dependencies remain explicitly unresolved.

## Behavior and validation lessons

Preserve check order, callback order, state invalidation, save scheduling, accepted/rejected inputs and numeric edge cases. A zero quoted price does not prove a free purchase if a separate ownership guard rejects it. Similar names do not establish identical behavior. Cached income can hide modifiers outside the current method. Missing checks in one method may exist in its callers or UI.

Use compiler checks for syntax/contracts, mocks for explicit modeled cases, and native primitive tests for the exact instruction semantics they exercise. None establish whole-game equivalence. Preserve the output and scope of actual checks; do not carry a case's test count into a new recovery as proof.

## Monetization lessons

- Publisher SDKs can bundle a full copy of their remote config in `assets/`: ad groups, placements, floor ladders, offers, segment rules. Read it first. It shows defaults, and the server can override them.
- Names and adapters show capability, not use. A flag can be off and a class unused.
- An SDK tracker's added and removed dates show what a publisher tried and dropped, which one build cannot.
- Cpp2IL on ARM32 needs native Capstone and disassembles every method while building its model: it had not finished after 40 minutes on an 82 MB library. Get the arm64 split, or fall back to metadata-only type lists and raw strings.
- A non-ASCII field name or `[SerializeReference]` data can break the standard value export of one object, often the config you came for. Confirm the money configs really exported. If one did not, decode its bytes by hand against the class layout and check that every byte is consumed.
- Check which game a team's measured result came from before quoting it next to another game.

## Live run lessons

- Read the app's data folder before the traffic. A publisher SDK can keep its live config as plain JSON on the device, even when the wire is compressed or encrypted. Diffing it against the bundled copy showed per-device floors, segments and experiment ids that no build holds.
- A server can key a player by device id or advertising id, so clearing app data does not make a new player. Wipe the emulator for that.
- Test mode changes what you see: MAX serves test creatives on emulators, and a floor logic that follows observed prices then climbs on fake fills. Label such numbers as test-mode.
- A game played by blind random swipes stays in its tutorial. Read the screen, act, then read it again.
- SDKs batch events. Killing the app seconds after an impression loses it, and the server never learns of it.

## Reading lessons

- Read data before code: level files, ScriptableObjects, localization tables and constant pools give exact numbers faster than method bodies.
- When code is unreadable, measure from store screenshots and gameplay video frame by frame, and label those numbers as observed.
- Prefer what players actually see when the build and the store disagree, and note the mismatch.

## Repository boundary

This repository holds tools, method docs, blank templates and synthetic examples only: no game's files, ever. Work in `~/Desktop/apk-work/<run-id>/` outside the repository and delete it afterwards. Learn the pattern and never clone the game. Tool repositories can inform generic fixes; original game repository source must never fill recovery gaps. Keep all upstream licenses.
