package com.pulsestream.telemetry.eventlog.application;

import static org.assertj.core.api.Assertions.assertThat;

import com.pulsestream.telemetry.eventlog.domain.EventRecord;
import com.pulsestream.telemetry.validation.domain.TelemetrySample;
import java.lang.reflect.Method;
import java.time.Instant;
import org.junit.jupiter.api.Test;
import reactor.core.publisher.Mono;

class EventLogRepositoryTest {

    @Test
    void append_declared_acceptsSampleAndReturnsMonoOfRecord() throws NoSuchMethodException {
        Method method = EventLogRepository.class.getMethod("append", TelemetrySample.class);

        assertThat(method.getReturnType()).isEqualTo(Mono.class);
    }

    @Test
    void findLatest_declared_acceptsKeyAndReturnsMono() throws NoSuchMethodException {
        Method method = EventLogRepository.class.getMethod("findLatest", String.class, String.class, Instant.class);

        assertThat(method.getReturnType()).isEqualTo(Mono.class);
    }

    @Test
    void append_declared_returnTypeParameterIsEventRecord() throws NoSuchMethodException {
        Method method = EventLogRepository.class.getMethod("append", TelemetrySample.class);

        assertThat(method.getGenericReturnType().getTypeName()).contains(EventRecord.class.getName());
    }
}
