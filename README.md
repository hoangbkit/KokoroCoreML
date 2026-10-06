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
    url: "https://github.com/OWNER/KokoroCoreML.git",
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

For lightweight model integration, consume the separately versioned synthetic
fixture bundle with explicit `assetPolicy: .executableFixture`. Default SDK
loading remains production-only. Models are not added to the library resources.
See [executable fixture generation and consumption](docs/executable-fixtures.md)
for contracts, cache isolation, manual validation, and release artifacts.
