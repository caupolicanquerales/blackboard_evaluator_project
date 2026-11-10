package com.pulsestream.telemetry.sequencing.domain;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.pulsestream.telemetry.shared.events.TelemetrySampleEvent;
import com.pulsestream.telemetry.shared.events.TelemetryWindowClosedEvent;
import java.time.Duration;
import java.time.Instant;
import java.util.List;
import org.junit.jupiter.api.Test;

class SlidingWindowAssemblerTest {

    private static final Duration SIZE = Duration.ofSeconds(10);
    private static final Duration SLIDE = Duration.ofSeconds(5);

    private static Instant at(long epochSecond) {
        return Instant.ofEpochSecond(epochSecond);
    }

    private static TelemetrySampleEvent sample(long epochSecond) {
        return new TelemetrySampleEvent("device-1", "temperature", 21.5, at(epochSecond),
                at(epochSecond + 100), TelemetrySampleEvent.VALID);
    }

    private static List<Instant> starts(List<TelemetryWindowClosedEvent> windows) {
        return windows.stream().map(TelemetryWindowClosedEvent::windowStart).toList();
    }

    @Test
    void constructor_slideGreaterThanSize_throwsIllegalArgument() {
        assertThatThrownBy(() -> new SlidingWindowAssembler(SLIDE, SIZE))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void constructor_zeroSlide_throwsIllegalArgument() {
        assertThatThrownBy(() -> new SlidingWindowAssembler(SIZE, Duration.ZERO))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void constructor_negativeSlide_throwsIllegalArgument() {
        assertThatThrownBy(() -> new SlidingWindowAssembler(SIZE, Duration.ofSeconds(-5)))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void add_firstSample_returnsNoClosedWindows() {
        SlidingWindowAssembler assembler = new SlidingWindowAssembler(SIZE, SLIDE);

        assertThat(assembler.add(sample(3))).isEmpty();
    }

    @Test
    void add_sampleBeyondEarliestWindowEnd_closesOnlyThatWindow() {
        SlidingWindowAssembler assembler = new SlidingWindowAssembler(SIZE, SLIDE);
        assembler.add(sample(3));

        List<TelemetryWindowClosedEvent> closed = assembler.add(sample(7));

        assertThat(closed).hasSize(1);
        assertThat(closed.get(0).windowStart()).isEqualTo(at(-5));
        assertThat(closed.get(0).windowEnd()).isEqualTo(at(5));
        assertThat(closed.get(0).samples()).containsExactly(sample(3));
    }

    @Test
    void add_sampleBelongsToEveryContainingWindow() {
        SlidingWindowAssembler assembler = new SlidingWindowAssembler(SIZE, SLIDE);
        assembler.add(sample(3));
        assembler.add(sample(7));

        List<TelemetryWindowClosedEvent> closed = assembler.add(sample(12));

        assertThat(closed).hasSize(1);
        assertThat(closed.get(0).windowStart()).isEqualTo(at(0));
        assertThat(closed.get(0).windowEnd()).isEqualTo(at(10));
        assertThat(closed.get(0).samples()).containsExactly(sample(3), sample(7));
    }

    @Test
    void add_sampleExactlyAtWindowEnd_closesThatWindowAndExcludesSample() {
        SlidingWindowAssembler assembler = new SlidingWindowAssembler(SIZE, SIZE);
        assembler.add(sample(1));

        List<TelemetryWindowClosedEvent> closed = assembler.add(sample(10));

        assertThat(closed).hasSize(1);
        assertThat(closed.get(0).samples()).containsExactly(sample(1));
    }

    @Test
    void add_sampleAtWindowStart_isIncludedInThatWindow() {
        SlidingWindowAssembler assembler = new SlidingWindowAssembler(SIZE, SIZE);
        assembler.add(sample(10));

        List<TelemetryWindowClosedEvent> closed = assembler.add(sample(20));

        assertThat(closed).hasSize(1);
        assertThat(closed.get(0).windowStart()).isEqualTo(at(10));
        assertThat(closed.get(0).samples()).containsExactly(sample(10));
    }

    @Test
    void add_sampleClosingSeveralWindows_returnsThemAscendingByWindowStart() {
        SlidingWindowAssembler assembler = new SlidingWindowAssembler(SIZE, SLIDE);
        assembler.add(sample(3));
        assembler.add(sample(7));

        List<TelemetryWindowClosedEvent> closed = assembler.add(sample(30));

        assertThat(starts(closed)).containsExactly(at(0), at(5));
    }

    @Test
    void add_gapWithoutSamples_neverEmitsEmptyWindows() {
        SlidingWindowAssembler assembler = new SlidingWindowAssembler(SIZE, SIZE);
        assembler.add(sample(1));

        List<TelemetryWindowClosedEvent> closed = assembler.add(sample(35));

        assertThat(closed).hasSize(1);
        assertThat(closed.get(0).samples()).isNotEmpty();
    }

    @Test
    void add_closedWindow_carriesDeviceId() {
        SlidingWindowAssembler assembler = new SlidingWindowAssembler(SIZE, SIZE);
        assembler.add(sample(1));

        List<TelemetryWindowClosedEvent> closed = assembler.add(sample(11));

        assertThat(closed.get(0).deviceId()).isEqualTo("device-1");
    }

    @Test
    void flush_withOpenWindows_closesAllNonEmptyWindowsAscending() {
        SlidingWindowAssembler assembler = new SlidingWindowAssembler(SIZE, SLIDE);
        assembler.add(sample(3));
        assembler.add(sample(7));

        List<TelemetryWindowClosedEvent> flushed = assembler.flush();

        assertThat(starts(flushed)).containsExactly(at(-5), at(0), at(5));
        assertThat(flushed.get(1).samples()).containsExactly(sample(3), sample(7));
    }

    @Test
    void flush_calledTwice_secondCallReturnsEmpty() {
        SlidingWindowAssembler assembler = new SlidingWindowAssembler(SIZE, SLIDE);
        assembler.add(sample(3));
        assembler.flush();

        assertThat(assembler.flush()).isEmpty();
    }

    @Test
    void flush_noSamplesAdded_returnsEmpty() {
        SlidingWindowAssembler assembler = new SlidingWindowAssembler(SIZE, SLIDE);

        assertThat(assembler.flush()).isEmpty();
    }
}
