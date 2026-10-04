use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct BusConfig {
    pub device: String,
    pub baudrate: u32,
    pub protocol: f64,
    pub expected_ids: Vec<u8>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct JointRole {
    pub motor_id: u8,
    pub name: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ArmConfig {
    pub bus: BusConfig,
    pub roles: Vec<JointRole>,
    pub physical_order_verified: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Fault {
    pub motor_id: u8,
    pub operation: String,
    pub comm_result: i32,
    pub device_error: u8,
    pub message: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Identity {
    pub motor_id: u8,
    pub model_number: u16,
    pub firmware_version: Option<u8>,
    pub observed_at: String,
    pub device_error: u8,
    pub faults: Vec<Fault>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RegisterValue {
    pub name: String,
    pub address: u16,
    pub size: u8,
    pub memory: String,
    pub raw: u32,
    pub value: i64,
    pub device_alert: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct MotorMetadata {
    pub motor_id: u8,
    pub identity: Option<Identity>,
    pub proposed_role: Option<String>,
    pub registers: Vec<RegisterValue>,
    pub faults: Vec<Fault>,
    pub skipped_registers: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct MotorTelemetry {
    pub motor_id: u8,
    pub torque_enabled: Option<bool>,
    pub hardware_error: Option<u8>,
    pub position_counts: Option<i32>,
    pub velocity_raw: Option<i32>,
    pub pwm_raw: Option<i16>,
    pub load_raw: Option<i16>,
    pub voltage_raw: Option<u16>,
    pub temperature_c: Option<u8>,
    pub moving: Option<bool>,
    pub moving_status: Option<u8>,
    pub tick_ms: Option<u16>,
    pub device_alert: bool,
    pub faults: Vec<Fault>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ReadMode {
    Sync,
    Unicast,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct TelemetryFrame {
    pub sequence: u64,
    pub started_at: String,
    pub finished_at: String,
    pub monotonic_ns: u64,
    pub duration_ms: f64,
    pub requested_rate_hz: f64,
    pub deadline_missed: bool,
    pub read_mode: ReadMode,
    pub motors: Vec<MotorTelemetry>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct StreamSummary {
    pub frames: u64,
    pub incomplete_frames: u64,
    pub deadline_misses: u64,
    pub elapsed_seconds: f64,
    pub achieved_rate_hz: f64,
    pub interrupted: bool,
    pub port_closed: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
pub enum Record {
    Metadata {
        schema_version: u32,
        metadata: Vec<MotorMetadata>,
        config: ArmConfig,
        observed_at: String,
        #[serde(default)]
        simulated: Option<bool>,
        #[serde(default)]
        acquisition_id: Option<String>,
    },
    Frame {
        schema_version: u32,
        frame: TelemetryFrame,
    },
    End {
        schema_version: u32,
        summary: StreamSummary,
    },
}

pub fn decode_line(line: &str) -> Result<Record, String> {
    let record: Record = serde_json::from_str(line).map_err(|error| error.to_string())?;
    let version = match &record {
        Record::Metadata { schema_version, .. }
        | Record::Frame { schema_version, .. }
        | Record::End { schema_version, .. } => *schema_version,
    };
    if version != 2 {
        return Err(format!("Unsupported schema version: {version}"));
    }
    Ok(record)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn python_fixture_preserves_signed_values_and_unknowns() {
        let line = include_str!("../../../tests/fixtures/frame_v2.json");
        let Record::Frame { frame, .. } = decode_line(line).unwrap() else {
            panic!("expected frame");
        };
        assert_eq!(frame.motors[0].position_counts, Some(-2048));
        assert_eq!(frame.motors[0].load_raw, Some(-30));
        assert_eq!(frame.motors[1].position_counts, None);
        assert_eq!(frame.motors[1].faults[0].comm_result, -3001);
    }

    #[test]
    fn python_stream_events_round_trip() {
        let stream = include_str!("../../../tests/fixtures/stream_v2.jsonl");
        for line in stream.lines() {
            let record = decode_line(line).unwrap();
            decode_line(&serde_json::to_string(&record).unwrap()).unwrap();
        }
    }

    #[test]
    fn unknown_schema_version_is_rejected() {
        let line = include_str!("../../../tests/fixtures/frame_v2.json");
        assert!(
            decode_line(&line.replace("\"schema_version\": 2", "\"schema_version\": 99")).is_err()
        );
    }
}
