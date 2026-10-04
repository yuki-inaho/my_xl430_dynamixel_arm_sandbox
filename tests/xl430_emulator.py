"""Serial-level Protocol 2.0 emulator of five XL430-W250 (offline only, no device).

Written during the 2026-10-03 adversarial review of the ID3 motion command and kept as a test
utility: it answers PING, READ, WRITE and SYNC_READ frames with CRC-correct status packets,
moves a torque-enabled motor toward its goal on each telemetry SYNC_READ, and exposes
read/write hooks so tests can raise interrupts or drop packets inside SDK transactions.
"""
from dynamixel_sdk.protocol2_packet_handler import Protocol2PacketHandler

CRC = Protocol2PacketHandler()


def crc_frame(body):
    frame = list(body) + [0, 0]
    crc = CRC.updateCRC(0, frame, len(frame) - 2)
    frame[-2], frame[-1] = crc & 0xFF, crc >> 8
    return frame


def put(table, address, size, value):
    table[address:address + size] = (value & ((1 << (8 * size)) - 1)).to_bytes(size, "little")


def get(table, address, size):
    return int.from_bytes(bytes(table[address:address + size]), "little")


class Motor:
    def __init__(self, mid, pos):
        t = bytearray(160)
        put(t, 0, 2, 1060)
        put(t, 6, 1, 42)
        put(t, 7, 1, mid)
        put(t, 8, 1, 3)
        put(t, 9, 1, 250)
        put(t, 11, 1, 3)
        put(t, 12, 1, 255)
        put(t, 13, 1, 2)
        put(t, 36, 2, 885)
        put(t, 48, 4, 4095)
        put(t, 52, 4, 0)
        put(t, 68, 1, 2)
        put(t, 100, 2, 885)
        put(t, 116, 4, pos)
        put(t, 132, 4, pos)
        put(t, 144, 2, 91)
        put(t, 146, 1, 35)
        self.t = t
        self.mid = mid

    def step(self, amount):
        t = self.t
        if t[64]:
            pos, goal = get(t, 132, 4), get(t, 116, 4)
            delta = goal - pos
            pos += max(-amount, min(amount, delta))
            put(t, 132, 4, pos)
            t[123] = 2 if pos != goal else 0
            t[122] = 1 if pos != goal else 0
        else:
            t[123] = 0
            t[122] = 0


class EmuSerial:
    """Fake pyserial object. Hooks may raise from read/write to model interrupts/IO errors;
    `drop` decides per WRITE frame whether the motor never receives it (lost packet)."""

    def __init__(self, positions=(2052, 3354, 1153, 2059, 2059), step=12):
        self.motors = {i + 1: Motor(i + 1, p) for i, p in enumerate(positions)}
        self.rx = bytearray()
        self.sent = []
        self.step_amount = step
        self.read_hook = None
        self.write_hook = None
        self.drop = None
        self.is_open = True

    # pyserial surface used by PortHandler
    def reset_input_buffer(self):
        self.rx.clear()

    @property
    def in_waiting(self):
        return len(self.rx)

    def close(self):
        self.is_open = False

    def read(self, n):
        if self.read_hook:
            self.read_hook(self)
        out = bytes(self.rx[:n])
        del self.rx[:n]
        return out

    def write(self, packet):
        if self.write_hook:
            self.write_hook(self, packet)
        data = bytes(packet)
        self.sent.append(data)
        if not (self.drop and data[7] == 0x03 and self.drop(data)):
            self.handle(list(data))
        return len(data)

    # protocol
    def status(self, mid, params=(), err=0):
        length = len(params) + 4
        header = [0xFF, 0xFF, 0xFD, 0, mid, length & 255, length >> 8, 0x55, err]
        self.rx += bytes(crc_frame([*header, *params]))

    def handle(self, p):
        mid, inst = p[4], p[7]
        if inst == 0x01 and mid in self.motors:
            m = self.motors[mid].t
            self.status(mid, [m[0], m[1], m[6]])
        elif inst == 0x02 and mid in self.motors:
            addr, size = p[8] | p[9] << 8, p[10] | p[11] << 8
            self.status(mid, list(self.motors[mid].t[addr:addr + size]))
        elif inst == 0x03 and mid in self.motors:
            addr = p[8] | p[9] << 8
            data = p[10:-2]
            # Secondary ID accepts RAM writes without its own status response.
            for motor in self.motors.values():
                if motor.mid == mid or (addr >= 64 and motor.t[12] == mid):
                    motor.t[addr:addr + len(data)] = bytes(data)
            self.status(mid)
        elif inst == 0x82:
            addr, size = p[8] | p[9] << 8, p[10] | p[11] << 8
            if addr == 120:
                for m in self.motors.values():
                    m.step(self.step_amount)
            for i in p[12:-2]:
                if i in self.motors:
                    self.status(i, list(self.motors[i].t[addr:addr + size]))

    def torque(self, mid=3):
        return self.motors[mid].t[64]

    def writes(self):
        return [(f[4], f[8] | f[9] << 8, int.from_bytes(f[10:-2], "little"))
                for f in self.sent if f[7] == 3]
