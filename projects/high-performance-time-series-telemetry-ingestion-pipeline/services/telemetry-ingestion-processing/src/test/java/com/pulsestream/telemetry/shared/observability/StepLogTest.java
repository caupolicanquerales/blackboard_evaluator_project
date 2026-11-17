package com.pulsestream.telemetry.shared.observability;

import static org.assertj.core.api.Assertions.assertThat;

import ch.qos.logback.classic.Level;
import ch.qos.logback.classic.Logger;
import ch.qos.logback.classic.spi.ILoggingEvent;
import ch.qos.logback.core.read.ListAppender;
import java.util.Map;
import java.util.stream.Collectors;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.slf4j.LoggerFactory;

class StepLogTest {

    private Logger logger;
    private ListAppender<ILoggingEvent> appender;

    @BeforeEach
    void attachAppender() {
        logger = (Logger) LoggerFactory.getLogger(StepLog.class);
        logger.setLevel(Level.TRACE);
        appender = new ListAppender<>();
        appender.start();
        logger.addAppender(appender);
    }

    @AfterEach
    void detachAppender() {
        logger.detachAppender(appender);
        appender.stop();
    }

    private static Map<String, Object> keyValues(ILoggingEvent event) {
        return event.getKeyValuePairs().stream()
                .collect(Collectors.toMap(kv -> kv.key, kv -> kv.value));
    }

    @Test
    void emit_validStepAndCorrelationId_logsExactlyOneEvent() {
        new StepLog().emit("ingest-received", "corr-1");

        assertThat(appender.list).hasSize(1);
    }

    @Test
    void emit_validStepAndCorrelationId_logsAtInfoLevel() {
        new StepLog().emit("ingest-received", "corr-1");

        assertThat(appender.list.get(0).getLevel()).isEqualTo(Level.INFO);
    }

    @Test
    void emit_validStepAndCorrelationId_carriesStepKeyValue() {
        new StepLog().emit("ingest-received", "corr-1");

        assertThat(keyValues(appender.list.get(0))).containsEntry("step", "ingest-received");
    }

    @Test
    void emit_validStepAndCorrelationId_carriesCorrelationIdKeyValue() {
        new StepLog().emit("ingest-received", "corr-1");

        assertThat(keyValues(appender.list.get(0))).containsEntry("correlationId", "corr-1");
    }
}
