# Kokoro fixture assets

`kokoro/` is generated synthetic executable Core ML content. Do not copy it into
production app resources. It requires explicit `.executableFixture` admission.
See [generation, consumption, and release documentation](../docs/executable-fixtures.md).

The existing Tier 1 filesystem fixtures remain in `swift-tts/Tests` and do not
compile models. This directory is the separate Tier 2 executable fixture.
