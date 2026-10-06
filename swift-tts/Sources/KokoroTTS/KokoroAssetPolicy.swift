import Foundation

/// Selects which asset provenance may enter the normal Kokoro runtime.
public enum KokoroAssetPolicy: Sendable {
    /// Accept existing verified production bundles; reject synthetic fixtures.
    case productionOnly

    /// Accept only the versioned synthetic fixture profile, retaining integrity checks.
    /// Never select this policy in a shipping app's production configuration.
    case executableFixture

    func validate(_ manifest: KokoroRuntimeManifest) throws {
        let declaresFixture = manifest.syntheticFixture != nil
            || manifest.bundleProfile.hasPrefix("fixture")
        switch self {
        case .productionOnly:
            guard !declaresFixture else { throw KokoroError.fixtureAssetsRejected }
            guard manifest.hfProvenanceVerified else {
                throw KokoroError.badHash(path: "hf_provenance_verified")
            }
        case .executableFixture:
            guard manifest.bundleProfile == "fixture-executable-v1",
                  let fixture = manifest.syntheticFixture,
                  fixture.kind == "synthetic-coreml",
                  fixture.contractVersion == 1,
                  !fixture.generatorRevision.isEmpty,
                  !fixture.artifactVersion.isEmpty,
                  !manifest.hfProvenanceVerified,
                  manifest.hfRepoID.isEmpty,
                  manifest.hfRevision.isEmpty,
                  manifest.hfDownloadManifestSHA256.isEmpty,
                  manifest.durationTokenSizes == [128],
                  manifest.buckets == [15],
                  manifest.modelPackages.count == 4,
                  Set(manifest.modelPackages.map(\.path)) == Set([
                    "coreml/kokoro_duration_t128.mlpackage",
                    "coreml/kokoro_f0ntrain_t600.mlpackage",
                    "coreml/kokoro_decoder_pre_15s.mlpackage",
                    "coreml/kokoro_decoder_har_post_15s.mlpackage",
                  ])
            else {
                throw KokoroError.invalidFixtureManifest
            }
        }
    }
}
