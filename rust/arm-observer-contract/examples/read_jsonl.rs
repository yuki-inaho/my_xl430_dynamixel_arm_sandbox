use arm_observer_contract::{decode_line, Record};
use std::io::{self, BufRead};

fn main() -> Result<(), String> {
    for line in io::stdin().lock().lines() {
        let line = line.map_err(|error| error.to_string())?;
        if let Record::Frame { frame, .. } = decode_line(&line)? {
            for motor in frame.motors {
                println!(
                    "sequence={} id={} position={:?} torque={:?}",
                    frame.sequence, motor.motor_id, motor.position_counts, motor.torque_enabled
                );
            }
        }
    }
    Ok(())
}
