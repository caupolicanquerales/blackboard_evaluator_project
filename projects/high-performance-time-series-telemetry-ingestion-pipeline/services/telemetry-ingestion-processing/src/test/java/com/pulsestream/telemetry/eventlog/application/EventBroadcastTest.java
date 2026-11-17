package com.pulsestream.telemetry.eventlog.application;

import static org.assertj.core.api.Assertions.assertThat;

import com.pulsestream.telemetry.eventlog.domain.EventRecord;
import java.lang.reflect.Method;
import org.junit.jupiter.api.Test;
import reactor.core.publisher.Flux;

class EventBroadcastTest {

    @Test
    void publish_declared_acceptsEventRecordAndReturnsBoolean() throws NoSuchMethodException {
        Method method = EventBroadcast.class.getMethod("publish", EventRecord.class);

        assertThat(method.getReturnType()).isEqualTo(boolean.class);
    }

    @Test
    void stream_declared_returnsFluxWithNoParameters() throws NoSuchMethodException {
        Method method = EventBroadcast.class.getMethod("stream");

        assertThat(method.getReturnType()).isEqualTo(Flux.class);
    }
}
