package com.pulsestream.telemetry.eventlog.domain;

import com.pulsestream.telemetry.validation.domain.TelemetrySample;

public record EventRecord(TelemetrySample sample, int revision, String kind) {

    public static final String KIND_RECORD = "RECORD";

    public static final String KIND_REVISION = "REVISION";
}
