// swift-tools-version: 5.9

import PackageDescription

let package = Package(
    name: "KokoroCoreML",
    platforms: [
        .macOS("15.0"),
        .iOS("18.0"),
    ],
    products: [
        .library(
            name: "KokoroTTS",
            targets: ["KokoroTTS"]
        ),
        .library(
            name: "KokoroPipeline",
            targets: ["KokoroPipeline"]
        ),
        .executable(
            name: "kokoro-bench",
            targets: ["KokoroBenchmark"]
        ),
        .executable(
            name: "kokoro-hnsf-bench",
            targets: ["KokoroHnsfBenchmark"]
        ),
        .executable(
            name: "kokoro-misaki-probe",
            targets: ["KokoroMisakiProbe"]
        ),
        .executable(
            name: "kokoro-sdk-smoke",
            targets: ["KokoroSDKSmoke"]
        ),
    ],
    dependencies: [
        .package(
            url: "https://github.com/mattmireles/MisakiSwift",
            revision: "3a27756a780fc138e328a96e533fb440a3419d5b"
        ),
    ],
    targets: [
        .target(
            name: "KokoroPipeline",
            path: "swift/Sources/KokoroPipeline"
        ),
        .target(
            name: "KokoroTTS",
            dependencies: [
                "KokoroPipeline",
                .product(
                    name: "MisakiSwift",
                    package: "MisakiSwift"
                ),
            ],
            path: "swift-tts/Sources/KokoroTTS",
            resources: [
                .process("Resources"),
            ]
        ),
        .executableTarget(
            name: "KokoroBenchmark",
            dependencies: ["KokoroPipeline"],
            path: "swift/Sources/KokoroBenchmark"
        ),
        .executableTarget(
            name: "KokoroHnsfBenchmark",
            dependencies: ["KokoroPipeline"],
            path: "swift/Sources/KokoroHnsfBenchmark"
        ),
        .executableTarget(
            name: "KokoroMisakiProbe",
            dependencies: ["KokoroTTS"],
            path: "swift-tts/Sources/KokoroMisakiProbe"
        ),
        .executableTarget(
            name: "KokoroSDKSmoke",
            dependencies: ["KokoroTTS"],
            path: "swift-tts/Sources/KokoroSDKSmoke"
        ),
        .testTarget(
            name: "KokoroPipelineTests",
            dependencies: ["KokoroPipeline"],
            path: "swift/Tests/KokoroPipelineTests"
        ),
        .testTarget(
            name: "KokoroTTSTests",
            dependencies: [
                "KokoroPipeline",
                "KokoroTTS",
            ],
            path: "swift-tts/Tests/KokoroTTSTests"
        ),
    ]
)
