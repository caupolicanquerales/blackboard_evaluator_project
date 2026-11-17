package com.pulsestream.telemetry.validation.application;

import org.springframework.stereotype.Service;
import io.micrometer.core.instrument.MeterRegistry;
import com.pulsestream.telemetry.shared.config.TelemetryProperties;
import com.pulsestream.telemetry.shared.observability.StepLog;
import com.pulsestream.telemetry.validation.domain.TelemetrySample;

@Service
public class ValidationService {

    private final TelemetryProperties properties;

    private final StepLog stepLog;

    private final MeterRegistry meterRegistry;

    public ValidationService(TelemetryProperties properties, StepLog stepLog, MeterRegistry meterRegistry) {
        this.properties = properties;
        this.stepLog = stepLog;
        this.meterRegistry = meterRegistry;
    }

    private boolean isValid(String metric, double value) {
        if (metric == null) {
            return true;
        }
        return switch(metric) {
            case "heart_rate" ->
                value >= properties.heartRateMin() && value <= properties.heartRateMax();
            case "power" ->
                value >= properties.powerMin() && value <= properties.powerMax();
            case "cadence" ->
                value >= properties.cadenceMin() && value <= properties.cadenceMax();
            case "swim_pace" ->
                value > properties.swimPaceMinExclusive();
            default ->
                true;
        };
    }

    public TelemetrySample validate(TelemetrySample sample) {
        boolean valid = isValid(sample.metric(), sample.value());
        String status = valid ? "valid" : "failed";
        meterRegistry.counter("telemetry.validation.samples", "status", status).increment();
        stepLog.emit(valid ? "validation.sample.validated" : "validation.sample.failed", sample.correlationId());
        return sample.withStatus(valid ? TelemetrySample.STATUS_VALID : TelemetrySample.STATUS_VALIDATION_FAILED);
    }
}
