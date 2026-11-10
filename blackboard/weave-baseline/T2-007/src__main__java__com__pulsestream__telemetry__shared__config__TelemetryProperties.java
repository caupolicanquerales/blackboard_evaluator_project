package com.pulsestream.telemetry.shared.config;

import java.time.Duration;
import java.util.Map;
import jakarta.validation.Valid;
import jakarta.validation.constraints.AssertTrue;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.validation.annotation.Validated;

@ConfigurationProperties(prefix = "pulsestream.telemetry")
@Validated
public record TelemetryProperties(@NotNull Duration reorderWindow, @Positive int reorderBufferCapacity, @NotNull @Valid Window window, @NotNull @Valid Channels channels, @NotEmpty Map<String, Boundary> boundaries) {

    @AssertTrue(message = "reorderWindow must be positive")
    public boolean isReorderWindowPositive() {
        return reorderWindow == null || (!reorderWindow.isZero() && !reorderWindow.isNegative());
    }

    @AssertTrue(message = "boundary keys must be lower-case and boundaries non-null")
    public boolean isBoundariesWellFormed() {
        return boundaries == null || boundaries.entrySet().stream().allMatch(entry -> entry.getKey() != null && entry.getValue() != null && entry.getKey().equals(entry.getKey().toLowerCase(java.util.Locale.ROOT)));
    }

    public record Window(@NotNull Duration size, @NotNull Duration slide) {

        @AssertTrue(message = "size and slide must be positive")
        public boolean isPositive() {
            return size == null || slide == null || (!size.isZero() && !size.isNegative() && !slide.isZero() && !slide.isNegative());
        }

        @AssertTrue(message = "size must be greater than or equal to slide")
        public boolean isSizeAtLeastSlide() {
            return size == null || slide == null || size.compareTo(slide) >= 0;
        }
    }

    public record Channels(@Positive int validatedSamples, @Positive int sequencedSamples, @Positive int backfillDetections, @Positive int closedWindows, @Positive int revisionsAppended, @Positive int streamPublications, @Positive int streamSubscriberBuffer) {
    }

    public record Boundary(Double min, Double max) {

        @AssertTrue(message = "min must be less than or equal to max")
        public boolean isOrdered() {
            return min == null || max == null || min <= max;
        }
    }
}
