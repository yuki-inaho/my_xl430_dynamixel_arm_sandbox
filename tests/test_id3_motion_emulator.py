"""End-to-end ID3 motion through the real DynamixelSDK and a serial-level XL430 emulator."""
from dynamixel_sdk import PacketHandler
from test_id3_motion import FakeClock, evidence_record, write_evidence
from xl430_emulator import EmuSerial

from arm_observer import id3_motion as motion
from arm_observer.motion_guard import MotionPort
from arm_observer.reader import SdkReader


def emulated_port(**kwargs):
    port = MotionPort("offline-emulator")
    port.ser = EmuSerial(**kwargs)
    port.is_open = True
    port.baudrate = 1000000
    port.tx_time_per_byte = (1000.0 / 1000000) * 10.0
    return port


def run(tmp_path, port):
    packet = PacketHandler(2.0)
    evidence = motion.load_evidence(write_evidence(tmp_path, evidence_record()))
    clock = FakeClock()
    return motion.run_motion(SdkReader(port, packet), motion.Id3Actuator(port, packet), evidence,
                             lambda event: None, clock.monotonic, clock.sleep)


def test_real_sdk_run_writes_only_id3_and_ends_torque_off(tmp_path):
    port = emulated_port()
    outcome = run(tmp_path, port)
    assert outcome.status == "converged" and outcome.torque_off_confirmed is True
    writes = port.ser.writes()
    assert {motor_id for motor_id, _, _ in writes} == {3}
    assert {address for _, address, _ in writes} <= {64, 100, 108, 112, 116}
    assert port.ser.torque() == 0 and port.is_using is False
    assert {opcode for opcode in (frame[7] for frame in port.ser.sent)} <= {0x02, 0x03, 0x82}


def test_interrupt_inside_a_sync_read_still_sends_torque_off(tmp_path):
    port = emulated_port()
    state = {"reads": 0}

    def interrupt(serial):
        state["reads"] += 1
        if state["reads"] == 400 and serial.torque():
            raise KeyboardInterrupt  # lands inside an SDK transaction, leaving is_using set

    port.ser.read_hook = interrupt
    outcome = run(tmp_path, port)
    assert outcome.interrupted is True and outcome.torque_off_confirmed is True
    assert port.ser.torque() == 0 and port.is_using is False


def test_lost_torque_off_is_reported_and_nothing_else_is_written(tmp_path):
    port = emulated_port()
    port.ser.drop = lambda frame: frame[8] == 64 and frame[10] == 0  # Torque=0 never arrives
    outcome = run(tmp_path, port)
    assert outcome.torque_off_confirmed is False
    assert motion.exit_code(outcome) == 3
    writes = port.ser.writes()
    first_off = next(i for i, write in enumerate(writes) if write[1:] == (64, 0))
    assert all(write[1:] == (64, 0) for write in writes[first_off:])  # only Torque=0 retries
    assert port.ser.torque() == 1
