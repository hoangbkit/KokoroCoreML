# Executable Kokoro fixtures

KokoroCoreML owns two fixture tiers. `KokoroBundleFixture` remains the lightweight,
non-executable filesystem helper. `testfixtures/kokoro` contains real synthetic
Core ML packages for the normal SDK pipeline. No models or voices from this
fixture directory are included in the production Swift library resources.

The executable profile is `fixture-executable-v1`: duration t128 and one 15-second
bucket. It has four models, three synthetic voices, the SDK phoneme vocabulary,
and synthetic harmonic-source projection weights. Synthesis produces a 440 Hz,
0.02-amplitude tone, trimmed and postprocessed by the normal runtime. These assets
exercise integration boundaries; they do not reproduce speech quality, model
performance, or production memory usage. Even with tiny weights, the normal
15-second intermediate tensor geometry and Swift harmonic DSP still execute.

## App consumption

Pin the KokoroCoreML package to the same release version as the fixture archive.
Retrieve `kokoro-fixture-VERSION.tar.gz` and its `.sha256` from that release,
verify the checksum, and extract it to obtain a `kokoro/` bundle root. The first
release containing this feature is expected to be 1.1.0; no release is created by
opening the implementation PR.

Stage the directory as plain resources (for example, an Xcode folder reference).
Avoid automatic Xcode compilation of these packages: fixture admission compiles
the verified source packages into its own writable cache. Keep generated
`.mlmodelc` assets out of the source archive. Consumers must not duplicate the
Python generator.

```swift
import KokoroTTS

let tts = try await KokoroTTS.load(
    resources: .directory(fixtureRoot),
    computePolicy: .cpuOnly,
    assetPolicy: .executableFixture
)
try await tts.prewarm(text: "Hello world.")
let audio = try await tts.synthesize("Hello world.", voice: .afHeart)
// audio.samples is final finite 24 kHz mono PCM after normal postprocessing.
```

CPU-only is useful for deterministic integration runs. An explicitly requested
Apple-device check should also cover the app's intended compute policy.
`load` validates resources lazily; actual compilation/prediction occurs in
`prewarm` or synthesis. Empty/inaudible text continues to follow SDK semantics.

For a manually requested command-line run on macOS:

```sh
swift run kokoro-sdk-smoke --fixture --cpu-only --bundle /absolute/path/kokoro --out fixture.wav
```

## Admission and production separation

`KokoroTTS.load` defaults to `.productionOnly`. Existing schema-v1 production
manifests remain compatible. Default loading rejects a fixture marker/profile
before model compilation. `.executableFixture` accepts only the supported
synthetic profile, exact four-package set, t128/15s geometry, and truthful
synthetic provenance. It does not admit production bundles as fixtures and does
not bypass file hashes, package hashes, schema, or path safety.

Fixture manifests have `hf_provenance_verified: false` and empty HF provenance
fields. Generator revision and artifact version live under `synthetic_fixture`.
Fixture mode ignores same-named compiled assets in `Bundle.main`, and even an
explicit compiled cache gets a source-digest-specific fixture subdirectory.
Loaded model descriptions are checked against the bundled contract descriptor
before the executor accesses named outputs. The descriptor is small JSON; it is
not executable model content.

Shipping app configuration must use `.productionOnly`. The supplied staging
hook also rejects model-level synthetic metadata even if a manifest is relabeled:

```sh
python scripts/fixtures/require_production_assets.py /path/to/staged/production/kokoro
```

Run this before Xcode model compilation in a consuming app's production
packaging flow. It supplements the existing runtime integrity checks rather
than replacing production download/digest verification. KokoroCoreML does not
own downstream app build configuration.

## Generation

Use Python 3.12 and a dedicated environment:

```sh
python3.12 -m venv .venv-fixtures
. .venv-fixtures/bin/activate
python -m pip install -r scripts/fixtures/requirements.txt
python scripts/fixtures/generate.py --version 1.1.0 --output /tmp/fixture-build/kokoro
python scripts/fixtures/package.py --bundle /tmp/fixture-build/kokoro --output-directory dist
```

The output location must not already exist. Generation builds in a temporary
sibling directory and moves the result into place only after construction.
It uses Core ML Tools 9.0, NumPy 2.2.6, and protobuf 6.33.0. It does not call Core
ML compilation, model prediction, Swift builds, or tests. Model construction
uses `skip_model_load=True`; it can run on Linux without the Apple runtime.

