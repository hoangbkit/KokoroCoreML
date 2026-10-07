import CoreML
import Foundation
import KokoroPipeline

/// Checks synthetic models before the executor's named output bindings are used.
/// The tiny descriptor is bundled; executable fixture models are never library resources.
enum KokoroFixtureContract {
    private struct Contract: Decodable {
        let models: [Model]
    }

    private struct Model: Decodable {
        let name: String
        let inputs: [Tensor]
        let outputs: [Tensor]
    }

    private struct Tensor: Decodable {
        let name: String
        let shape: [Int]
        let dtype: String
    }

    static func validate(_ model: MLModel, packageName: String) throws {
        let url = try KokoroRuntimeAssets.url(for: .fixtureContract)
        let contract = try JSONDecoder().decode(Contract.self, from: Data(contentsOf: url))
        guard let expected = contract.models.first(where: { $0.name == packageName }) else {
            throw mismatch(packageName, "package is outside the fixture contract")
        }
        try validate(model.modelDescription.inputDescriptionsByName, tensors: expected.inputs, packageName: packageName)
        try validate(model.modelDescription.outputDescriptionsByName, tensors: expected.outputs, packageName: packageName)
    }

    private static func validate(
        _ descriptions: [String: MLFeatureDescription], tensors: [Tensor], packageName: String
    ) throws {
        guard Set(descriptions.keys) == Set(tensors.map(\.name)) else {
            throw mismatch(packageName, "input/output names changed")
        }
        for tensor in tensors {
            guard let constraint = descriptions[tensor.name]?.multiArrayConstraint else {
                throw mismatch(packageName, "\(tensor.name) must be a multi-array")
            }
            let expectedType: MLMultiArrayDataType
            switch tensor.dtype {
            case "int32": expectedType = .int32
            case "float32": expectedType = .float32
            default: throw mismatch(packageName, "unsupported contract dtype \(tensor.dtype)")
            }
            guard constraint.dataType == expectedType,
                  constraint.shape.map({ $0.intValue }) == tensor.shape else {
                throw mismatch(packageName, "\(tensor.name) dtype or shape changed")
            }
        }
    }

    private static func mismatch(_ package: String, _ detail: String) -> PipelineError {
        .modelContractMismatch("fixture \(package): \(detail)")
    }
}
