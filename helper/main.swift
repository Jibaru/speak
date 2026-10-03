import AppKit
import Carbon
import CoreAudio
import Foundation

struct Options {
    var port: UInt16 = 0
    var token = ""
    var hotkey = "option+escape"
    var stopOnMic = false
    var selfTest = false

    static func parse(_ arguments: [String]) -> Options {
        var options = Options()
        var iterator = arguments.dropFirst().makeIterator()
        while let argument = iterator.next() {
            switch argument {
            case "--port": options.port = UInt16(iterator.next() ?? "") ?? 0
            case "--token": options.token = iterator.next() ?? ""
            case "--hotkey": options.hotkey = iterator.next() ?? options.hotkey
            case "--stop-on-mic": options.stopOnMic = true
            case "--self-test": options.selfTest = true
            default: log("ignoring unknown argument \(argument)")
            }
        }
        return options
    }
}

func log(_ message: String) {
    FileHandle.standardError.write("speak-helper: \(message)\n".data(using: .utf8)!)
}

func requestStop(port: UInt16, token: String, source: String) {
    let descriptor = socket(AF_INET, SOCK_STREAM, 0)
    guard descriptor >= 0 else { return }
    defer { close(descriptor) }

    var address = sockaddr_in()
    address.sin_family = sa_family_t(AF_INET)
    address.sin_port = port.bigEndian
    address.sin_addr.s_addr = inet_addr("127.0.0.1")
    let connected = withUnsafePointer(to: &address) { pointer in
        pointer.withMemoryRebound(to: sockaddr.self, capacity: 1) {
            connect(descriptor, $0, socklen_t(MemoryLayout<sockaddr_in>.size))
        }
    }
    guard connected == 0 else { return }

    let message = "{\"op\":\"stop\",\"source\":\"\(source)\",\"token\":\"\(token)\"}\n"
    _ = message.withCString { write(descriptor, $0, strlen($0)) }
    var buffer = [UInt8](repeating: 0, count: 256)
    _ = read(descriptor, &buffer, buffer.count)
}

enum Hotkey {
    static let keyCodes: [String: UInt32] = [
        "escape": 53, "esc": 53, "space": 49, "return": 36, "tab": 48, "delete": 51,
        "f1": 122, "f2": 120, "f3": 99, "f4": 118, "f5": 96, "f6": 97,
        "f7": 98, "f8": 100, "f9": 101, "f10": 109, "f11": 103, "f12": 111,
        "a": 0, "s": 1, "d": 2, "f": 3, "h": 4, "g": 5, "z": 6, "x": 7, "c": 8, "v": 9,
        "b": 11, "q": 12, "w": 13, "e": 14, "r": 15, "y": 16, "t": 17, "o": 31, "u": 32,
        "i": 34, "p": 35, "l": 37, "j": 38, "k": 40, "n": 45, "m": 46, "period": 47,
    ]
    static let modifiers: [String: UInt32] = [
        "option": UInt32(optionKey), "alt": UInt32(optionKey),
        "cmd": UInt32(cmdKey), "command": UInt32(cmdKey),
        "ctrl": UInt32(controlKey), "control": UInt32(controlKey),
        "shift": UInt32(shiftKey),
    ]

    static func parse(_ description: String) -> (keyCode: UInt32, modifiers: UInt32)? {
        let parts = description.lowercased().split(separator: "+").map(String.init)
        guard let key = parts.last, let keyCode = keyCodes[key] else { return nil }
        var flags: UInt32 = 0
        for part in parts.dropLast() {
            guard let flag = modifiers[part] else { return nil }
            flags |= flag
        }
        return (keyCode, flags)
    }

