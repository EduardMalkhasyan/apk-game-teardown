# Method: open a game package and read how it plays

This repository is the toolbox and the method, like Photoshop without photos. It never holds a game. The package you study, everything you extract from it and your notes about it live in a work folder outside the repository, `~/Desktop/apk-work/<run-id>/`, and you delete that folder when you are done. The steps are written for Android packages.

## 0. Rules

- **Learn, never clone.** Take the pattern (core loop, pacing, feedback, economy shape, difficulty curve), then build your own game with your own code, art, sound, names and numbers. Never ship, publish or paste recovered code, assets or level data.
- **No game files in this repository**: no packages, recovered code, exported assets or per-game notes.
- **Read recovered code, never run it.** Treat every package as untrusted input.
- Respect each game's terms and your local law. Study for learning only.

## 1. Get the complete package and unzip it

- Prefer a bundle (XAPK, APKS or APKM) over a single APK. A lone base APK often lacks the native-code split (`config.arm64_v8a`), the Unity data (asset packs, `assets/aa`) or the OBB.
- Most native tools work best on `arm64-v8a`. If only `armeabi-v7a` is present, expect fewer recovered method bodies.

```sh
shasum -a 256 package.xapk
unzip -l package.xapk | tail -1             # total unpacked size: stop if it is far bigger than expected
python3 toolkit/unpack_package.py package.xapk ~/Desktop/apk-work/<run-id>
```

