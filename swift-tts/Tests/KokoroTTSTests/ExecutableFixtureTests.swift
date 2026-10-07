import CoreML
import Foundation
import KokoroPipeline
import XCTest
@testable import KokoroTTS

/// Authored for manual validation; no tests are triggered by fixture generation.
final class ExecutableFixtureTests: XCTestCase {
    func testProductionAdmissionRejectsTruthfulFixtures() throws {
        let root = try filesystemFixture()
        defer { try? FileManager.default.removeItem(at: root) }
        XCTAssertThrowsError(try KokoroSDKModelProvider(resources: .directory(root))) {
            XCTAssertEqual($0 as? KokoroError, .fixtureAssetsRejected)
        }
    }

    func testFixtureAdmissionRetainsDigestValidation() throws {
        let root = try filesystemFixture()
        defer { try? FileManager.default.removeItem(at: root) }
        try Data([1]).write(to: root.appendingPathComponent("voices/af_heart.bin"))
        XCTAssertThrowsError(try KokoroSDKModelProvider(resources: .directory(root), assetPolicy: .executableFixture)) {
            XCTAssertEqual($0 as? KokoroError, .badHash(path: "voices/af_heart.bin"))
        }
    }

    func testFixtureAdmissionCannotBypassProductionProvenance() throws {
        let root = try KokoroBundleFixture.makeBundleRoot()
        defer { try? FileManager.default.removeItem(at: root) }
        XCTAssertThrowsError(try KokoroSDKModelProvider(resources: .directory(root), assetPolicy: .executableFixture)) {
            XCTAssertEqual($0 as? KokoroError, .invalidFixtureManifest)
        }
    }

    func testExplicitCachesAreNamespacedByFixtureIdentity() throws {
        let root = try filesystemFixture()
        let shared = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: root) }
        let provider = try KokoroSDKModelProvider(
            resources: .directory(root, compiledModelsDirectory: shared), assetPolicy: .executableFixture
        )
        XCTAssertEqual(provider.compiledModelsDirectory.deletingLastPathComponent(), shared)
        XCTAssertTrue(provider.compiledModelsDirectory.lastPathComponent.hasPrefix("fixture-"))
    }

    func testExecutableStagesAndMaximumDurationSpan() throws {
        let root = try executableRoot()
        let cache = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: cache) }
        let resources = KokoroResourceProvider.directory(root, compiledModelsDirectory: cache)
        let provider = try KokoroSDKModelProvider(resources: resources, computePolicy: .cpuOnly, assetPolicy: .executableFixture)
        // This new cache forces compilation. Runtime fixture checks bind all stage contracts.
        try provider.prewarm()
        let weights = try provider.hnsfWeights()
        // Vocab ID 43 is "a", an ordinary phoneme, so punctuation postprocessing preserves it.
        let request = KokoroSynthesisRequest(inputIds: [Int32](repeating: 43, count: 128),
            attentionMask: [Int32](repeating: 1, count: 128), refS: [Float](repeating: 0.001, count: 256))
        var dump: TensorDumpWriter? = nil
        let result = try executeKokoroSynthesis(request: request, modelProvider: provider,
            linearWeights: weights.linearWeights, linearBias: weights.linearBias, tensorDump: &dump)
        XCTAssertEqual(result.tokenDurationFrames, [Int](repeating: 1, count: 128))
        XCTAssertEqual(result.audio.count, 128 * 600)
        XCTAssertTrue(result.audio.allSatisfy(\.isFinite))
        XCTAssertGreaterThan(result.audio.map { abs($0) }.max() ?? 0, 0.001)
        // A second provider must reuse the same source-identified compiled cache.
        let warm = try KokoroSDKModelProvider(resources: resources, computePolicy: .cpuOnly, assetPolicy: .executableFixture)
        try warm.prewarm()
        var secondDump: TensorDumpWriter? = nil
        let repeated = try executeKokoroSynthesis(request: request, modelProvider: warm,
            linearWeights: weights.linearWeights, linearBias: weights.linearBias, tensorDump: &secondDump)
        XCTAssertEqual(result.audio, repeated.audio)
    }

    func testPublicPrewarmAndMultiChunkSynthesis() async throws {
        let root = try executableRoot()
        let cache = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: cache) }
        let tts = try await KokoroTTS.load(resources: .directory(root, compiledModelsDirectory: cache),
            computePolicy: .cpuOnly, assetPolicy: .executableFixture)
        try await tts.prewarm()
        let text = String(repeating: "Hello world. ", count: 20)
        let options = KokoroSynthesisOptions(maxCharacters: 40)
        let prepared = try await tts.prepare(text, options: options)
        XCTAssertGreaterThan(prepared.count, 1)
        let audio = try await tts.synthesize(text, options: options)
        let repeated = try await tts.synthesizePrepared(prepared)
        XCTAssertFalse(audio.samples.isEmpty)
        XCTAssertTrue(audio.samples.allSatisfy(\.isFinite))
        XCTAssertGreaterThan(audio.samples.map { abs($0) }.max() ?? 0, 0.001)
        XCTAssertEqual(audio.samples, repeated.samples)
    }

    private func executableRoot() throws -> URL {
        guard let path = ProcessInfo.processInfo.environment["KOKORO_EXECUTABLE_FIXTURE_ROOT"] else {
            throw XCTSkip("Set KOKORO_EXECUTABLE_FIXTURE_ROOT only when executable validation is requested")
        }
        return URL(fileURLWithPath: path, isDirectory: true)
    }

    private func filesystemFixture() throws -> URL {
        let root = try KokoroBundleFixture.makeBundleRoot()
        let url = root.appendingPathComponent("KokoroRuntimeManifest.json")
        var manifest = try XCTUnwrap(JSONSerialization.jsonObject(with: Data(contentsOf: url)) as? [String: Any])
        manifest["bundle_profile"] = "fixture-executable-v1"
        manifest["hf_provenance_verified"] = false
        manifest["hf_repo_id"] = ""
        manifest["hf_revision"] = ""
        manifest["hf_download_manifest_sha256"] = ""
        manifest["synthetic_fixture"] = ["kind": "synthetic-coreml", "contract_version": 1,
            "generator_revision": "unit-fixture", "artifact_version": "unit-fixture"]
        try JSONSerialization.data(withJSONObject: manifest, options: [.sortedKeys]).write(to: url)
        return root
    }
}
