package com.pulsestream.telemetry.intake.domain;
import org.checkerframework.checker.units.qual.Temperature;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatNoException;

import java.time.Instant;
import java.util.HashMap;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

class SensorMetricBoundaryPolicyTest {

    private static final Instant T_DEVICE = Instant.parse("2024-01-01T00:00:00Z");
    private static final Instant T_INGRESS = Instant.parse("2024-01-01T00:00:01Z");

    private static Map<String, SensorMetricBoundary> boundaries() {
        Map<String, SensorMetricBoundary> map = new HashMap<>();
        map.put("temperature", new SensorMetricBoundary("temperature", -40.0, 125.0));
        return map;
    }

    private static TelemetrySample sample(String metric, double value) {
        return TelemetrySample.unvalidated("dev-1", metric, value, T_DEVICE, T_INGRESS);
    }

    @Test
    void validate_valueInsideBoundary_returnsValid() {
        SensorMetricBoundaryPolicy policy = new SensorMetricBoundaryPolicy(boundaries());

        TelemetrySample result = policy.validate(sample("temperature", 20.5));

        assertThat(result.status()).isEqualTo(ValidationStatus.VALID);
    }

    @ParameterizedTest
    @ValueSource(doubles = {-40.0, 125.0})
    void validate_valueOnInclusiveLimit_returnsValid(double value) {
        SensorMetricBoundaryPolicy policy = new SensorMetricBoundaryPolicy(boundaries());

        assertThat(policy.validate(sample("temperature", value)).status())
                .isEqualTo(ValidationStatus.VALID);
    }

    @ParameterizedTest
    @ValueSource(doubles = {-40.001, 125.001, 1000.0})
    void validate_valueOutsideBoundary_returnsValidationFailed(double value) {
        SensorMetricBoundaryPolicy policy = new SensorMetricBoundaryPolicy(boundaries());

        assertThat(policy.validate(sample("temperature", value)).status())
                .isEqualTo(ValidationStatus.VALIDATION_FAILED);
    }

    @ParameterizedTest
    @ValueSource(doubles = {Double.NaN, Double.POSITIVE_INFINITY, Double.NEGATIVE_INFINITY})
    void validate_nonFiniteValue_returnsValidationFailedWithoutThrowing(double value) {
        SensorMetricBoundaryPolicy policy = new SensorMetricBoundaryPolicy(boundaries());

        assertThatNoException().isThrownBy(() -> policy.validate(sample("temperature", value)));
        assertThat(policy.validate(sample("temperature", value)).status())
                .isEqualTo(ValidationStatus.VALIDATION_FAILED);
    }

    @Test
    void validate_metricWithoutBoundary_returnsValidationFailed() {
        SensorMetricBoundaryPolicy policy = new SensorMetricBoundaryPolicy(boundaries());

        assertThat(policy.validate(sample("humidity", 10.0)).status())
                .isEqualTo(ValidationStatus.VALIDATION_FAILED);
    }

    @Test
    void validate_metricInDifferentCase_looksUpBoundaryCaseInsensitively() {
        SensorMetricBoundaryPolicy policy = new SensorMetricBoundaryPolicy(boundaries());

        assertThat(policy.validate(sample("TeMpErAtUrE", 20.0)).status())
                .isEqualTo(ValidationStatus.VALID);
    }

    @Test
    void validate_anyOutcome_preservesAllFieldsExceptStatus() {
        SensorMetricBoundaryPolicy policy = new SensorMetricBoundaryPolicy(boundaries());
        TelemetrySample input = sample("Temperature", 500.0);

        TelemetrySample result = policy.validate(input);

        assertThat(result).isEqualTo(input.withStatus(ValidationStatus.VALIDATION_FAILED));
        assertThat(result.deviceId()).isEqualTo("dev-1");
        assertThat(result.metric()).isEqualTo("Temperature");
        assertThat(result.value()).isEqualTo(500.0);
        assertThat(result.tDevice()).isEqualTo(T_DEVICE);
        assertThat(result.tIngress()).isEqualTo(T_INGRESS);
    }

    @Test
    void constructor_sourceMapMutatedAfterwards_doesNotAffectPolicy() {
        Map<String, SensorMetricBoundary> source = boundaries();
        SensorMetricBoundaryPolicy policy = new SensorMetricBoundaryPolicy(source);

        source.clear();

        assertThat(policy.validate(sample("temperature", 20.0)).status())
                .isEqualTo(ValidationStatus.VALID);
    }
}
