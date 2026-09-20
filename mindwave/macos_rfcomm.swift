// Native Bluetooth byte transport. Signal processing stays in the Python pipeline.
import Foundation
import IOBluetooth

func fail(_ message: String) -> Never {
    FileHandle.standardError.write(Data((message + "\n").utf8))
    exit(1)
}
func normalized(_ name: String) -> String {
    name.lowercased().filter { $0.isLetter || $0.isNumber }
}
let port = CommandLine.arguments.dropFirst().first ?? ""
let target = normalized(port.components(separatedBy: ".").last ?? port)
let paired = IOBluetoothDevice.pairedDevices() as? [IOBluetoothDevice] ?? []
let matches = paired.filter {
    let name = normalized($0.name ?? "")
    return !name.isEmpty && target.hasPrefix(name)
}
guard matches.count == 1 else { fail("No unique paired Bluetooth headset matches \(port)") }
let device = matches[0]
let services = device.services as? [IOBluetoothSDPServiceRecord] ?? []
var channelID: BluetoothRFCOMMChannelID = 0
for service in services {
    var candidate: BluetoothRFCOMMChannelID = 0
    if service.getRFCOMMChannelID(&candidate) == kIOReturnSuccess && candidate > 0 {
        channelID = candidate
        break
    }
}
guard channelID > 0 else { fail("Headset has no cached RFCOMM service; pair it again in Bluetooth settings") }

class Reader: NSObject, IOBluetoothRFCOMMChannelDelegate {
    var closed = false
    func rfcommChannelData(_ channel: IOBluetoothRFCOMMChannel!, data ptr: UnsafeMutableRawPointer!, length count: Int) {
        FileHandle.standardOutput.write(Data(bytes: ptr, count: count))
    }
    func rfcommChannelClosed(_ channel: IOBluetoothRFCOMMChannel!) { closed = true }
}
let reader = Reader()
var channel: IOBluetoothRFCOMMChannel?
let result = device.openRFCOMMChannelSync(&channel, withChannelID: channelID, delegate: reader)
guard result == kIOReturnSuccess else { fail("Bluetooth RFCOMM connection failed (\(result))") }
while !reader.closed {
    RunLoop.current.run(until: Date().addingTimeInterval(0.2))
}
channel?.close()
fail("Bluetooth headset disconnected")
