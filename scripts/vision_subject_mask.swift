import CoreImage
import Foundation
import ImageIO
import Vision

enum MaskError: Error {
    case usage
    case imageLoad
    case noSubject
}

guard CommandLine.arguments.count == 3 else {
    throw MaskError.usage
}

let inputURL = URL(fileURLWithPath: CommandLine.arguments[1])
let outputURL = URL(fileURLWithPath: CommandLine.arguments[2])
guard
    let source = CGImageSourceCreateWithURL(inputURL as CFURL, nil),
    let image = CGImageSourceCreateImageAtIndex(source, 0, nil)
else {
    throw MaskError.imageLoad
}

let request = VNGenerateForegroundInstanceMaskRequest()
let handler = VNImageRequestHandler(cgImage: image, options: [:])
try handler.perform([request])
guard let observation = request.results?.first else {
    throw MaskError.noSubject
}

let maskBuffer = try observation.generateScaledMaskForImage(
    forInstances: observation.allInstances,
    from: handler
)
let maskImage = CIImage(cvPixelBuffer: maskBuffer)
let context = CIContext(options: [.useSoftwareRenderer: false])
try context.writePNGRepresentation(
    of: maskImage,
    to: outputURL,
    format: .L8,
    colorSpace: CGColorSpaceCreateDeviceGray()
)
