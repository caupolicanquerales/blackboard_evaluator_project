package com.pulsestream.telemetry.validation.application;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;

import com.pulsestream.telemetry.shared.config.TelemetryProperties;
import com.pulsestream.telemetry.shared.observability.StepLog;
import com.pulsestream.telemetry.validation.domain.TelemetrySample;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import java.time.Instant;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

class ValidationServiceTest {

    private static final String VALID = "VALID";
    private static final String FAILED = "VALIDATION_FAILED";
    private static final String COUNTER = "telemetry.validation.samples";

    private StepLog stepLog;
    private SimpleMeterRegistry registry;
    private ValidationService service;

    @BeforeEach
    void setUp() {
        TelemetryProperties props = new TelemetryProperties(5L, 100, 30.0, 220.0, 0.0, 2000.0, 20.0, 150.0, 0.5);
        stepLog = mock(StepLog.class);
        registry = new SimpleMeterRegistry();
        service = new ValidationService(props, stepLog, registry);
    }

    private static TelemetrySample sample(String metric, double value) {
        return new TelemetrySample("dev-1", metric, Instant.parse("2024-01-01T00:00:00Z"),
                Instant.parse("2024-01-01T00:00:01Z"), value, "RECEIVED", "corr-1");
    }

    @ParameterizedTest
    @CsvSource({
        "heart_rate,30.0", "heart_rate,220.0", "heart_rate,100.0",
        "power,0.0", "power,2000.0", "cadence,20.0", "cadence,150.0",
        "swim_pace,0.6"
    })
    void validate_valueWithinBounds_returnsValid(String metric, double value) {
        TelemetrySample result = service.validate(sample(metric, value));

        assertThat(result.status()).isEqualTo(VALID);
    }

    @ParameterizedTest
    @CsvSource({
        "heart_rate,29.9", "heart_rate,220.1", "power,-0.1", "power,2000.1",
        "cadence,19.9", "cadence,150.1", "swim_pace,0.5", "swim_pace,0.4"
    })
    void validate_valueOutOfRange_returnsValidationFailed(String metric, double value) {
        TelemetrySample result = service.validate(sample(metric, value));

        assertThat(result.status()).isEqualTo(FAILED);
    }

    @ParameterizedTest
    @CsvSource({
        "ground_contact_time,-1000.0", "respiration,99999.0", "swim_stroke,0.0", "mystery_metric,-5.0"
    })
    void validate_unboundedMetric_returnsValid(String metric, double value) {
        TelemetrySample result = service.validate(sample(metric, value));

        assertThat(result.status()).isEqualTo(VALID);
    }

    @Test
    void validate_failedSample_preservesPayload() {
        TelemetrySample input = sample("heart_rate", 500.0);

        TelemetrySample result = service.validate(input);

        assertThat(result).usingRecursiveComparison().ignoringFields("status").isEqualTo(input);
    }

    @Test
    void validate_validSample_incrementsValidCounterOnly() {
        service.validate(sample("heart_rate", 100.0));

        assertThat(registry.get(COUNTER).tag("status", "valid").counter().count()).isEqualTo(1.0);
        assertThat(registry.find(COUNTER).tag("status", "failed").counter())
                .satisfiesAnyOf(c -> assertThat(c).isNull(), c -> assertThat(c.count()).isZero());
    }

    @Test
    void validate_invalidSample_incrementsFailedCounter() {
        service.validate(sample("heart_rate", 500.0));
        service.validate(sample("power", -5.0));

        assertThat(registry.get(COUNTER).tag("status", "failed").counter().count()).isEqualTo(2.0);
    }

    @Test
    void validate_validSample_emitsValidatedStepWithCorrelationId() {
        service.validate(sample("heart_rate", 100.0));

        verify(stepLog).emit("validation.sample.validated", "corr-1");
        verify(stepLog, never()).emit("validation.sample.failed", "corr-1");
    }

    @Test
    void validate_invalidSample_emitsFailedStepWithCorrelationId() {
        service.validate(sample("heart_rate", 500.0));

        verify(stepLog).emit("validation.sample.failed", "corr-1");
        verify(stepLog, never()).emit("validation.sample.validated", "corr-1");
    }
}
