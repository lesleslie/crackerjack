// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "SwiftLib",
    platforms: [
        .macOS(.v13),
    ],
    products: [
        .library(name: "SwiftLib", targets: ["SwiftLib"]),
    ],
    targets: [
        .target(name: "SwiftLib", path: "Sources/SwiftLib"),
    ]
)
