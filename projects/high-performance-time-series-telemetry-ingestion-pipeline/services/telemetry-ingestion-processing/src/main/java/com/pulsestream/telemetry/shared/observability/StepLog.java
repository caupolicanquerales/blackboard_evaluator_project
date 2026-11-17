package com.pulsestream.telemetry.shared.observability;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public class StepLog {

    private static final Logger LOGGER = LoggerFactory.getLogger(StepLog.class);

    public void emit(String step, String correlationId) {
        LOGGER.atInfo().addKeyValue("step", step).addKeyValue("correlationId", correlationId).log("step");
    }
}