    static func register(_ description: String, onPress: @escaping () -> Void) -> Bool {
        guard let (keyCode, flags) = parse(description) else { return false }
        HotkeyTarget.shared.onPress = onPress

        var eventType = EventTypeSpec(eventClass: OSType(kEventClassKeyboard), eventKind: UInt32(kEventHotKeyPressed))
        InstallEventHandler(GetApplicationEventTarget(), { _, _, _ in
            HotkeyTarget.shared.onPress?()
            return noErr
        }, 1, &eventType, nil, nil)

        var reference: EventHotKeyRef?
        let identifier = EventHotKeyID(signature: OSType(0x5350_4B48), id: 1)
        return RegisterEventHotKey(keyCode, flags, identifier, GetApplicationEventTarget(), 0, &reference) == noErr
    }
}

final class HotkeyTarget {
    static let shared = HotkeyTarget()
    var onPress: (() -> Void)?
}

final class MicrophoneMonitor {
    private let onStart: () -> Void
    private var device = AudioObjectID(kAudioObjectUnknown)
    private var wasRunning = false
    private let queue = DispatchQueue(label: "speak.mic")

    init(onStart: @escaping () -> Void) {
        self.onStart = onStart
    }

    func start() {
        var defaultInput = Self.address(kAudioHardwarePropertyDefaultInputDevice)
        AudioObjectAddPropertyListenerBlock(AudioObjectID(kAudioObjectSystemObject), &defaultInput, queue) { [weak self] _, _ in
            self?.attachToDefaultInput()
        }
        queue.sync { attachToDefaultInput() }
    }

    private func attachToDefaultInput() {
        var running = Self.address(kAudioDevicePropertyDeviceIsRunningSomewhere)
        if device != kAudioObjectUnknown {
            AudioObjectRemovePropertyListenerBlock(device, &running, queue, listener)
        }
        device = Self.defaultInputDevice()
        guard device != kAudioObjectUnknown else { return }
        wasRunning = isRunning()
        AudioObjectAddPropertyListenerBlock(device, &running, queue, listener)
    }

    private lazy var listener: AudioObjectPropertyListenerBlock = { [weak self] _, _ in
        guard let self else { return }
        let running = self.isRunning()
        if running && !self.wasRunning { self.onStart() }
        self.wasRunning = running
    }

    private func isRunning() -> Bool {
        var address = Self.address(kAudioDevicePropertyDeviceIsRunningSomewhere)
        var value: UInt32 = 0
        var size = UInt32(MemoryLayout<UInt32>.size)
        return AudioObjectGetPropertyData(device, &address, 0, nil, &size, &value) == noErr && value != 0
    }

    private static func defaultInputDevice() -> AudioObjectID {
        var address = address(kAudioHardwarePropertyDefaultInputDevice)
        var device = AudioObjectID(kAudioObjectUnknown)
        var size = UInt32(MemoryLayout<AudioObjectID>.size)
        AudioObjectGetPropertyData(AudioObjectID(kAudioObjectSystemObject), &address, 0, nil, &size, &device)
        return device
    }

    private static func address(_ selector: AudioObjectPropertySelector) -> AudioObjectPropertyAddress {
        AudioObjectPropertyAddress(mSelector: selector, mScope: kAudioObjectPropertyScopeGlobal, mElement: kAudioObjectPropertyElementMain)
    }
}

let options = Options.parse(CommandLine.arguments)
guard options.port != 0, !options.token.isEmpty else {
    log("missing --port or --token")
    exit(2)
}

if options.selfTest {
    requestStop(port: options.port, token: options.token, source: "helper-self-test")
    exit(0)
}

let application = NSApplication.shared
application.setActivationPolicy(.prohibited)

if Hotkey.register(options.hotkey, onPress: { requestStop(port: options.port, token: options.token, source: "hotkey") }) {
    log("hotkey \(options.hotkey) registered")
} else {
    log("could not register hotkey \(options.hotkey)")
}

let microphone = MicrophoneMonitor { requestStop(port: options.port, token: options.token, source: "mic") }
if options.stopOnMic {
    microphone.start()
    log("watching microphone")
}

let parent = getppid()
Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { _ in
    if getppid() != parent { exit(0) }
}

application.run()
