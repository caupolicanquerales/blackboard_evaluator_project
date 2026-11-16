package com.blackboard.telemetry.history.infrastructure;

import static org.assertj.core.api.Assertions.assertThat;

import ch.qos.logback.classic.Logger;
import ch.qos.logback.classic.spi.ILoggingEvent;
import ch.qos.logback.core.read.ListAppender;
import com.blackboard.telemetry.history.domain.HistoryEvent;
import com.blackboard.telemetry.history.domain.HistoryEventType;
import com.blackboard.telemetry.ingestion.domain.MetricKind;
import com.blackboard.telemetry.ingestion.domain.TelemetrySample;
import com.blackboard.telemetry.ingestion.domain.ValidationStatus;
import com.blackboard.telemetry.shared.config.TelemetryProperties;
import java.time.Duration;
import java.time.Instant;
import java.util.List;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.slf4j.LoggerFactory;
import reactor.test.StepVerifier;

class InMemoryHistoryEventPublisherTest {

    private ListAppender<ILoggingEvent> appender;
    private Logger logger;

    @BeforeEach
    void attachAppender() {
        logger = (Logger) LoggerFactory.getLogger(InMemoryHistoryEventPublisher.class);
        appender = new ListAppender<>();
        appender.start();
        logger.addAppender(appender);
    }

    @AfterEach
    void detachAppender() {
        logger.detachAppender(appender);
    }

    private static InMemoryHistoryEventPublisher publisher(int capacity) {
        return new InMemoryHistoryEventPublisher(new TelemetryProperties(
                Duration.ofSeconds(5), 10, 10, capacity, Duration.ofMillis(100), List.of()));
    }

    private static HistoryEvent event(String correlationId) {
        TelemetrySample sample = new TelemetrySample("dev-1", MetricKind.values()[0],
                Instant.parse("2026-01-01T00:00:00Z"), Instant.parse("2026-01-01T00:00:01Z"),
                21.5, ValidationStatus.VALID);
        return new HistoryEvent(HistoryEventType.values()[0], sample, 0, 0, correlationId);
    }

    @Test
    void publish_subscriberPresent_deliversEventAndCompletes() {
        InMemoryHistoryEventPublisher publisher = publisher(4);
        HistoryEvent event = event("req-1");
        var verifier = StepVerifier.create(publisher.events().take(1)).expectNext(event).expectComplete();

        publisher.publish(event).block();

        verifier.verify(Duration.ofSeconds(2));
    }

    @Test
    void publish_returnsMonoThatCompletesEmpty() {
        StepVerifier.create(publisher(4).publish(event("req-1"))).verifyComplete();
    }

    @Test
    void events_lateSubscriberAfterOverflow_replaysOnlyLastBroadcastCapacityEvents() {
        InMemoryHistoryEventPublisher publisher = publisher(2);
        HistoryEvent e1 = event("req-1");
        HistoryEvent e2 = event("req-2");
        HistoryEvent e3 = event("req-3");
        publisher.publish(e1).block();
        publisher.publish(e2).block();
        publisher.publish(e3).block();

        StepVerifier.create(publisher.events().take(2))
                .expectNext(e2, e3)
                .verifyComplete();
    }

    @Test
    void publish_twoEvents_logsOneStepEventPerPublishedEvent() {
        InMemoryHistoryEventPublisher publisher = publisher(4);

        publisher.publish(event("req-1")).block();
        publisher.publish(event("req-2")).block();

        assertThat(appender.list)
                .hasSize(2)
                .allSatisfy(e -> assertThat(e.getLoggerName())
                        .isEqualTo(InMemoryHistoryEventPublisher.class.getName()));
    }
}