The unpacker writes `splits/` (the bundle's APKs and OBB) and `unzipped/` (all of them merged, base APK first). It works for a single APK too. Read its `warnings` and `renamed` list: in Unity split builds the APK and the OBB both hold `assets/bin/Data/data.unity3d` with different scenes, so the OBB copy is kept as `data.main.unity3d` next to the APK one. Do not merge splits by hand with `unzip -n`: it keeps the first copy and silently drops the OBB's game data. Check that `unzipped/assets/` exists before step 3.

## 2. Find the engine

```sh
python3 toolkit/inspect_package.py ~/Desktop/apk-work/<run-id>/package.xapk
find ~/Desktop/apk-work/<run-id>/unzipped -maxdepth 3 | sort | less
```

The inventory flags Unity, Flutter, Godot, Unreal and Cocos libraries plus Lua and web files. For the other engines, compare the file list with this table.

| You find | Engine | Gameplay code | Assets |
| --- | --- | --- | --- |
| `lib/*/libil2cpp.so` + `assets/bin/Data/Managed/Metadata/global-metadata.dat` | Unity IL2CPP | native `libil2cpp.so`, with names in the metadata | `assets/bin/Data`, `assets/aa/**`, AssetBundles, OBB |
| `assets/bin/Data/Managed/Assembly-CSharp.dll` | Unity Mono | `Assembly-CSharp.dll` (readable C#) | same as IL2CPP |
| `lib/*/libapp.so` + `libflutter.so` | Flutter | Dart AOT snapshot in `libapp.so` | `assets/flutter_assets/**` (the UI is drawn in code) |
| `libcocos2djs.so` / `libcocos.so`, `*.jsc` | Cocos (JS) | `.jsc` (xxtea-encrypted JS) or plain JS | `assets/**`: png, json, plist/atlas, Spine |
| `libcocos2dlua.so`, `*.luac` | Cocos2d-x Lua | Lua, usually xxtea-encrypted | `assets/**` |
| `libgodot_android.so`, `assets/project.binary` (a `.pck` only in an expansion OBB) | Godot | GDScript under `assets/` (`.gd` text or compiled `.gdc`) | `assets/**`: scenes, imported textures, sounds |
| `libUE4.so` / `libUnreal.so`, `*.pak` (often in the OBB) | Unreal | native C++, plus Blueprints in `.uasset` | `.pak` |
| `assets/game.arcd` / `.arci` / `.dmanifest`, `libdmengine.so` | Defold | Lua inside the archive | the archive |
| `assets/game.droid`, `libyoyo.so` | GameMaker | GML bytecode (VM builds) or native (YYC builds) | `game.droid` |
| `assets/index.android.bundle` | React Native | JS, or Hermes bytecode | `assets/`, `res/` |
| `assets/www/**` or other HTML | WebView / HTML5 | JS | `assets/` |
| only `classes*.dex` | Java / Kotlin | dex | `res/`, `assets/` |

For gameplay, ignore ad, analytics and attribution SDKs, in native libraries and in code packages alike (Google Mobile Ads, AppLovin, Unity Ads, ironSource, Meta, AppsFlyer, Adjust, Firebase, Appodeal and so on). Ignore the engine's own code too. Several engines can share one package. To study how a game earns money instead, follow [MONETIZATION.md](MONETIZATION.md).

## 3. Extract the assets

### Unity

Install UnityPy once, in its own environment:

```sh
python3.12 -m venv ~/.venvs/unitypy
~/.venvs/unitypy/bin/pip install "UnityPy[full]==1.25.4"   # includes FSB audio and script-value support
```

Then export:

```sh
~/.venvs/unitypy/bin/python -I toolkit/export_unity_assets.py \
  ~/Desktop/apk-work/<run-id>/unzipped ~/Desktop/apk-work/<run-id>/assets
```

The exporter does the following:

- Loads every Unity file under `unzipped/assets/` together, so `.resS` and `resources.resource` streams resolve.
- Writes `Sprite/` and `Texture2D/` PNGs, `AudioClip/` files in their real format (wav, ogg or m4a), `Mesh/` OBJs, `Font/`, `TextAsset/` and `MonoBehaviour/` JSON values.
- Keeps going when one object fails and counts the failures.
- Refuses an output folder inside this repository.

What we learned:

- **Sprites.** Keep each sprite's pivot (`m_Pivot`), pixels per unit (`m_PixelsToUnits`) and 9-slice border (`m_Border`). A texture that backs two or more sprites is an atlas, and `SpriteAtlas` objects name the rest.
- **3D models.** A 3D game can hold 15,000 meshes, so the exporter keeps the 300 that `MeshFilter` and `SkinnedMeshRenderer` components use most (`--max-meshes`). UnityPy's OBJ export already mirrors X and reverses the triangle winding (Unity is left-handed). For rigged characters, animation clips, materials, prefabs and scenes, use AssetRipper. It exports a whole Unity project with glTF meshes, which you open in Unity or Blender.
- **Values** (ScriptableObjects and MonoBehaviours: levels, prices, tuning).
  - AssetBundles and Addressables carry type trees, so these values read directly.
  - Player builds usually strip them. The exporter then generates type trees from the Mono DLLs or from the IL2CPP binary plus metadata.
  - On Unity 6000.x IL2CPP builds, loading the binary directly fails. Generate dummy assemblies with Cpp2IL (`--use-processor attributeanalyzer,attributeinjector --output-as dummydll`) and pass them with `--dll-folder`: see [MONETIZATION.md](MONETIZATION.md) step 2. This read nearly every script value on 6000.0 and 6000.3 builds (November 2026).
- **Text.** If the game uses Unity Localization, its string tables (in the Addressables bundles) hold the player-facing text, which is a fast map of features. Other games keep text in I2 Localization assets or CSV/JSON text assets.
- **Fonts.** TextMeshPro fonts usually ship only as SDF atlases (no TTF), so identify the typeface by its name.
- **Audio.** FSB5 banks are decoded through fmod_toolkit, which is included. Wwise `.bnk`/`.wem` need vgmstream.
- **Contact sheets.** Paste thumbnails onto grids (Pillow) so you can scan hundreds of sprites, textures and meshes in a minute.
- **Speed.** Our filtering exporter took about 4 s on a ~100 MB Unity 6 IL2CPP XAPK and about 10 s on a ~200 MB 3D one. Cap time (`--budget`) and disk, since packages can be decompression bombs.

### Other engines

| Engine | How to get the assets |
| --- | --- |
| Flutter | `assets/flutter_assets/**` are plain files. The UI is drawn in code, so study it from store screenshots and a gameplay video. |
| Cocos | Plain png, json and plist atlases under `assets/`. Spine skeletons are `.skel`/`.json` plus `.atlas` and png. |
| Godot | Open the APK (or the `.pck`) in GDRE Tools (gdsdecomp). It recovers scenes, scripts, textures and sounds. |
| Unreal | FModel on the `.pak` files (needs the AES key if the paks are encrypted): textures, meshes, sounds. |
| GameMaker | UndertaleModTool on `game.droid`: sprites, sounds, rooms. |
| Defold | Unpack `assets/game.arcd` with a Defold archive unpacker. Keep `game.arci` (the index) and `game.dmanifest` (the file names) next to it. |
| Standalone textures | `.ktx`, `.astc`, `.pvr`: astcenc or PVRTexTool. UnityPy decodes ASTC and ETC2 inside Unity files on its own. |

## 4. Read the code

| Engine | Tool and command | What you get |
| --- | --- | --- |
| Unity Mono | From the repository folder (needs .NET 10): `dotnet toolkit/ILSpy/ilspycmd.dll -p -o ~/Desktop/apk-work/<run-id>/code ~/Desktop/apk-work/<run-id>/unzipped/assets/bin/Data/Managed/Assembly-CSharp.dll`, or `toolkit/recover_gameplay.py` | Readable C#, formulas verbatim |
| Unity IL2CPP | Names: Cpp2IL or Il2CppInspectorRedux on `libil2cpp.so` + `global-metadata.dat` give classes, fields, methods and RVAs. Il2CppDumper only supports Unity 5.3 to 2022.2. Bodies: `toolkit/recover_gameplay.py` (partial, read its `quality.json`) or Ghidra at those RVAs. | Full names, partial bodies |
| Flutter | Blutter (arm64) or Jadart Tier 2 (arm32) on `libapp.so`; see [ENGINE_ROUTES](ENGINE_ROUTES.md) | Names, pseudo-assembly; numbers sit in the object pool |
| Cocos JS | 1. Find the key: a short ASCII string in `libcocos*.so`. List candidates with `strings`, or in Ghidra read the string passed to `jsb_set_xxtea_key` / `xxtea_decrypt`. 2. Decrypt each `.jsc` with Cocos's own xxtea variant: pad the key with zero bytes to 16, decrypt the whole file without padding, then keep only the first N bytes, where N is the file's last 4 bytes read as a little-endian number. Libraries with default PKCS#7 padding fail. 3. Gunzip the result if it starts with `1F 8B`. | Plain JS with the whole gameplay |
| Cocos2d-x Lua | Strip the sign prefix from each `.luac`, then decrypt as for Cocos JS. The key and the sign are strings in `libcocos2dlua.so`. | Lua or Lua bytecode |
| React Native | Run `file` on `index.android.bundle`. If it says Hermes JavaScript bytecode, run `hbc-decompiler index.android.bundle ~/Desktop/apk-work/<run-id>/code/bundle.js` (hermes-dec); otherwise it is plain JS. | JS or pseudo-JS |
| Java / Kotlin | `jadx -d ~/Desktop/apk-work/<run-id>/code base.apk` | Java-like code |
| Godot | GDRE Tools; C# Godot games ship .NET DLLs, so use ILSpy | GDScript or C# |
| Lua (Defold, Solar2D, cocos-lua) | Plain `.lua`, or luajit/luac bytecode decompiled with a luajit decompiler or unluac | Lua |
| GameMaker VM | UndertaleModTool | GML |
| Unreal, YYC GameMaker, pure native | Ghidra; for Unreal also inspect Blueprints in FModel | Pseudo-C, no original names |

Check the tool's supported metadata, snapshot or engine version against the game before trusting the output. Newer engine versions often need the newest tool build.

## 5. Read the gameplay (the order that worked)

1. **Data before code.** Read ScriptableObjects, level files, JSON/CSV text assets, localization tables and Flutter object-pool constants first. The numbers there are exact and quick to read.
2. **Map the systems.** List the game's own class names, with how many scenes and prefabs use each one: player, spawner, level, economy, shop, upgrades, tutorial.
3. **Trace one mechanic end to end:** trigger → checks → state changes → output (spawn, damage, reward, save). Note timings, order, boundaries and units.
4. **Write findings as confirmed, inferred or unknown**, each with its source (asset path, class.method, address). Use [templates/MECHANIC.md](../templates/MECHANIC.md).
5. **When the code is unreadable**, study store screenshots and a gameplay video. Measure speeds and timings frame by frame, and mark those numbers as observed, not recovered.

The evidence rules for deep code work are in [WORKFLOW.md](WORKFLOW.md).

## 6. Turn it into your own game

- Write the pattern in your own words, in the "Original design lesson" part of the mechanic record.
- Change the theme, art, audio, names, numbers and level layouts, and improve at least one thing: onboarding, game feel, pacing or difficulty curve.
- Write fresh code from the pattern. Never paste recovered code or assets into your project.
- Delete `~/Desktop/apk-work/<run-id>/` when you are done.

See [examples/synthetic-mechanic.md](../examples/synthetic-mechanic.md) for a filled mechanic record based on a made-up game.
