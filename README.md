# KokoroCoreML

Swift Package for running Kokoro text-to-speech with Core ML.

The package exposes two library products:

- `KokoroTTS`: the high-level text-to-speech API intended for applications.
- `KokoroPipeline`: the lower-level Core ML and audio synthesis pipeline.

## Requirements

- iOS 18 or later
- macOS 15 or later
- Swift 5.9 or later

## Swift Package Manager

Add this repository as a package dependency, then link the `KokoroTTS`
product to the application target:

```swift
.package(
    url: "https://github.com/hoangbkit/KokoroCoreML.git",
    revision: "PINNED_COMMIT"
)
```

Import the high-level API with:

```swift
import KokoroTTS
```

Model packages and voice files are application resources. They are not bundled
with this Swift package. The consuming application supplies them through
`KokoroResourceProvider`.

The small vocabulary and harmonic-source runtime files required by the SDK are
included in the `KokoroTTS` target resources.

## Executable integration fixtures

Use the fixture bundle in another app, such as ReadAloud, to exercise the real
Core ML pipeline without downloading production weights. It produces a synthetic
440 Hz tone, not speech. The fixture models are distributed separately from the
Swift package, so the consuming app does not need Python or the generator.

### 1. Pin the matching package version

Choose a [release](https://github.com/hoangbkit/KokoroCoreML/releases) containing
`kokoro-fixture-VERSION.tar.gz`. Pin the package to that exact tag and link
`KokoroTTS` to your app target. For example, after `1.1.0` is published:

```swift
.package(
    url: "https://github.com/hoangbkit/KokoroCoreML.git",
    exact: "1.1.0"
)
```

In Xcode's package dependency dialog, select **Exact Version**. This feature is
currently in the implementation PR; the `1.1.0` example does not imply that a
fixture release has already been published.

### 2. Download, verify, and extract the fixtures

Download the archive and its `.sha256` from the same release. On macOS:

```sh
VERSION=1.1.0 # Replace with the published package/fixture version.
ARCHIVE="kokoro-fixture-${VERSION}.tar.gz"
RELEASE="https://github.com/hoangbkit/KokoroCoreML/releases/download/${VERSION}"
curl -fL "${RELEASE}/${ARCHIVE}" -o "${ARCHIVE}"
curl -fL "${RELEASE}/${ARCHIVE}.sha256" -o "${ARCHIVE}.sha256"
shasum -a 256 -c "${ARCHIVE}.sha256" && tar -xzf "${ARCHIVE}"
```

The extracted `kokoro/` directory contains the runtime manifest, four
`.mlpackage` models, synthetic voices, vocabulary, and harmonic-source weights.
Workflow-produced archives also contain `FixtureValidation.json` and
`ProductionContractInspection.json`, recording the tested commit, macOS run,
and pinned production specification hashes.

### 3. Include the directory in your fixture app build

Copy the entire `kokoro/` directory into your app's resources, preserving its
name and internal paths. In Xcode, use a folder reference or a copy-resources
step that preserves the directory. Confirm the built app contains
`kokoro/KokoroRuntimeManifest.json` and the original model packages underneath it.

Stage the packages as plain files; avoid Xcode's automatic Core ML compilation
for these fixtures. The SDK verifies the source packages and compiles them into
its own writable cache when needed. Keep this resource copy in a dedicated
fixture build configuration rather than the app's production configuration.

### 4. Load and synthesize through the app API

Call this from your app's asynchronous loading flow:

```swift
import KokoroTTS

let tts = try await KokoroTTS.load(
    resources: .appBundle(.main, subdirectory: "kokoro"),
    computePolicy: .cpuOnly,
    assetPolicy: .executableFixture
)
try await tts.prewarm(text: "Hello world.")
let audio = try await tts.synthesize("Hello world.", voice: .afHeart)
let buffer = try audio.makePCMBuffer()
// Schedule buffer on your app's AVAudioPlayerNode for playback.
```

Keep the `tts` actor in your app's existing model/session owner and reuse it for
subsequent requests. `load` validates the bundle; `prewarm` compiles models and
runs the complete prediction pipeline. Audio is mono Float32 PCM at 24 kHz.
CPU-only is useful for repeatable integration runs. For fixtures stored outside
the app bundle, replace the resource provider with `.directory(fixtureRoot)`,
where `fixtureRoot` is the URL of the extracted `kokoro/` directory.

Production builds use a production bundle and the default `.productionOnly`
policy. Fixture admission is explicit and retains hash/contract checks; default
loading rejects synthetic assets. To catch accidental staging in a production
build, run this before Xcode model compilation:

```sh
python scripts/fixtures/require_production_assets.py /path/to/staged/production/kokoro
```

### Publishing the download

The manual **Generate, test, and release fixtures** workflow generates fresh
assets, compares pinned production contracts, runs macOS Core ML integration
tests, and packages the downloads. Enable its publication input to create a new
tag and release after all checks pass. A macOS validation report does not cover
ReadAloud's iPhone playback or device runtime; validate those in the consuming app.

See [executable fixture generation and consumption](docs/executable-fixtures.md)
for workflow inputs, contracts, cache isolation, and validation commands.
