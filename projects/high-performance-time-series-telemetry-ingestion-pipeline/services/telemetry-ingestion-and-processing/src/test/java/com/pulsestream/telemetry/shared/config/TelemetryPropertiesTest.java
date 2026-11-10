package com.pulsestream.telemetry.shared.config;

import static org.assertj.core.api.Assertions.assertThat;

import com.pulsestream.telemetry.shared.config.TelemetryProperties.Boundary;
import com.pulsestream.telemetry.shared.config.TelemetryProperties.Channels;
import com.pulsestream.telemetry.shared.config.TelemetryProperties.Window;
import jakarta.validation.ConstraintViolation;
import jakarta.validation.Validation;
import jakarta.validation.Validator;
import java.time.Duration;
import java.util.Map;
import java.util.Set;
import org.junit.jupiter.api.Test;

class TelemetryPropertiesTest {

    private static final Validator VALIDATOR = Validation.buildDefaultValidatorFactory().getValidator();

    private static Window window(Duration size, Duration slide) {
        return new Window(size, slide);
    }

    private static Channels channels(int capacity) {
        return new Channels(capacity, capacity, capacity, capacity, capacity, capacity, capacity);
    }

    private static Map<String, Boundary> boundaries() {
        return Map.of("temperature", new Boundary(-50.0, 150.0));
    }

    private static TelemetryProperties props(Duration reorderWindow, int reorderCapacity, Window window,
            Channels channels, Map<String, Boundary> boundaries) {
        return new TelemetryProperties(reorderWindow, reorderCapacity, window, channels, boundaries);
    }

    private static TelemetryProperties valid() {
        return props(Duration.ofSeconds(5), 100, window(Duration.ofSeconds(60), Duration.ofSeconds(10)),
                channels(64), boundaries());
    }

    private static Set<ConstraintViolation<TelemetryProperties>> validate(TelemetryProperties p) {
        return VALIDATOR.validate(p);
    }

    @Test
    void validate_validProperties_hasNoViolations() {
        assertThat(validate(valid())).isEmpty();
    }

    @Test
    void validate_nullReorderWindow_hasViolation() {
        var p = props(null, 100, window(Duration.ofSeconds(60), Duration.ofSeconds(10)), channels(64), boundaries());
        assertThat(validate(p)).isNotEmpty();
    }

    @Test
    void validate_zeroReorderWindow_hasViolation() {
        var p = props(Duration.ZERO, 100, window(Duration.ofSeconds(60), Duration.ofSeconds(10)), channels(64),
                boundaries());
        assertThat(validate(p)).isNotEmpty();
    }

    @Test
    void validate_negativeReorderWindow_hasViolation() {
        var p = props(Duration.ofSeconds(-1), 100, window(Duration.ofSeconds(60), Duration.ofSeconds(10)),
                channels(64), boundaries());
        assertThat(validate(p)).isNotEmpty();
    }

    @Test
    void validate_zeroReorderBufferCapacity_hasViolation() {
        var p = props(Duration.ofSeconds(5), 0, window(Duration.ofSeconds(60), Duration.ofSeconds(10)),
                channels(64), boundaries());
        assertThat(validate(p)).isNotEmpty();
    }

    @Test
    void validate_nullWindowSize_hasViolation() {
        var p = props(Duration.ofSeconds(5), 100, window(null, Duration.ofSeconds(10)), channels(64), boundaries());
        assertThat(validate(p)).isNotEmpty();
    }

    @Test
    void validate_nullWindowSlide_hasViolation() {
        var p = props(Duration.ofSeconds(5), 100, window(Duration.ofSeconds(60), null), channels(64), boundaries());
        assertThat(validate(p)).isNotEmpty();
    }

    @Test
    void validate_zeroWindowSlide_hasViolation() {
        var p = props(Duration.ofSeconds(5), 100, window(Duration.ofSeconds(60), Duration.ZERO), channels(64),
                boundaries());
        assertThat(validate(p)).isNotEmpty();
    }

    @Test
    void validate_windowSizeSmallerThanSlide_hasViolation() {
        var p = props(Duration.ofSeconds(5), 100, window(Duration.ofSeconds(5), Duration.ofSeconds(10)),
                channels(64), boundaries());
        assertThat(validate(p)).isNotEmpty();
    }

    @Test
    void validate_windowSizeEqualToSlide_hasNoViolations() {
        var p = props(Duration.ofSeconds(5), 100, window(Duration.ofSeconds(10), Duration.ofSeconds(10)),
                channels(64), boundaries());
        assertThat(validate(p)).isEmpty();
    }

    @Test
    void validate_zeroChannelCapacity_hasViolation() {
        var p = props(Duration.ofSeconds(5), 100, window(Duration.ofSeconds(60), Duration.ofSeconds(10)),
                new Channels(64, 64, 64, 0, 64, 64, 64), boundaries());
        assertThat(validate(p)).isNotEmpty();
    }

    @Test
    void validate_negativeStreamSubscriberBuffer_hasViolation() {
        var p = props(Duration.ofSeconds(5), 100, window(Duration.ofSeconds(60), Duration.ofSeconds(10)),
                new Channels(64, 64, 64, 64, 64, 64, -1), boundaries());
        assertThat(validate(p)).isNotEmpty();
    }

    @Test
    void validate_emptyBoundaries_hasViolation() {
        var p = props(Duration.ofSeconds(5), 100, window(Duration.ofSeconds(60), Duration.ofSeconds(10)),
                channels(64), Map.of());
        assertThat(validate(p)).isNotEmpty();
    }

    @Test
    void validate_boundaryMinGreaterThanMax_hasViolation() {
        var p = props(Duration.ofSeconds(5), 100, window(Duration.ofSeconds(60), Duration.ofSeconds(10)),
                channels(64), Map.of("temperature", new Boundary(10.0, 5.0)));
        assertThat(validate(p)).isNotEmpty();
    }

    @Test
    void validate_boundaryMinEqualToMax_hasNoViolations() {
        var p = props(Duration.ofSeconds(5), 100, window(Duration.ofSeconds(60), Duration.ofSeconds(10)),
                channels(64), Map.of("temperature", new Boundary(5.0, 5.0)));
        assertThat(validate(p)).isEmpty();
    }

    @Test
    void validate_boundaryWithUnboundedSides_hasNoViolations() {
        var p = props(Duration.ofSeconds(5), 100, window(Duration.ofSeconds(60), Duration.ofSeconds(10)),
                channels(64), Map.of("humidity", new Boundary(null, 100.0), "pressure", new Boundary(0.0, null),
                        "any", new Boundary(null, null)));
        assertThat(validate(p)).isEmpty();
    }

    @Test
    void accessors_validProperties_exposeConfiguredValues() {
        var p = valid();
        assertThat(p.reorderWindow()).isEqualTo(Duration.ofSeconds(5));
        assertThat(p.window().size()).isEqualTo(Duration.ofSeconds(60));
        assertThat(p.channels().closedWindows()).isEqualTo(64);
        assertThat(p.boundaries().get("temperature").max()).isEqualTo(150.0);
    }
}
