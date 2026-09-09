public struct SwiftLib {
    public let name: String

    public init(name: String) {
        self.name = name
    }

    public func greet() -> String {
        "Hello, \(name)!"
    }
}