The committed fixture is generated from the source commit recorded in
`FixtureProvenance.json` and the runtime manifest. Recreate assets from that
commit into an empty output directory. Reproducibility means equivalent
contracts and deterministic synthesis output under the same inputs/seed.
Core ML package UUIDs and conversion metadata may differ, so archives are not
claimed to be byte-identical across separate generation runs. Every archive's
checksum and runtime hashes describe its own actual bytes. Archive file order,
permissions, owner fields, and timestamps are normalized by the packaging tool.
Do not hand-edit generated model internals.

## Contract source and release gate

The shared machine-readable descriptor is
`swift-tts/Sources/KokoroTTS/Resources/KokoroRuntime/KokoroFixtureContract.json`.
It pins the upstream exporter source at
`mattmireles/kokoro-coreml@a3f1ff27b1d8683efa9976704b46cb1d96da1a4b`.

This includes duration outputs `s` and `ref_s_out`, int32 token IDs/durations,
float32 boundary tensors, and required validity masks for all three acoustic
stages. The fixed generator takes `x_pre [1,512,1200]`, `har [1,22,72001]`, and
outputs `waveform [1,1,360000]`. Range generators and their extra masks are
outside this initial fixture contract.

**Published production model specification comparison remains a release gate.**
The initial implementation derived contracts from pinned exporter source;
access to the published binary specifications was unavailable during authoring.
Do not describe this as artifact-verified until the following comparison has
been explicitly requested and completed. It needs only the small
`Data/com.apple.CoreML/model.mlmodel` files, not production weights:

```sh
python scripts/fixtures/inspect_contract.py \
  --bundle /tmp/fixture-build/kokoro \
  --production-specs /path/to/pinned/production/specs \
  --production-revision EXACT_ARTIFACT_REVISION \
  --report /tmp/fixture-build/kokoro/ProductionContractInspection.json
```

Preserve package names and the `Data/com.apple.CoreML/model.mlmodel` layout in
the supplied specifications directory. The command rejects name, dtype, shape,
and static/flexible drift, and records exact specification SHA-256 hashes and
artifact revision. If the actual selected artifacts differ, update the contract,
generator, and runtime assumptions deliberately before release.

## Validation and release

Ask the user before running tests, runtime checks, CI, or device/simulator
validation. The implementation does not trigger any automatically.

When explicitly requested:

```sh
python scripts/fixtures/inspect_contract.py --bundle /tmp/fixture-build/kokoro
KOKORO_EXECUTABLE_FIXTURE_ROOT=/tmp/fixture-build/kokoro swift test --filter ExecutableFixtureTests
```

The focused tests cover default fixture rejection, strict fixture admission,
digest retention, cache namespacing, cold model compilation, staged contracts,
maximum 128-token duration span, final PCM, repeated predictions/cache reuse,
and public prewarm/multi-chunk synthesis. Executable tests skip without the
explicit fixture-root environment variable. Apple-device and bundled-model
collision checks should be requested separately; they are not UI tests.

## One manual workflow for generation, tests, and release

`Generate, test, and release fixtures` is **workflow_dispatch only**. It runs on
any selected branch or tag and always generates fresh fixtures, compares the
actual pinned production specifications, runs the macOS Core ML integration
tests, and packages the archive/checksum plus validation reports. A failed step
prevents publication.

GitHub must first register the workflow on the default branch (`master`) before
the **Run workflow** button is available. Once registered, select the branch
you want to run. This PR adds a new workflow; it is not automatically registered
while it exists only on the PR branch.

To create a downloadable release:

1. Open **Actions → Generate, test, and release fixtures → Run workflow**.
2. Select the source branch, normally `master` after review/merge.
3. Enter a new version such as `1.1.0` (without `v`). This becomes both the package
   tag and fixture artifact version.
4. Enter the exact `hf_revision` from the production bundle's
   `KokoroRuntimeManifest.json`. The workflow fetches only the small model
   specifications from that immutable HF revision, not production weights.
5. Enable **Create a new tag and GitHub Release after tests pass**.
6. Run the workflow. It creates the tag at the exact tested commit only after
   all generation, contract inspection, and runtime tests pass.

With `publish=false`, the same validation runs and the downloads remain in the
Actions run's artifact. With `publish=true`, a new GitHub Release contains:

- `kokoro-fixture-VERSION.tar.gz`
- `kokoro-fixture-VERSION.tar.gz.sha256`
- `FixtureValidation.json` (tested commit, version, macOS status, and run URL)
- `ProductionContractInspection.json` (actual specification hashes and revision)

The reports are also included inside the archive. Existing tags/releases are
not overwritten; select a new version for another published release.

After success, ReadAloud pins the exact package tag and downloads/extracts the
matching fixture archive. No consumer-owned generation is needed. iPhone
runtime validation remains separate from this macOS workflow.
